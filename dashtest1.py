import psycopg2
import pandas as pd
from shiny import *

def connect():
    return psycopg2.connect(user="postgres", password="1234", host="localhost", port="3307",database="postgres")

def fetch_data():
    conn = connect()
    cursor = conn.cursor()
    query = """SELECT * FROM public.bp_gmail;"""
    df = pd.read_sql(query, conn)
    cursor.close()
    conn.close()
    return df

def render_table(df):
    header = ui.tags.tr(
        [ui.tags.th(col, style="border:1px solid #ccc; padding:5px;") for col in df.columns]
    )
    body = [
        ui.tags.tr(
            [ui.tags.td(str(row[col]), style="border:1px solid #ccc; padding:5px;") for col in df.columns]
        ) for _, row in df.iterrows()
    ]
    return ui.tags.table(
        header,
        *body,
        style="border-collapse: collapse; width: 100%;"
    )

app_ui = ui.page_sidebar(
    ui.sidebar(ui.tags.h3("Test sidebar", style="font-size: 30px; margin-top: 0;")),
    ui.output_ui("table")
)
def server(input,output,session):
    @output()
    @render.ui
    def table():
        df = fetch_data()
        return render_table(df)

app = App(app_ui, server)
if __name__ == '__main__':
    run_app(
        app,
        host="localhost",
        port=8005,
        launch_browser=False,
    )