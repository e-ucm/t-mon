import dash
from dash import html, dash_table, dcc, callback, Output, Input, State
from dash.exceptions import PreventUpdate
import pandas as pd
import json
import TMonWidgets
from LoadProcessStatements import resolve_actor_name_column, flatten_for_display
from TMonWidgets.ActivityFilter import filter_df_by_activities, statements_activity_ids
from TMonWidgets.MultiSelector import searchValueFromMultiSelector
from vis import xAPISGPlayersProgress, xAPISGVideosSeenSkipped
from urllib.parse import unquote, urlencode

# Query parameter carrying the activities left out of the view. The name is deliberately
# not `activity`: get_value_from_url matches substrings, so `activity=` would also be
# found inside `hidden-activity=` and would read back the wrong value.
HIDDEN_ACTIVITIES_PARAM = "hidden-activity"

# A button row only earns its place when there is a choice to make, which needs at least
# two activities: a selection that is a single activity, and a data set that names none,
# are both views the user cannot narrow.
MIN_ACTIVITIES_TO_CHOOSE = 2

def get_value_from_url(url, valueId, urlValuesDelimiter='&'):
    decoded_string = unquote(url).replace('+', ' ')
    values=decoded_string.split(urlValuesDelimiter)
    print(f"{url} - {values}")
    for val in values:
        index=val.find(valueId)
        if index != -1:
            return val[index+len(valueId):]
    return None

homepagecontent=[
   html.H2('T-Mon Home Page.'),
   html.H3('Please select another tab to see default visualisations with this data.')
]

@callback(
    [
        Output('t-mon-tabs', 'value'),
        Output("users-multi-dynamic-dropdown", "value"),
        Output("object-multi-dynamic-dropdown", "value")
    ],
    Input('output-t-mon', 'style'), 
    State('url-t-mon', 'pathname')
)
def update_tab(style, stateUrl):
    if style == {"display":"block"} : 
        print(f"StateUrl: {stateUrl}")
        new_tab=None
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
            object=get_value_from_url(urlValues, "object.id=")
        else:
            new_tab="home_tab"
            users=None
            object=None
        tab=new_tab
        user_value=users.split(",") if users else []
        object_value=object.split(",") if object else []
        print(f"Tab: {tab} - URL : {urlValues} - user_value : {user_value} - object_value: {object_value}")
        return tab, user_value, object_value
    else:
        raise PreventUpdate


def activity_name_of(activity_id):
    """
    Return the label of an activity, its SimVA name when the selection named it.

    Args:
        activity_id (str): The id of the activity.

    Returns:
        str: The name published for that id, or the id itself when there is none, which
            is the case for anything that does not come from a SimVA session.
    """
    for activity in getattr(TMonWidgets, "sessionActivities", []) or []:
        if activity.get("id") == str(activity_id):
            return activity.get("name") or str(activity_id)
    return str(activity_id)


def hidden_activities_from_url(pathname):
    """
    Read the activities a link leaves out of the view.

    Args:
        pathname (str): The dashboard URL, query parameters included.

    Returns:
        list: The activity ids named by the URL, empty when it names none.
    """
    found = get_value_from_url(pathname or "", f"{HIDDEN_ACTIVITIES_PARAM}=")
    return [value for value in found.split(",") if value] if found else []


