import dash
from dash import html, dash_table, dcc, callback, Output, Input, State
from dash.exceptions import PreventUpdate
import pandas as pd
import TMonWidgets
from TMonWidgets.MultiSelector import searchValueFromMultiSelector
from vis import xAPISGPlayersProgress
from urllib.parse import unquote

def get_value_from_url(url, valueId, urlValuesDelimiter='&'):
    decoded_string = unquote(url)
    values=decoded_string.split(urlValuesDelimiter)
    print(f"{url} - {values}")
    for val in values:
        index=val.find(valueId)
        if index != -1:
            return val[index+len(valueId):]
    return url

homepagecontent=[
   html.H2('T-Mon Home Page.'),
   html.H3('Please select another tab to see default visualisations with this data.')
]

@callback(
    [
        Output('t-mon-tabs', 'value'),
        Output("users-multi-dynamic-dropdown", "value"),
    ],
    Input('output-t-mon', 'style'), 
    State('url-t-mon', 'pathname')
)
def update_tab(style, stateUrl):
    if style == {"display":"block"} : 
        print(f"StateUrl: {stateUrl}")
        new_tab=None
        new_users=None
        urlValues=None
        dashboard_data=False
        index = stateUrl.find("/dashboard/")
        # Slice the string up to the index if "/dashboard/" is found
        if index != -1:
            urlValues = stateUrl[index + len("/dashboard/"):]
            dashboard_data=True
        if dashboard_data and urlValues:
            new_tab=get_value_from_url(urlValues, "tab=")
            users=get_value_from_url(urlValues, "actor.name=")
            new_users=users.split(",")
        else:
            new_tab="home_tab"
            new_users=[]
        if new_tab != "":
            tab=new_tab
        else:
            tab="home_tab"
        if new_users:
            user_value=new_users
        else:
            user_value=[]
        print(f"Tab: {tab} - URL : {urlValues} - user_value : {user_value}")
        return tab, user_value
    else:
        raise PreventUpdate

@callback(
    [
        Output('url-t-mon', 'pathname'),        
        Output("users-multi-dynamic-dropdown", "options"),
        Output('tabs-content', 'children'),
     ],
    Input('t-mon-tabs', 'value'),
    Input("users-multi-dynamic-dropdown", "search_value"),
    Input("users-multi-dynamic-dropdown", "value"),
)
def update_output(tab, user_search_value, user_value):
    ctx = dash.callback_context
    triggered=ctx.triggered
    triggered_prop_id = ctx.triggered[0]['prop_id']
    res=f"Triggered : {triggered} - {triggered_prop_id}"
    print(res)
    # Normalize the JSON data to a pandas DataFrame
    if 'users-multi-dynamic-dropdown' in triggered_prop_id or 't-mon-tabs' in triggered_prop_id:
        if len(TMonWidgets.xapiData) > 0:
            df = pd.json_normalize(TMonWidgets.xapiData)
            filtered_df, user_unique_options=searchValueFromMultiSelector(df, "actor.name", user_search_value, user_value)
            if tab == 'home_tab':
                tab_content = html.Div(html.Div(homepagecontent))
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
            url=f"tab={tab}"
            if user_value and len(user_value)>0:
                url=f"{url}&actor.name={",".join(user_value)}"
            print(f"url:{url}")
            return f"{url}", user_unique_options, tab_content
        else:
            url=f"tab=home_tab"
            return f"{url}",[], html.Div(homepagecontent)
    else:
        raise PreventUpdate
    
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
            dcc.Tabs(id="t-mon-tabs", value="home_tab", children=[
                dcc.Tab(label='HomePage', value='home_tab'),
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
