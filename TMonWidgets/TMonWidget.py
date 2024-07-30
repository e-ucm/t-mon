from dash import html, dash_table, dcc, callback, Output, Input, State
from dash.exceptions import PreventUpdate
import pandas as pd
import TMonWidgets
from TMonWidgets.MultiSelector import searchValueFromMultiSelector
from vis import xAPISGPlayersProgress

@callback(
    [Output("users-multi-dynamic-dropdown", "options"),
     Output('tabs-content', 'children'),
     Output('url-t-mon', 'pathname')],
    Input('t-mon-tabs', 'value'),
    Input("users-multi-dynamic-dropdown", "search_value"),
    Input("users-multi-dynamic-dropdown", "value"),
    State('url-t-mon', 'pathname')
)
def update_output(tab, user_search_value, user_value, stateUrl):
    # Find the position of "/dashboard/"
    index = stateUrl.find("/dashboard/")
    # Slice the string up to the index if "/dashboard/" is found
    if index != -1:
        newStateUrl = stateUrl[index:]
    else:
        newStateUrl = stateUrl
    print(f"Path : {stateUrl} - {newStateUrl}")
    if not user_search_value and not tab:
        raise PreventUpdate
    # Normalize the JSON data to a pandas DataFrame
    if len(TMonWidgets.xapiData) > 0:
        df = pd.json_normalize(TMonWidgets.xapiData)
        filtered_df, user_unique_options=searchValueFromMultiSelector(df, "actor.name", user_search_value, user_value)
        if tab == 'home':
           content=[
               html.H2('T-Mon Home Page.'),
               html.H3('Please select another tab to see default visualisations with this data.')
           ]
           tab_content = html.Div(html.Div(content))
        elif tab == 'progress_tab':
            content=[]
            content.append(html.H3('Player Progress Throw Serious game'))
            seriousgamesId=df.loc[df["object.definition.type"]=="https://w3id.org/xapi/seriousgames/activity-types/serious-game"]['object.id'].unique()
            for game in seriousgamesId:
                bargamedata=xAPISGPlayersProgress.ProgressPlayerLineChart(filtered_df, game)
                fig=xAPISGPlayersProgress.displayPlayerProgressFig(
                    bar_game_data=bargamedata,
                    game=game
                )
                content.append(dcc.Graph(id=f"barchart-{game}",figure=fig))
                fig=xAPISGPlayersProgress.displayPlayerProgressInitFig(
                    bar_game_data=bargamedata,
                    game=game
                )
                content.append(dcc.Graph(id=f"barchart-init-{game}",figure=fig))
                fig=xAPISGPlayersProgress.displayPlayerProgressPieFig(
                    pie_chart_data=xAPISGPlayersProgress.ProgressPlayerPie(filtered_df, game),
                    game=game
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
            # Convert the DataFrame to a dictionary suitable for DataTable
            data = filtered_df.to_dict('records')
            tab_content= html.Div([
                html.H3("Length table : " + str(len(data))),
                dash_table.DataTable(
                    id='table-all-xapi-data',
                    columns=[{"name": i, "id": i} for i in filtered_df.columns],
                    data=data,
                    filter_action='native',
                    sort_action="native",
                    sort_mode="multi",
                    #sort_by=[{'column_id': 'timestamp', 'direction': 'asc'}],
                )
            ])
        else:
            tab_content = html.Div()
        return user_unique_options, tab_content, f"{tab}"
    else:
        return [], html.Div(), ""
    
TMonHeader=html.Div([
    html.H1(children='T-Mon'),
    html.Hr(),
    html.H2(children='Select JSON xAPI-SG file to process and see visualizations'),
])

TMonBody=html.Div([
    dcc.Location(id='url-t-mon', refresh=False), # Location component for URL handling
    html.Div(id='output-t-mon', style={'display': 'none'}, children=[
        dcc.Dropdown(id='users-multi-dynamic-dropdown', multi=True),
        html.Div(
            dcc.Tabs(id="t-mon-tabs", value="home", children=[
                dcc.Tab(label='HomePage', value='home'),
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
