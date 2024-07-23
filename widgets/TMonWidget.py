from dash import html, dash_table, dcc, callback, Output, Input
from dash.exceptions import PreventUpdate
import pandas as pd

@callback(
    [Output("users-multi-dynamic-dropdown", "options"),
     Output('tabs-content', 'children')],
    Input("users-multi-dynamic-dropdown", "search_value"),
    Input('t-mon-tabs', 'value'),
    Input("users-multi-dynamic-dropdown", "value"),
)
def update_output(search_value, tab, value):
    if not search_value and not tab:
        raise PreventUpdate
    # Normalize the JSON data to a pandas DataFrame
    if len(xapiData) > 0:
        df = pd.json_normalize(xapiData)
        filtered_df=df
        # Make sure that the set values are in the option list, else they will disappear
        # from the shown select list, but still part of the `value`.
        # Convert the dictionary keys to the appropriate format for dropdown options
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
            filtered_df = df.loc[df['actor.name'].isin(value)]
        #else:
        #    filtered_df=df
        # Remove duplicates while preserving order
        unique_options = list({v['value']:v for v in filtered_options}.values())
        if tab == 'progress_tab':
            from vis import xAPISGPlayersProgress
            content=[]
            content.append(html.H3('Player Progress Throw Serious game'))
            seriousgamesId=df.loc[df["object.definition.type"]=="https://w3id.org/xapi/seriousgames/activity-types/serious-game"]['object.id'].unique()
            for game in seriousgamesId:
                fig=xAPISGPlayersProgress.displayPlayerProgressFig(
                    bar_game_data=xAPISGPlayersProgress.ProgressPlayerLineChart(filtered_df, game),
                    game=game
                )
                content.append(dcc.Graph(id=f"barchart-{game}",figure=fig))
                fig=xAPISGPlayersProgress.displayPlayerProgressInitFig(
                    bar_game_data=xAPISGPlayersProgress.ProgressPlayerLineChart(filtered_df, game),
                    game=game
                )
                content.append(dcc.Graph(id=f"barchart-init-{game}",figure=fig))
                fig=xAPISGPlayersProgress.displayPlayerProgressPieFig(
                    pie_chart_data=xAPISGPlayersProgress.ProgressPlayerPie(filtered_df, game)
                )
                content.append(dcc.Graph(id=f"pie-{game}",figure=fig))
            tab_content = html.Div(html.Div(content))
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
            data = filtered_df.to_dict('records')
            tab_content= html.Div([
                html.H3("Length table : " + str(len(data))),
                dash_table.DataTable(
                    id='table-all-xapi-data',
                    columns=[{"name": i, "id": i} for i in filtered_df.columns],
                    data=data
                )
            ])

        return unique_options, tab_content
    else: 
        return [], html.Div()
    
TMonHeader=html.Div([
    html.H1(children='T-Mon'),
    html.Hr(),
    html.H2(children='Select JSON xAPI-SG file to process and see visualizations'),
])

TMonBody=html.Div([
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
    ])
])
TMonFooter=html.Div([
    html.Hr(),
    html.H4(children='T-MON, by eUCM research team')
])
