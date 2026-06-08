import pandas as pd
import matplotlib, requests
from pathlib import Path
from shiny import App, render, ui, reactive
from shinywidgets import render_widget, output_widget
from sqlalchemy import create_engine
import plotly.graph_objects as go

matplotlib.use("Agg")
here = Path(__file__).parent

CARD_BG  = "background: rgba(49, 107, 180, 0.4);"
FONT     = 'font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;'

    # Drugačiji paket/struktura za SQL sekciju zbog brze reaktivnosti na promjenu filtera
def fetch_data(days):
    engine = create_engine("TYPE_ENGINE")
    where  = "" if days == "all" else f"WHERE time >= NOW() - INTERVAL '{days} days'"
    df = pd.read_sql( f"SELECT systolic, diastolic, pulse, time FROM public.bp_gmail {where} ORDER BY time;",engine)
    df["time"] = pd.to_datetime(df["time"])
    return df
  
def get_meal_suggestions(sys, dia, bpm):
    rawPrompt = f"""You are a nutrition advisor. Based on the health data below, suggest 3 meals.
HEALTH DATA:
- Age: 22 years | Weight: 62 kg
- Heart Rate: {bpm} BPM | Blood Pressure: {sys}/{dia} mmHg

TASK:
1. Analyze if any metrics suggest health concerns (two sentences)
2. Generate 3 short Mediterranean appropriate meals (do not generate recurring meals).
   (if blood pressure under SYS 120 then recommend tasty food instead of healthy), format as:
   • Meal 1: [Name]  • Meal 2: [Name]  • Meal 3: [Name]
3. Brief explanation why these meals fit (one sentence per meal)
"""
    r = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": "KEY", "Content-Type": "application/json"},
        json={
            "model": "qwen/qwen3.6-flash",
            "messages": [{"role": "user", "content": rawPrompt}],
            "max_tokens": 1000, "temperature": 0.85,
            "top_p": 1, "frequency_penalty": 0.9, "presence_penalty": 0.8,
        },
    )
    try:
        result = r.json()
    except Exception:
        return f"Invalid response: {r.text}"
    if "error"   in result: return f"API error: {result['error']}"
    return result["choices"][0]["message"].get("content") or "Empty response from model."

app_ui = ui.page_sidebar(
    ui.sidebar(
        ui.tags.figure(
            ui.output_image("sidebar_img"),
            ui.tags.figcaption(
                "Systolic/Diastolic Time Series",
                style=f"text-align:center; font-size:22px; background:rgba(55,119,200,0.4); border-radius:16px; border-color:#316bb4; {FONT} width:100%;",
            ),
        ),
        ui.hr(),
        ui.div(ui.h4("Filter"), ui.input_select("days", None, {"2":"2 Days","7":"7 Days","30":"30 Days","all":"All time"}, selected="30"), style=FONT),
        ui.div(ui.h4("Latest"), ui.output_text("latest_bp")),
        ui.div(ui.h4("Average"), ui.output_text("avg_bp"),    style="margin-bottom:5px;"),
        ui.div(ui.h4("Status"),  ui.output_ui("bp_status"),   style="margin-bottom:5px;"),
        style="background:rgba(55,119,200,0.4); display:flex; flex-direction:column;",
    ),
    ui.page_fluid(ui.navset_tab(
        ui.nav_panel("Home",
                     ui.card(
                         ui.markdown("""
                                ## Blood Pressure Monitoring Dashboard
                                With this dashboard you will be able to track your blood pressure through time,
                                gain food recommendations from an assigned LLM and some basic analytics about your health

                                You may use this dashboard for:
                                - Tracking blood pressure trends over time
                                - Gain insight into how the average values are changing
                                - Get AI-based meal recommendations and general health information

                                Use the navigation above to switch between pages.
                                """),
                         style="background: rgba(49, 107, 180, 0.4);"
                     )
        ),
        ui.nav_panel("Graph",
            ui.card(ui.card_header("Blood Pressure Over Time"), output_widget("bp_graph"), full_screen=True, style=CARD_BG)
        ),
        ui.nav_panel("AI",
            ui.card(
                ui.card_header("AI Meal Recommendations"),
                ui.input_action_button("generate", "Generate", class_="generate-btn"),
                ui.hr(),
                ui.output_ui("llm_output"),
                ui.hr(),
                ui.h5("Blood Pressure Distribution"),
                ui.div(output_widget("bp_pie"), style="max-width:500px; margin:0 auto; width:100%; border-radius:16px;"),
                style=CARD_BG,
            )
        ),
    ),
    ),
    style="background:rgba(49,107,180,0.1); height:100vh;",
)


def server(input, output, session):
    @render.image
    def sidebar_img():
        return {"src": str(here / "www" / "panacealogo.png"),
                "style": "width:100%; max-width:180px; height:auto; border-radius:20px; border:5px solid #d6d9df; padding:3px; display:block; margin:0 auto;"}

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
        color, text = ("#72eb83","Normal") if sys < 120 else ("#d8ac59","Elevated") if sys < 140 else ("#f84b4a","High")
        return ui.div(text, style=f"background-color:{color}; color:white; padding:6px; border-radius:5px; text-align:center; font-weight:bold;")

    @render_widget
    def bp_graph():
        df = data()
        fig = go.Figure([
            go.Scatter(x=df["time"], y=df["systolic"],  name="Systolic",  mode="lines",
                       line=dict(width=2, color="green"),  fill="tozeroy", fillcolor="rgba(110,185,63,0.15)"),
            go.Scatter(x=df["time"], y=df["diastolic"], name="Diastolic", mode="lines",
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
        vals = [(s < 120).sum(), ((s >= 120) & (s <= 139)).sum(), (s > 139).sum()]
        fig = go.Figure(go.Pie(
            labels=["Normal","Prehypertension","Hypertension"], values=vals,
            hole=0.4, textinfo="label+percent", marker=dict(colors=["green","orange","red"])
        ))
        fig.update_layout(showlegend=True, autosize=True, height=250, paper_bgcolor="rgba(49,107,180,0.01)")
        return fig


app = App(app_ui, server)
if __name__ == "__main__":
    app.run()
