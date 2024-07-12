from dash import Dash, html, dash_table, dcc, callback, Output, Input, State, dash_table
from dash.exceptions import PreventUpdate
import plotly.subplots as subplots
import fileBrowserAndUploadButtonToLoadProcessStatements
import datetime

global players_info, names
# Initialize the app
app = Dash(__name__)

# App layout
app.layout = html.Div([
    html.H1(children='T-Mon'),
    html.Hr(),
    html.H2(children='Select JSON xAPI-SG file to process and see visualisations'),
    dcc.Upload(
        id='upload-data',
        children=html.Div([
            'Drag and Drop or ',
            html.A('Select Files')
        ]),
        style={
            'width': '100%',
            'height': '60px',
            'lineHeight': '60px',
            'borderWidth': '1px',
            'borderStyle': 'dashed',
            'borderRadius': '5px',
            'textAlign': 'center',
            'margin': '10px'
        },
        # Allow multiple files to be uploaded
        multiple=True
    ),
    html.Div(id='output-data-upload'),
    dcc.Store(id='progress-store', data={'count': 0, 'total': 0, 'in_progress': False}),
    html.Hr(),
    dcc.Dropdown(id='users-multi-dynamic-dropdown', multi=True),
    dcc.Tabs(id="t-mon-tabs", value='t-mon-tabs', children=[
        dcc.Tab(label='Progress', value='progress_tab'),
        dcc.Tab(label='Videos', value='video_tab'),
        dcc.Tab(label='Completable', value='completable_tab'),
        dcc.Tab(label='Alternatives', value='alternative_tab'),
        dcc.Tab(label='Interactions', value='interaction_tab'),
        dcc.Tab(label='Accessible', value='accessible_tab'),
        dcc.Tab(label='Menu', value='menu_tab'),
    ]),
    html.Div(id='tabs-content'),
    html.H4(children='T-MON, by eUCM research team')
])

players_info={}
@callback(Output('output-data-upload', 'children'),
              Input('upload-data', 'contents'),
              State('upload-data', 'filename'),
              State('upload-data', 'last_modified'))
def update_output(list_of_contents, list_of_names, list_of_dates):
    if list_of_contents is not None:
        players_info={}
        div_list= []
        for c, n, d in zip(list_of_contents, list_of_names, list_of_dates):
            out, err = [], []
            div_list.append(html.Div([
                html.H5(n),
                html.H6(datetime.datetime.fromtimestamp(d)),
            ]))
            try:
                fileBrowserAndUploadButtonToLoadProcessStatements.load_players_info_from_content(c, n, players_info, out, err)
                div_list.append(html.Div([
                    html.Div(out),
                    html.Div(err),
                    html.Hr() # horizontal line
                    # For debugging, display the raw contents provided by the web browser
                    #html.Div('Raw Content'),
                    #html.Pre(content_string[0:200], style={
                    #    'whiteSpace': 'pre-wrap',
                    #    'wordBreak': 'break-all'
                    #})
                ]))
            except Exception as e:
                print(e)
                div_list.append(html.Div(
                    html.Div([
                        'There was an error processing this file.'
                    ]),
                    html.Div(out),
                    html.Div(err)
                ))

        return html.Div(div_list)

#@callback(
#    Output("my-dynamic-dropdown", "options"),
#    Input("my-dynamic-dropdown", "search_value")
#)
#def update_options(search_value):
#    if not search_value:
#        raise PreventUpdate
#    return [o for o in list(players_info.keys()) if search_value in o["label"]]

@callback(
    Output("users-multi-dynamic-dropdown", "options"),
    Input("users-multi-dynamic-dropdown", "search_value"),
    State("users-multi-dynamic-dropdown", "value")
)
def update_multi_options(search_value, value):
    if not search_value:
        raise PreventUpdate
    # Make sure that the set values are in the option list, else they will disappear
    # from the shown select list, but still part of the `value`.
    # Convert the dictionary keys to the appropriate format for dropdown options
    all_options = [{'label': k, 'value': k} for k in players_info.keys()]

    # Filter options based on the search value
    filtered_options = [o for o in all_options if search_value.lower() in o['label'].lower()]

    # Ensure selected values remain in the options list
    if value:
        selected_options = [o for o in all_options if o['value'] in value]
        filtered_options = selected_options + filtered_options

    # Remove duplicates while preserving order
    unique_options = list({v['value']:v for v in filtered_options}.values())

    return unique_options

@callback(Output('tabs-content', 'children'),
              Input('t-mon-tabs', 'value'))
def render_content(tab):
    if tab == 'progress_tab':
        return html.Div([
            html.H3('Tab content 1'),
            dcc.Graph(
                figure={
                    'data': [{
                        'x': [1, 2, 3],
                        'y': [3, 1, 2],
                        'type': 'bar'
                    }]
                }
            )
        ])
    elif tab == 'video_tab':
        return html.Div([
            html.H3('Tab content 2'),
            dcc.Graph(
                id='graph-2-tabs-dcc',
                figure={
                    'data': [{
                        'x': [1, 2, 3],
                        'y': [5, 10, 6],
                        'type': 'bar'
                    }]
                }
            )
        ])
    elif tab == 'completable_tab':
        return html.Div([
            html.H3('Tab content 3'),
            dcc.Graph(
                id='graph-2-tabs-dcc',
                figure={
                    'data': [{
                        'x': [1, 2, 3],
                        'y': [5, 10, 6],
                        'type': 'bar'
                    }]
                }
            )
        ])
    elif tab == 'alternative_tab':
        return html.Div([
            html.H3('Tab content 4'),
            dcc.Graph(
                id='graph-2-tabs-dcc',
                figure={
                    'data': [{
                        'x': [1, 2, 3],
                        'y': [5, 10, 6],
                        'type': 'bar'
                    }]
                }
            )
        ])
    elif tab == 'interaction_tab':
        return html.Div([
            html.H3('Tab content 5'),
            dcc.Graph(
                id='graph-2-tabs-dcc',
                figure={
                    'data': [{
                        'x': [1, 2, 3],
                        'y': [5, 10, 6],
                        'type': 'bar'
                    }]
                }
            )
        ])
    elif tab == 'accessible_tab':
        return html.Div([
            html.H3('Tab content 6'),
            dcc.Graph(
                id='graph-2-tabs-dcc',
                figure={
                    'data': [{
                        'x': [1, 2, 3],
                        'y': [5, 10, 6],
                        'type': 'bar'
                    }]
                }
            )
        ])
    elif tab == 'menu_tab':
        return html.Div([
            html.H3('Tab content 7'),
            dcc.Graph(
                id='graph-2-tabs-dcc',
                figure={
                    'data': [{
                        'x': [1, 2, 3],
                        'y': [5, 10, 6],
                        'type': 'bar'
                    }]
                }
            )
        ])


if __name__ == '__main__':
    app.run(debug=True, port="8051")