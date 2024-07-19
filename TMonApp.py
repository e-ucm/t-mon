from dash import Dash, html, dash_table, dcc, callback, Output, Input, State
from dash.exceptions import PreventUpdate
import plotly.subplots as subplots
import fileBrowserAndUploadButtonToLoadProcessStatements
import datetime
import pandas as pd
global players_info, xapiData
players_info = {}
xapiData = []

# Initialize the app
TMonApp = Dash(__name__)

# App layout
TMonApp.layout = html.Div([
    html.H1(children='T-Mon'),
    html.Hr(),
    html.H2(children='Select JSON xAPI-SG file to process and see visualizations'),
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
    html.Div(id='output-treatment'),
    html.Div(id='output-t-mon', style={'display': 'none'}, children=[
        dcc.Dropdown(id='users-multi-dynamic-dropdown', multi=True),
        html.Div(
            dcc.Tabs(id="t-mon-tabs", children=[
                dcc.Tab(label='Progress', value='progress_tab'),
                dcc.Tab(label='Videos', value='video_tab'),
                dcc.Tab(label='Completable', value='completable_tab'),
                dcc.Tab(label='Alternatives', value='alternative_tab'),
                dcc.Tab(label='Interactions', value='interaction_tab'),
                dcc.Tab(label='Accessible', value='accessible_tab'),
                dcc.Tab(label='Menu', value='menu_tab'),
                dcc.Tab(label='xAPI Data', value='data_tab')
            ])
        ),
        html.Div(id="tabs-content")
    ]),
    html.Hr(),
    html.H4(children='T-MON, by eUCM research team')
])

@callback(
    [Output('output-treatment', 'children'), 
     Output('output-t-mon', 'style')],
    Input('upload-data', 'contents'),
    State('upload-data', 'filename'),
    State('upload-data', 'last_modified')
)
def update_output(list_of_contents, list_of_names, list_of_dates):
    if list_of_contents is None:
        raise PreventUpdate
    else:
        div_list = []
        global players_info, xapiData
        players_info = {}
        xapiData = []
        nbError=0
        style={'display': 'block'}
        for c, n, d in zip(list_of_contents, list_of_names, list_of_dates):
            out, err = [], []
            div_list.append(html.H5(n))
            div_list.append(html.H6(datetime.datetime.fromtimestamp(d)))
            fileBrowserAndUploadButtonToLoadProcessStatements.load_players_info_from_content(c, n, players_info, xapiData, out, err)
            div_list.append(html.Div(out))
            div_list.append(html.Div(err))
            if len(err) > 0 : 
                nbError+=1
            div_list.append(html.Hr())
        if nbError == len(list_of_names):
            style={'display': 'none'}
        return div_list, style

@callback(
    [Output("users-multi-dynamic-dropdown", "options"),
     Output('tabs-content', 'children')],
    Input("users-multi-dynamic-dropdown", "search_value"),
    Input('t-mon-tabs', 'value'),
    State("users-multi-dynamic-dropdown", "value"),
)
def update_output(search_value, tab, value):
    if not search_value and not tab:
        raise PreventUpdate
    # Normalize the JSON data to a pandas DataFrame
    if len(xapiData) > 0: 
        df = pd.json_normalize(xapiData)
        # Make sure that the set values are in the option list, else they will disappear
        # from the shown select list, but still part of the `value`.
        # Convert the dictionary keys to the appropriate format for dropdown options
        #all_options = [{'label': k, 'value': k} for k in players_info.keys()]
        all_options = [{'label': k, 'value': k} for k in df['actor.name'].unique()]
        # Filter options based on the search value
        if search_value is not None:
            filtered_options = [o for o in all_options if search_value.lower() in o['label'].lower()]
        else:
            filtered_options = all_options
        # Ensure selected values remain in the options list
        if value:
            selected_options = [o for o in all_options if o['value'] in value]
            filtered_options = selected_options + filtered_options
            df = df.loc[df['actor.name'].isin(value)]
        # Remove duplicates while preserving order
        unique_options = list({v['value']:v for v in filtered_options}.values())
        if tab == 'progress_tab':
            tab_content = html.Div([
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
            tab_content= html.Div([
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
            tab_content= html.Div([
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
            tab_content= html.Div([
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
            tab_content= html.Div([
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
            tab_content= html.Div([
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
            tab_content= html.Div([
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
        elif tab == 'data_tab':
        #else:
            # Convert the DataFrame to a dictionary suitable for DataTable
            data = df.to_dict('records')
            tab_content= html.Div([
                html.H3("Length table : " + str(len(xapiData))),
                dash_table.DataTable(
                    #id='table',
                    columns=[{"name": i, "id": i} for i in df.columns],
                    data=data
                )
            ])

        return unique_options, tab_content
    else: 
        return [], html.Div()

if __name__ == '__main__':
    TMonApp.run(debug=True, port="5001")