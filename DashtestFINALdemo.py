import pandas as pd
import requests
from pathlib import Path
from shiny import App, render, ui, reactive, run_app
from shinywidgets import render_widget, output_widget
from sqlalchemy import create_engine
import plotly.graph_objects as go
import keys
import random

here = Path(__file__).parent

CARD_BG  = "background: rgba(49, 107, 180, 0.4);"
FONT     = 'font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;'

    # Drugačiji paket/struktura za SQL sekciju zbog brze reaktivnosti na promjenu filtera
def fetch_data(days):
    engine = create_engine(f"{keys.DB_PARAMS}")
    where  = "" if days == "all" else f"WHERE time >= NOW() - INTERVAL '{days} days'"
    df = pd.read_sql( f"SELECT systolic, diastolic, pulse, time FROM public.bp_gmail {where} ORDER BY time;",engine)
    df["time"] = pd.to_datetime(df["time"])
    return df

# LLM ZAHTJEV BLOK
def get_meal_suggestions(sys, dia, bpm):
    rawPrompt = f"""You are a nutrition advisor. Based on the health data below, suggest 3 meals.
HEALTH DATA:
- Age: 22 years | Weight: 62 kg
- Heart Rate: {bpm} BPM | Blood Pressure: {sys}/{dia} mmHg

TASK:
1. Analyze if any given metrics suggest health concerns if pressure normal under 120 or prehypertension over 120 (two sentences)
2. Generate 3 short Mediterranean meals (NO SALMON)
   (if blood pressure under SYS 120 then recommend tasty food instead of healthy), format as:
   • Meal 1: [Name]  • Meal 2: [Name]  • Meal 3: [Name]
3. Brief explanation why these meals fit (one sentence per meal)
Requirements:
- No duplicate main ingredient.
- No duplicate protein.
- Include a mix of seafood, poultry and beef/lamb where appropriate.
- Then select any 3 of those 10 to recommend.
"""

    # IZVORNI HTTP POZIV LLM-u S OPENROUTERA
    r = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {keys.OPENROUTER_KEY}", "Content-Type": "application/json"},
        json={
            "model": "mistralai/mistral-medium-3-5",
            "messages": [{"role": "user", "content": rawPrompt}],
            "max_tokens": 500, "temperature": 1.1,
            "frequency_penalty": 0.6, "presence_penalty": 1.3, "seed": random.randint(1, 1000000),
        },
    )

    # FORMATIRANJE ODGOVORA U JSON OBLIK
    try:
        result = r.json()
    except Exception:
        return f"Invalid response: {r.text}"
    if "error"   in result: return f"API error: {result['error']}"
    return result["choices"][0]["message"].get("content") or "Empty response from model."

# BLOK APLIKACIJE (STRANICA + SIDEBAR STIL)
app_ui = ui.page_sidebar(
    ui.sidebar(
        ui.tags.figure(
        ui.output_image("sidebar_img", height="200px"),
              ui.hr(),
              ui.tags.figcaption(
                "Sistolički/Dijastolički tlak kroz vrijeme",
                style=f"text-align:center; font-size:22px; background:rgba(55,119,200,0.4); border-radius:16px; border-color:#316bb4; {FONT} width:100%; align-items:center",
              ),
        ),
        ui.hr(),
        ui.div(ui.h4("Filter"), ui.input_select("days", None, {"2":"2 Dana","7":"7 Dana","30":"30 Dana","all":"Sveukupno"}, selected="30"), style=FONT),
        ui.div(ui.h4("Posljednji tlak"), ui.output_text("latest_bp")),
        ui.div(ui.h4("Prosječni tlak"), ui.output_text("avg_bp")),
        ui.div(ui.h4("Status"),  ui.output_ui("bp_status"), style="margin-bottom:10px;"),
        style="background:rgba(55,119,200,0.4); flex: 1; height:100%;",
    ),
    # NAVIGACIJSKA TRAKA
    ui.page_fluid(ui.navset_tab(
        ui.nav_panel("Početna",
                     ui.card(
                         ui.markdown("""
                                ## Nadzorna ploča krvnog tlaka
                                Dobrodošli na Panacea web stranicu za praćenje krvnog tlaka. Ova prototipna stranica sadrži
                                podatkovne vizualizacije, osnovne informacije o provedenim mjerenjima i odlomak s umjetnom inteligencijom

                                Ploča se može koristiti za:
                                - Praćenje mjerenja krvnog tlaka kroz vrijeme
                                - Stjecanje uvida u to kako se mijenjaju vrijednosti
                                - Generiranje eksperimentalnog AI odgovora koji šalje tri jela koja smatra primjerenim
                                  za posljednji rezultat mjerenja tlaka, korisničke dobi i tjelesne težine

                                Koristite navigacijsku traku za pregled.
                                """),
                         style="background: rgba(49, 107, 180, 0.4);"
                     )
        ),
        ui.nav_panel("Graf",
            ui.card(ui.card_header("Graf krvnog tlaka"), output_widget("bp_graph"), full_screen=True, style=CARD_BG)
        ),
        ui.nav_panel("AI",
            ui.card(
                ui.card_header("AI upit za jela"),
                ui.input_action_button("generate", "Generate", class_="generate-btn"),
                ui.hr(),
                ui.output_ui("llm_output"),
                ui.hr(),
                ui.h5("Postotak stanja krvnog tlaka", style="text-align:center;"),
                ui.div(output_widget("bp_pie"), style="max-width:500px; margin:0 auto; width:100%; border-radius:16px;"),
                style=CARD_BG,
            )
        ),
    ),
    ),
    style="background:rgba(49,107,180,0.1);",
)

