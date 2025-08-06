from dash import Dash, dcc, html, Input, Output, State
import dash_bootstrap_components as dbc

app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

# Página do formulário com layout aprimorado
form_page = html.Div([
    html.H2("Investigation Information", style={"margin-bottom": "20px"}),

    # Investigation Identifier, Title, and Description
    dbc.Row([
        dbc.Col([
            dbc.Label("Investigation Identifier:"),
            dbc.Input(type="text", placeholder="@WNO_UNLOCK")
        ], width=4),
        dbc.Col([
            dbc.Label("Investigation Title:"),
            dbc.Input(type="text", placeholder="Investigation Title")
        ], width=4),
        dbc.Col([
            dbc.Label("Investigation Description:"),
            dbc.Input(type="text", placeholder="Investigation Description")
        ], width=4),
    ], style={"margin-bottom": "20px"}),

    # First Name, Last Name, Email, Organization, ORCID, Department, Role
    html.Hr(),
    html.H3("Add persons involved in this investigation.", style={"margin-top": "20px"}),
    dbc.Row([
        dbc.Col([
            dbc.Label("First name:"),
            dbc.Input(type="text", placeholder="First Name")
        ], width=3),
        dbc.Col([
            dbc.Label("Last name:"),
            dbc.Input(type="text", placeholder="Last Name")
        ], width=3),
        dbc.Col([
            dbc.Label("Email:"),
            dbc.Input(type="email", placeholder="Email")
        ], width=3),
        dbc.Col([
            dbc.Label("Organization:"),
            dbc.Input(type="text", placeholder="Organization")
        ], width=3),
    ], style={"margin-bottom": "20px"}),

    dbc.Row([
        dbc.Col([
            dbc.Label("ORCID:"),
            dbc.Input(type="text", placeholder="ORCID")
        ], width=3),
        dbc.Col([
            dbc.Label("Department:"),
            dbc.Input(type="text", placeholder="Department")
        ], width=3),
        dbc.Col([
            dbc.Label("Role:"),
            dbc.Select(options=[
                {"label": "Role 1", "value": "role1"},
                {"label": "Role 2", "value": "role2"},
                {"label": "Role 3", "value": "role3"}
            ], placeholder="Select a role")
        ], width=3),
    ], style={"margin-bottom": "20px"}),

    # Botões para adicionar e remover membros
    dbc.Row([
        dbc.Button("Add", color="primary", className="mr-2"),
        dbc.Button("Clear", color="secondary", outline=True, className="ml-2"),
    ], style={"margin-bottom": "20px"}),

    # Tabela de membros adicionados
    html.Hr(),
    dbc.Table(
        children=[
            html.Thead(html.Tr([html.Th("First Name"), html.Th("Last Name"), html.Th("E-Mail"),
                                html.Th("ORCID"), html.Th("Organization"), html.Th("Department"), html.Th("Role")])),
            html.Tbody(id="member-table-body")
        ],
        bordered=True,
        style={"margin-bottom": "20px"}
    ),

    # Export Section
    html.Hr(),
    html.H3("Export", style={"margin-top": "20px"}),
    dbc.Row([
        dbc.Col([
            dbc.Label("Select a package"),
            dbc.Input(type="text", placeholder="Filter")
        ], width=4),
        dbc.Col([
            dbc.Button("Generate Workbook", color="primary", className="mr-2")
        ], width="auto"),
    ])
])

# Layout principal da aplicação
app.layout = html.Div([
    form_page
])

# Executa a aplicação
if __name__ == "__main__":
    app.run_server(debug=True)