@callback(
    [
        Output('activity-filter-hidden', 'data'),
        Output('activity-filter-div', 'children'),
        Output('activity-filter-controls', 'style'),
        Output('activity-filter-info', 'children'),
    ],
    [
        Input({'type': 'activity-button', 'index': dash.dependencies.ALL}, 'n_clicks'),
        Input('activity-filter-all', 'n_clicks'),
        Input('activity-filter-none', 'n_clicks'),
        # Bumped by the poller when statements arrive, so an activity that produces its
        # first ones joins the row instead of being filtered out of a view it is not in.
        Input("lrs-data-version", "data"),
        # The URL is what a shared link carries, so a reload or a pasted link shows the
        # same activities. Written by the same callback chain that hides the buttons, so
        # the two settle on the same value instead of driving each other.
        Input('url-t-mon', 'pathname'),
    ],
    [
        State('activity-filter-hidden', 'data'),
    ]
)
def update_activity_filter(button_n_clicks, all_n_clicks, none_n_clicks, lrs_data_version, pathname, hidden):
    """
    Keep the activity buttons and the list of hidden activities in step.

    The store holds the activities that are *out* of the view rather than the ones in it,
    which is what makes a stale value harmless: the ids of another session are simply not
    in the data, so they hide nothing, and an activity that appears later is on until it
    is clicked.

    The buttons are built from the statements currently loaded, so the row always offers
    exactly the activities there is something to choose between.
    """
    triggered = dash.callback_context.triggered
    triggered_prop_id = triggered[0]['prop_id'] if triggered else ''
    known = statements_activity_ids(TMonWidgets.xapiData)
    hidden = [str(value) for value in (hidden or [])]
    print(f"Activities : known={known} - hidden={hidden} - triggered={triggered_prop_id}")
    if 'url-t-mon' in triggered_prop_id:
        # Adopt what the link says. The URL is written from this same store, so the two
        # always name the same view, whichever of the two is read first.
        hidden = hidden_activities_from_url(pathname)
    elif 'activity-filter-all' in triggered_prop_id:
        hidden = []
    elif 'activity-filter-none' in triggered_prop_id:
        hidden = list(known)
    elif 'activity-button' in triggered_prop_id:
        activity_id = str(json.loads(triggered_prop_id.rsplit('.n_clicks', 1)[0])['index'])
        # Toggling works on the activities that are in the view, since that is what the
        # user sees: the button they pressed leaves the view, and the hidden ones are
        # whatever is left out of it. Written back in the order of the statements, which
        # is the order the buttons are drawn in, so the store and the row never disagree.
        visible = [known_id for known_id in known if known_id not in hidden]
        if activity_id in visible:
            # The activity leaves the view, and the ones that stayed keep their place.
            visible = [known_id for known_id in visible if known_id != activity_id]
        else:
            # The activity comes back, listed where the statements put it.
            visible = [known_id for known_id in known
                       if known_id == activity_id or known_id in visible]
        hidden = [known_id for known_id in known if known_id not in visible]
    # Whatever the trigger, an id that names no activity of the data left behind is
    # dropped: those are what a link to another session carries, they hide nothing, and
    # keeping them would only put ids of another study in the next link written out.
    hidden = [known_id for known_id in known if known_id in hidden]
    if len(known) < MIN_ACTIVITIES_TO_CHOOSE:
        # Nothing to choose between: a single activity, a selection that is an activity
        # itself, or a data set that names none. No row, and no state either, so such a
        # selection is never held to a filter that does not apply to it.
        return [], [], {'display': 'none'}, ''
    shown = [known_id for known_id in known if known_id not in hidden]
    buttons = [
        html.Button(
            f"{activity_name_of(known_id)} ({known_id})",
            id={'type': 'activity-button', 'index': known_id},
            n_clicks=0,
            # The same green the file buttons use, so "in the view" looks the same
            # everywhere in the browser panel.
            style={'backgroundColor': 'lightgray' if known_id in hidden else 'green'},
        )
        for known_id in known
    ]
    return (
        hidden,
        buttons,
        {'display': 'block'},
        f"{len(shown)} of {len(known)} activities shown",
    )