# REAKTIVNI PRIKAZ/RENDER SADRŽAJA
def server(input, output, session):
    @render.image
    def sidebar_img():
        return {"src": str(here / "www" / "panacealogo.png"),
                "style": "width:100%; max-width:180px; height: auto; border-radius:20px; border:5px solid #d6d9df; padding:3px; display:block; margin: 0 auto;"}

    @reactive.calc
    def data():
        return fetch_data(input.days())

    @render.text
    def latest_bp():
        df = data()
        r = df.iloc[-1]
        return f"{r['systolic']}/{r['diastolic']} mmHg"

    @render.text
    def avg_bp():
        df = data()
        return f"{int(df['systolic'].mean())}/{int(df['diastolic'].mean())} mmHg"

    @render.ui
    def bp_status():
        df = data()
        sys = df.iloc[-1]["systolic"]
        color, text = ("#72eb83","Normalan") if sys < 120 else ("#d8ac59","Povišen") if sys < 140 else ("#f84b4a","Visok")
        return ui.div(text, style=f"background-color:{color}; color:white; padding:2px; border-radius:5px; text-align:center; font-weight:bold;")

    @render_widget
    def bp_graph():
        df = data()
        fig = go.Figure([
            go.Scatter(x=df["time"], y=df["systolic"],  name="Sistolički",  mode="lines",
                       line=dict(width=2, color="green"),  fill="tozeroy", fillcolor="rgba(110,185,63,0.15)"),
            go.Scatter(x=df["time"], y=df["diastolic"], name="Dijastolički", mode="lines",
                       line=dict(width=2, color="indigo"), fill="tozeroy", fillcolor="rgba(190,65,99,0.15)")])
        fig.update_layout(yaxis_title="mmHg", legend=dict(orientation="h", y=1.1),
                          margin=dict(l=40, r=20, t=40, b=40), autosize=True,
                          hovermode="x unified", plot_bgcolor="rgba(49,107,180,0.08)", paper_bgcolor="rgba(49,107,180,0.04)")
        return fig

    @reactive.event(input.generate)
    def llm_result():
        df = data()
        r = df.iloc[-1]
        return get_meal_suggestions(r["systolic"], r["diastolic"], r["pulse"])

    @render.ui
    def llm_output():
        return ui.markdown(llm_result())

    @render_widget
    def bp_pie():
        df = data()
        s = df["systolic"]
        vals = [(s < 120).sum(), ((s >= 120) & (s <= 139)).sum(), (s > 139).sum(), (s >159).sum()]
        fig = go.Figure(go.Pie(
            labels=["Normalan","Predhipertenzija","Hipertenzija prvog stupnja","Hipertenzija drugog stupnja"], values=vals,
            hole=0.4, textinfo="label+percent", marker=dict(colors=["green","orange","red", "indigo"])
        ))
        fig.update_layout(showlegend=False, autosize=True, height=250, paper_bgcolor="rgba(49,107,180,0.01)")
        return fig

# OTVARANJE STRANICE NA LOKALNI PRIKLJUČAK
app = App(app_ui, server)
if __name__ == '__main__':
    run_app(
        app,
        host="localhost",
        port=8000,
        launch_browser=False,
    )
