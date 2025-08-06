from dash import html
import dash_bootstrap_components as dbc

sidebar = html.Div(
    [
        html.H2("Menu", className="display-4"),
        html.Hr(),
        dbc.Nav(
            [
                dbc.NavLink("Metadata Configurator", href="/", active="exact"),
                dbc.NavLink("Metadata Table", href="/metadata", active="exact"),
                dbc.NavLink("Metadata Overview", href="/metadata_overview", active="exact"),
                dbc.NavLink("Submission to ENA", href="/upload_page", active="exact"),
                #dbc.NavLink("Opção 5", href="/option5", active="exact"),
            ],
            vertical=True,
            pills=True,
        ),
    ],
    style={"position": "fixed", "top": 0, "left": 0, "bottom": 0, "width": "16rem", "padding": "2rem 1rem", "backgroundColor": "#FFB02D"},
)
