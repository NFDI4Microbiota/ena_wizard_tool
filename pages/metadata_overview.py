from dash import html

from dash import html, dash_table, dcc
import pandas as pd

# Lê o arquivo CSV
df_metadata = pd.read_csv("20241111_proposed_terrestrial_metadata_fields.csv")  # Substitua com o caminho do seu arquivo CSV

# Página de Metadados Terrestres
metadata_overview = html.Div([
    html.H2("Terrestrial Metadata"),
    dash_table.DataTable(
        id='metadata-table',
        columns=[{"name": i, "id": i} for i in df_metadata.columns],
        data=df_metadata.to_dict("records"),
        style_table={'overflowX': 'auto'},
        style_header={'backgroundColor': 'rgb(230, 230, 230)', 'fontWeight': 'bold'},
        style_cell={'textAlign': 'left', 'padding': '5px'},
    ),
    html.Br(),
    dcc.Link("Voltar ao menu principal", href="/")
])