def filterObjectIdDependingTab(df, value, tab):
    if tab == "progress_tab":
        vals=df.loc[df["object.definition.type"]=="https://w3id.org/xapi/seriousgames/activity-types/serious-game"]["object.id"].unique()
    elif tab == "video_tab":
        vals=df.loc[df["object.definition.type"]=="https://w3id.org/xapi/seriousgames/activity-types/Cutscene"]["object.id"].unique()
    elif tab == "completable_tab":
        vals=df.loc[df["object.definition.type"]=="https://w3id.org/xapi/seriousgames/activity-types/level"]["object.id"].unique()
    elif tab == "alternative_tab":
        vals=df.loc[df["object.definition.type"]=="https://w3id.org/xapi/seriousgames/activity-types/Alternative"]["object.id"].unique()
    elif tab == "interaction_tab":
        vals=df.loc[df["object.definition.type"]=="https://w3id.org/xapi/seriousgames/activity-types/Screen"]["object.id"].unique()
    elif tab == "accessible_tab":
        vals=df.loc[df["object.definition.type"]=="https://w3id.org/xapi/seriousgames/activity-types/Screen"]["object.id"].unique()
    elif tab == "menu_tab":
        vals=df.loc[df["object.definition.type"]=="https://w3id.org/xapi/seriousgames/activity-types/Screen"]["object.id"].unique()
    else:
        vals=value
    return vals

