from dash import dcc, html, dash_table
import dash_bootstrap_components as dbc

# Example MAG metadata
mag_metadata = [
    {
        "MAG_ID": "MAG_001",
        "Collection Date": "2023-03-15",
        "Collected By": "Institute A",
        "Geo Location": "USA: California, Los Angeles",
        "Latitude": "34.052235",
        "Longitude": "-118.243683",
        "Depth (m)": "10",
        "Environment": "Marine biome",
        "Actions": "[Edit](#) | [Delete](#)",
    },
    {
        "MAG_ID": "MAG_002",
        "Collection Date": "2022-11-02",
        "Collected By": "Institute B",
        "Geo Location": "Australia: Queensland, Brisbane",
        "Latitude": "-27.470125",
        "Longitude": "153.021072",
        "Depth (m)": "50",
        "Environment": "Aquatic biome",
        "Actions": "[Edit](#) | [Delete](#)",
    },
    {
        "MAG_ID": "MAG_003",
        "Collection Date": "2021-06-25",
        "Collected By": "Institute C",
        "Geo Location": "Brazil: São Paulo, São Paulo",
        "Latitude": "-23.550520",
        "Longitude": "-46.633308",
        "Depth (m)": "0.5",
        "Environment": "Terrestrial biome",
        "Actions": "[Edit](#) | [Delete](#)",
    },
    {
        "MAG_ID": "MAG_004",
        "Collection Date": "2020-01-18",
        "Collected By": "Institute D",
        "Geo Location": "India: Maharashtra, Mumbai",
        "Latitude": "19.076090",
        "Longitude": "72.877426",
        "Depth (m)": "1.2",
        "Environment": "Urban biome",
        "Actions": "[Edit](#) | [Delete](#)",
    },
    {
        "MAG_ID": "MAG_005",
        "Collection Date": "2021-09-13",
        "Collected By": "Institute E",
        "Geo Location": "Germany: Bavaria, Munich",
        "Latitude": "48.135125",
        "Longitude": "11.581981",
        "Depth (m)": "3",
        "Environment": "Forest biome",
        "Actions": "[Edit](#) | [Delete](#)",
    },
    {
        "MAG_ID": "MAG_006",
        "Collection Date": "2022-05-10",
        "Collected By": "Institute F",
        "Geo Location": "China: Beijing, Beijing",
        "Latitude": "39.904202",
        "Longitude": "116.407394",
        "Depth (m)": "2.5",
        "Environment": "Agricultural biome",
        "Actions": "[Edit](#) | [Delete](#)",
    },
    {
        "MAG_ID": "MAG_007",
        "Collection Date": "2023-08-05",
        "Collected By": "Institute G",
        "Geo Location": "South Africa: Gauteng, Johannesburg",
        "Latitude": "-26.204103",
        "Longitude": "28.047304",
        "Depth (m)": "20",
        "Environment": "Grassland biome",
        "Actions": "[Edit](#) | [Delete](#)",
    },
    {
        "MAG_ID": "MAG_008",
        "Collection Date": "2020-12-22",
        "Collected By": "Institute H",
        "Geo Location": "Canada: Ontario, Toronto",
        "Latitude": "43.651070",
        "Longitude": "-79.347015",
        "Depth (m)": "15",
        "Environment": "Freshwater biome",
        "Actions": "[Edit](#) | [Delete](#)",
    },
]

# Page layout with buttons and metadata table
upload_page = html.Div(
    style={"backgroundColor": "#f7f7f7", "padding": "20px"},
    children=[
        # Header with dropdown menu
        html.Div(
            children=[
                html.H2("ENA Submission", style={"color": "#ffffff", "paddingLeft": "10px"}),
                dbc.DropdownMenu(
                    label="Metadata Type",
                    children=[
                        dbc.DropdownMenuItem("Terrestrial", id="terrestrial"),
                        dbc.DropdownMenuItem("Animal Associated", id="animal_associated"),
                        dbc.DropdownMenuItem("Marine", id="marine"),
                        dbc.DropdownMenuItem("Human", id="human"),
                        dbc.DropdownMenuItem("Plant", id="plant"),
                    ],
                    style={"marginLeft": "auto"},
                ),
            ],
            style={
                "backgroundColor": "#343a40",
                "padding": "10px",
                "borderRadius": "5px",
                "display": "flex",
                "alignItems": "center",
                "justifyContent": "space-between",
            },
        ),
        # Upload file button
        html.Div(
            [
                dbc.Button("Upload File...", color="primary", className="mr-2"),
                html.Span(
                    "Upload a project RDF file in .ttl format",
                    style={"paddingLeft": "10px", "color": "#6c757d"},
                ),
            ],
            style={"padding": "20px"},
        ),
        # Metadata table
        html.Div(
            children=[
                html.H3("MAG Metadata Table", style={"marginTop": "20px", "color": "#343a40"}),
                dash_table.DataTable(
                    id="mag-metadata-table",
                    columns=[
                        {"name": "MAG_ID", "id": "MAG_ID"},
                        {"name": "Collection Date", "id": "Collection Date"},
                        {"name": "Collected By", "id": "Collected By"},
                        {"name": "Geo Location", "id": "Geo Location"},
                        {"name": "Latitude", "id": "Latitude"},
                        {"name": "Longitude", "id": "Longitude"},
                        {"name": "Depth (m)", "id": "Depth (m)"},
                        {"name": "Environment", "id": "Environment"},
                        {"name": "Actions", "id": "Actions", "presentation": "markdown"},
                    ],
                    data=mag_metadata,
                    style_table={"marginTop": "20px", "overflowX": "auto"},
                    style_cell={
                        "textAlign": "center",
                        "padding": "10px",
                        "whiteSpace": "normal",
                        "height": "auto",
                        "border": "1px solid #ddd",
                    },
                    style_header={
                        "backgroundColor": "#343a40",
                        "color": "white",
                        "fontWeight": "bold",
                        "border": "1px solid #ddd",
                    },
                    style_data={
                        "backgroundColor": "#f7f7f7",
                        "color": "#212529",
                        "border": "1px solid #ddd",
                    },
                ),
            ],
        ),
        # Buttons
        html.Div(
            children=[
                dbc.Button("Confirm", color="success", className="me-2"),
                dbc.Button("Save Metadata", color="info", className="me-2"),
                dbc.Button("Submit to ENA", color="primary"),
            ],
            style={"marginTop": "20px", "display": "flex", "justifyContent": "center"},
        ),
    ],
)
