from dash import html, dash_table
import pandas as pd

# Exemplo de dados para a tabela de metadados
df_metadata = pd.DataFrame({
    "Package": ["Package 1", "Package 2", "Package 3"],
    "Label": ["Label 1", "Label 2", "Label 3"],
    "Syntax": ["Syntax 1", "Syntax 2", "Syntax 3"],
    "Example": ["Example 1", "Example 2", "Example 3"],
    "Definition": ["Definition 1", "Definition 2", "Definition 3"]
})

metadata_page = html.Div([
    html.H2("Tabela de Metadados"),
    dash_table.DataTable(
        id='metadata-table',
        columns=[{"name": i, "id": i} for i in df_metadata.columns],
        data=df_metadata.to_dict("records"),
        style_table={'overflowX': 'auto'},
        style_header={'backgroundColor': 'rgb(230, 230, 230)', 'fontWeight': 'bold'},
        style_cell={'textAlign': 'left', 'padding': '5px'},
    ),
])