@callback(
    [
        Output('url-t-mon', 'pathname'),        
        Output("users-multi-dynamic-dropdown", "options"),
        Output('object-multi-dynamic-dropdown', "options"),
        Output('tabs-content', 'children'),
     ],
    Input('t-mon-tabs', 'value'),
    Input("users-multi-dynamic-dropdown", "search_value"),
    Input("users-multi-dynamic-dropdown", "value"),
    Input("object-multi-dynamic-dropdown", "search_value"),
    Input("object-multi-dynamic-dropdown", "value"),
    # Bumped by the poller only when new statements arrived, so a tick with no new
    # data leaves this untouched and nothing is redrawn.
    Input("lrs-data-version", "data"),
    # The activities left out of the view, so clicking one of the buttons redraws
    # whatever tab is open with the statements of the remaining activities.
    Input("activity-filter-hidden", "data"),
)
def update_output(tab, user_search_value, user_value, object_search_value, object_value, lrs_data_version=None, hidden_activities=None):
    ctx = dash.callback_context
    triggered=ctx.triggered
    triggered_prop_id = ctx.triggered[0]['prop_id']
    res=f"Triggered : {triggered} - {triggered_prop_id}"
    print(res)
    # Normalize the JSON data to a pandas DataFrame
    if ('object-multi-dynamic-dropdown' in triggered_prop_id or 'users-multi-dynamic-dropdown' in triggered_prop_id
            or 't-mon-tabs' in triggered_prop_id or 'lrs-data-version' in triggered_prop_id
            or 'activity-filter-hidden' in triggered_prop_id):
        if len(TMonWidgets.xapiData) > 0:
            df = pd.json_normalize(TMonWidgets.xapiData)
            df = resolve_actor_name_column(df)
            # Narrow the data to the activities that are on before anything reads it, so
            # the charts, the table and the choice lists of the dropdowns all describe
            # the same view instead of the whole session.
            df, activity_ids = filter_df_by_activities(df, hidden_activities)
            filtered_df, user_unique_options=searchValueFromMultiSelector(df, "actor.name", user_search_value, user_value)
            filtered_df, object_unique_options=searchValueFromMultiSelector(filtered_df, "object.id", object_search_value, object_value)
            object_unique_options=filterObjectIdDependingTab(df, object_unique_options, tab)
            if len(df) == 0:
                # Deactivating the last activity empties the view on purpose. Say so
                # rather than opening a tab of empty charts with no hint why. The link
                # still carries the choice, since that is what brings the view back.
                new_query_params = {'tab': tab}
                if hidden_activities:
                    new_query_params[HIDDEN_ACTIVITIES_PARAM] = ",".join(hidden_activities)
                return (
                    f"{urlencode(new_query_params)}",
                    user_unique_options,
                    object_unique_options,
                    html.Div(html.Div([
                        html.H3('No activity is on'),
                        html.P(
                            f"All {len(activity_ids)} activities of this session are deactivated, so there "
                            "is nothing to plot. Use the All button above to bring them back."
                        ),
                    ])),
                )
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
                    html.H3('Video Seen/Skipped'),
                    dcc.Graph(
                        id='video-skipped-seen',
                        figure=xAPISGVideosSeenSkipped.VideoSeenSkippedBarChart(filtered_df)
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
                # Flatten nested statement values (e.g. context.contextActivities.parent,
                # an array per the xAPI spec) into sub-columns, on a display-only copy:
                # the charts share filtered_df and must keep one row per statement.
                table_df = flatten_for_display(filtered_df)
                data = table_df.where(pd.notna(table_df), None).to_dict('records')
                tab_content= html.Div([
                    html.H3("Length table : " + str(len(data))),
                    dash_table.DataTable(
                        id='table-all-xapi-data',
                        columns=[{"name": i, "id": i} for i in table_df.columns],
                        data=data,
                        filter_action='native',
                        sort_action="native",
                        sort_mode="multi",
                        #sort_by=[{'column_id': 'timestamp', 'direction': 'asc'}],
                    )
                ])
            else:
                tab_content = html.Div()
            new_query_params = { 'tab': tab }
            if user_value and len(user_value)>0:
                new_query_params["actor.name"]=",".join(user_value)
            if object_value and len(object_value)>0:
                new_query_params["object.id"]=",".join(object_value)
            if hidden_activities and len(hidden_activities)>0:
                # Only written when something is hidden, so a link to a whole session
                # stays the short one it is without the parameter.
                new_query_params[HIDDEN_ACTIVITIES_PARAM]=",".join(hidden_activities)
            print(f"Query param url:{new_query_params}")
            # Construct a new query string with unique parameters
            new_query_string = urlencode(new_query_params, safe=" ")
            print(f"new_query_string: {new_query_string}")
            return f"{new_query_string}", user_unique_options,object_unique_options, tab_content
        else:
            url=f"tab=home_tab"
            return url,[], [], html.Div(homepagecontent)
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
        dcc.Dropdown(id='object-multi-dynamic-dropdown', multi=True),
        # Which activities of the session are in the view. Above the tabs and not inside
        # one, so it applies to every visualisation at once instead of only to the tab it
        # happens to sit in. The row is built by update_activity_filter and stays hidden
        # until there is a choice to make.
        dcc.Store(id='activity-filter-hidden', data=[]),
        html.Div(id='activity-filter-controls', style={'display': 'none'}, children=[
            html.Span('Activities: ', style={'marginRight': '10px'}),
            html.Button('All', id='activity-filter-all', n_clicks=0,
                        style={'marginRight': '5px'}),
            html.Button('None', id='activity-filter-none', n_clicks=0,
                        style={'marginRight': '15px'}),
            html.Span(id='activity-filter-info', children='', style={'color': '#555'}),
        ]),
        html.Div(id='activity-filter-div', children=[], style={'margin': '5px 0'}),
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
        html.Div(id="tabs-content"),
        # Live updates: only meaningful once statements have been loaded, so these
        # controls live inside the panel that is revealed by a successful analysis.
        html.Hr(),
        html.Div([
            dcc.Checklist(
                id='lrs-poll-enabled',
                options=[{'label': ' Live updates', 'value': 'on'}],
                value=[],
                style={'display': 'inline-block', 'marginRight': '15px'}
            ),
            dcc.Dropdown(
                id='lrs-poll-rate',
                options=[{'label': f'{s} seconds', 'value': s} for s in (5, 10, 30, 60, 300)],
                value=10,
                clearable=False,
                style={'display': 'inline-block', 'width': '140px'}
            ),
            html.Span(id='lrs-poll-count', children='', style={'marginLeft': '15px'}),
        ]),
        html.Div(id='lrs-poll-status', children='', style={'fontSize': '0.85em', 'color': '#555'})
    ])
])
TMonFooter=html.Div([
    html.Hr(),
    html.H4(children='T-MON, by eUCM research team')
])
