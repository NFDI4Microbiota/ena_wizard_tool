from dash import Dash, dcc, html, Input, Output
import dash_bootstrap_components as dbc
from sidebar import sidebar
from pages.form_page import form_page
from pages.metadata_page import metadata_page
from pages.metadata_overview import metadata_overview
from pages.upload_page import upload_page
from pages.option5_page import option5_page

# Inicialização da aplicação
app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

# Layout principal da aplicação
app.layout = html.Div([dcc.Location(id="url"), sidebar, html.Div(id="page-content", style={"marginLeft": "18rem", "padding": "2rem 1rem"})])

# Função de navegação entre páginas
@app.callback(Output("page-content", "children"), [Input("url", "pathname")])
def display_page(pathname):
    if pathname == "/metadata":
        return metadata_page
    elif pathname == "/metadata_overview":
        return metadata_overview
    elif pathname == "/upload_page":
        return upload_page
    elif pathname == "/option5":
        return option5_page
    else:
        return form_page

# Executa a aplicação
if __name__ == "__main__":
    app.run_server(debug=True)
