import dash
from dash import html, dash_table, dcc, callback, Output, Input, State
from dash.exceptions import PreventUpdate
import pandas as pd
import json
import TMonWidgets
from LoadProcessStatements import resolve_actor_name_column, flatten_for_display
from TMonWidgets.ActivityFilter import filter_df_by_activities, statements_activity_ids
from TMonWidgets.ChartBuilder import (
    AGGREGATION_LABELS,
    CHART_TYPES,
    COUNT_LABEL,
    CREATED_CHARTS_PARAM,
    MAX_CREATED_CHARTS,
    build_chart,
    chartable_columns,
    decode_specs,
    describe,
    encode_spec,
    normalise_spec,
    numeric_columns,
)
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


def created_charts_from_url(pathname):
    """
    Read the charts a link asks for.

    Args:
        pathname (str): The dashboard URL, query parameters included.

    Returns:
        list: The chart descriptions named by the URL, empty when it names none.
    """
    return decode_specs(get_value_from_url(pathname or "", f"{CREATED_CHARTS_PARAM}="))


def creator_controls_style(tab):
    """
    Return whether the creator row is shown, which is only in its own tab.

    The row stays where it is in the layout so that the choices already made in it
    survive a change of tab, and it is hidden everywhere else so that it does not sit
    over the visualisations of the other tabs.

    Args:
        tab (str): The value of the open tab.

    Returns:
        dict: The style to show the row with.
    """
    return {'display': 'block'} if tab == 'create_tab' else {'display': 'none'}


@callback(
    # Declared without a list on purpose. A callback whose outputs are wrapped in a list
    # is a multi-output one even when there is a single output, and Dash then unpacks
    # the returned value as one element per output: a bare list would be spread over the
    # outputs instead of being the value of the only one there is. Written this way the
    # value is the value, list or not, which is what this callback answers with.
    Output('activity-filter-hidden', 'data'),
    [
        Input({'type': 'activity-button', 'index': dash.dependencies.ALL}, 'n_clicks'),
        Input('activity-filter-all', 'n_clicks'),
        Input('activity-filter-none', 'n_clicks'),
        # Bumped by the poller when statements arrive, so an activity that produces its
        # first ones joins the row instead of being filtered out of a view it is not in.
        Input("lrs-data-version", "data"),
        # The panel is revealed by a successful analysis, which is when the selection,
        # and with it the statements, changes.
        Input('output-t-mon', 'style'),
    ],
    [
        State('activity-filter-hidden', 'data'),
        # The URL is read as a State, never as an Input: the dashboard writes its state
        # into the URL, so an Input here would close a loop back into this callback.
        State('url-t-mon', 'pathname'),
    ]
)
def update_activity_filter(button_n_clicks, all_n_clicks, none_n_clicks, lrs_data_version,
                           panel_style, hidden, pathname):
    """
    Change which activities are out of the view, and drop what no longer applies.

    The store holds the activities that are *out* of the view rather than the ones in it,
    which is what makes a stale value harmless: the ids of another session are simply not
    in the data, so they hide nothing, and an activity that appears later is on until it
    is clicked.

    Drawing the buttons is left to render_activity_filter, so that this is the only
    callback that writes the store. Were it to draw the row as well, the store would have
    a second writer and the two could disagree about which activities are out.

    A new selection takes its state from the link, which is how a shared link or a reload
    shows what it says, and drops the ids of activities the new selection does not have.
    """
    triggered = dash.callback_context.triggered
    triggered_prop_id = triggered[0]['prop_id'] if triggered else ''
    known = statements_activity_ids(TMonWidgets.xapiData)
    hidden = [str(value) for value in (hidden or [])]
    print(f"Activities : known={known} - hidden={hidden} - triggered={triggered_prop_id}")
    if 'output-t-mon' in triggered_prop_id and panel_style == {"display": "block"}:
        hidden = [activity_id for activity_id in hidden_activities_from_url(pathname)
                  if activity_id in known]
    elif 'activity-filter-all' in triggered_prop_id and int(all_n_clicks or 0) > 0:
        hidden = []
    elif 'activity-filter-none' in triggered_prop_id and int(none_n_clicks or 0) > 0:
        hidden = list(known)
    elif 'activity-button' in triggered_prop_id and button_n_clicks and max(button_n_clicks) > 0:
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
    if len(known) < MIN_ACTIVITIES_TO_CHOOSE:
        # Nothing to choose between: a single activity, a selection that is an activity
        # itself, or a data set that names none. No row, and no state either, so such a
        # selection is never held to a filter that does not apply to it.
        return []
    # An id that names no activity of the data left behind is dropped: those are what a
    # link to another session carries, they hide nothing, and keeping them would only put
    # ids of another study in the next link written out.
    return [known_id for known_id in known if known_id in hidden]


@callback(
    [
        Output('activity-filter-div', 'children'),
        Output('activity-filter-controls', 'style'),
        Output('activity-filter-info', 'children'),
    ],
    [
        Input('activity-filter-hidden', 'data'),
        # New statements may name an activity that was not there to draw a button for.
        Input("lrs-data-version", "data"),
    ]
)
def render_activity_filter(hidden, lrs_data_version):
    """
    Draw the row of activity buttons for the statements currently loaded.

    The buttons are built from the data rather than from a list kept alongside it, so
    the row always offers exactly the activities there is something to choose between,
    and one whose first statement has just arrived is there to be chosen.
    """
    known = statements_activity_ids(TMonWidgets.xapiData)
    if len(known) < MIN_ACTIVITIES_TO_CHOOSE:
        return [], {'display': 'none'}, ''
    hidden = [str(value) for value in (hidden or [])]
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
        buttons,
        {'display': 'block'},
        f"{len(shown)} of {len(known)} activities shown",
    )


@callback(
    [
        Output('created-charts', 'data'),
        Output('chart-creator-status', 'children'),
    ],
    [
        Input('chart-add', 'n_clicks'),
        Input({'type': 'chart-remove', 'index': dash.dependencies.ALL}, 'n_clicks'),
        # A new selection takes its charts from the link, for the same reason the
        # activities do: this is where a shared link or a reload is read.
        Input('output-t-mon', 'style'),
    ],
    [
        State('chart-type', 'value'),
        State('chart-x', 'value'),
        State('chart-y', 'value'),
        State('chart-aggregation', 'value'),
        State('created-charts', 'data'),
        # A State, never an Input, for the same reason as in update_activity_filter.
        State('url-t-mon', 'pathname'),
    ]
)
def update_created_charts(add_n_clicks, remove_n_clicks, panel_style, chart_type, chart_x,
                          chart_y, chart_aggregation, charts, pathname):
    """
    Add and remove the charts the creator holds, and take them from a link.

    This is the only callback that writes the list, so the store, the buttons that
    remove a chart and the URL the dashboard carries it in never disagree.
    """
    triggered = dash.callback_context.triggered
    triggered_prop_id = triggered[0]['prop_id'] if triggered else ''
    charts = [chart for chart in (charts or []) if isinstance(chart, dict)]
    status = ''
    if 'output-t-mon' in triggered_prop_id and panel_style == {"display": "block"}:
        charts = created_charts_from_url(pathname)
    elif 'chart-add' in triggered_prop_id and int(add_n_clicks or 0) > 0:
        spec = normalise_spec({
            "type": chart_type, "x": chart_x, "y": chart_y, "aggregation": chart_aggregation
        })
        if spec is None:
            status = 'Pick a column for the x axis first.'
        elif len(charts) >= MAX_CREATED_CHARTS:
            status = f'The dashboard holds {MAX_CREATED_CHARTS} charts at most, remove one first.'
        else:
            charts = charts + [spec]
    elif 'chart-remove' in triggered_prop_id and remove_n_clicks and max(remove_n_clicks) > 0:
        index = int(json.loads(triggered_prop_id.rsplit('.n_clicks', 1)[0])['index'])
        if 0 <= index < len(charts):
            charts = charts[:index] + charts[index + 1:]
    print(f"Charts : {[describe(chart) for chart in charts]} - triggered={triggered_prop_id}")
    return charts[:MAX_CREATED_CHARTS], status


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
        # The axes the creator offers are the columns the data actually has, so they are
        # published from here, where the frame that names them lives.
        Output('chart-x', 'options'),
        Output('chart-y', 'options'),
        # And the creator shows itself only in the tab it belongs to, so it does not sit
        # over the other visualisations. Decided here because this is the callback that
        # knows which tab is open, and the row keeps its place in the layout, which is
        # what preserves the choices already made in it.
        Output('chart-creator-controls', 'style'),
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
    # The charts to draw, so adding or removing one shows it without another round trip.
    Input("created-charts", "data"),
)
def update_output(tab, user_search_value, user_value, object_search_value, object_value,
                  lrs_data_version=None, hidden_activities=None, created_charts=None):
    ctx = dash.callback_context
    triggered=ctx.triggered
    triggered_prop_id = ctx.triggered[0]['prop_id']
    res=f"Triggered : {triggered} - {triggered_prop_id}"
    print(res)
    # Normalize the JSON data to a pandas DataFrame
    if ('object-multi-dynamic-dropdown' in triggered_prop_id or 'users-multi-dynamic-dropdown' in triggered_prop_id
            or 't-mon-tabs' in triggered_prop_id or 'lrs-data-version' in triggered_prop_id
            or 'activity-filter-hidden' in triggered_prop_id or 'created-charts' in triggered_prop_id):
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
            # The creator is offered the axes the data has: any column on the x axis, and
            # on the y axis only the ones holding a number, since nothing else can be
            # summed or averaged. Counting statements needs no value at all.
            x_options=[{'label': column, 'value': column} for column in chartable_columns(df)]
            y_options=[{'label': COUNT_LABEL, 'value': COUNT_LABEL}] + [
                {'label': column, 'value': column} for column in numeric_columns(df)
            ]
            creator_style=creator_controls_style(tab)
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
                    [],
                    [],
                    creator_style,
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
            elif tab == 'create_tab':
                # The charts the creator holds, drawn from the same filtered statements
                # every other tab reads, so they follow the activity buttons, the player
                # and object selectors, and the live updates without being asked again.
                content=[]
                for index, spec in enumerate(created_charts or []):
                    content.append(html.Div([
                        html.Button('Remove', id={'type': 'chart-remove', 'index': index},
                                    n_clicks=0, style={'backgroundColor': 'lightgray',
                                                       'marginBottom': '5px'}),
                        dcc.Graph(figure=build_chart(filtered_df, spec)),
                    ]))
                tab_content=html.Div(html.Div([
                    html.H3('Your visualisations'),
                    html.P(
                        "Every chart you create is listed here and drawn from the statements the "
                        "filters leave in the view. Add one with the row above: pick a chart type, "
                        "the column for each axis and how to count or measure, then press Add chart."
                    ),
                ] + content) if content else [
                    html.H3('No visualisation created yet'),
                    html.P(
                        "Pick a chart type, the column to put on each axis and how to count or "
                        "measure the statements, then press Add chart. The chart is drawn here "
                        "straight away."
                    ),
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
            if created_charts and len(created_charts)>0:
                # The charts a link carries, in the order they are drawn.
                encoded = [encode_spec(spec) for spec in created_charts]
                described = [value for value in encoded if value]
                if described:
                    new_query_params[CREATED_CHARTS_PARAM]=",".join(described)
            print(f"Query param url:{new_query_params}")
            # Construct a new query string with unique parameters
            new_query_string = urlencode(new_query_params, safe=" ")
            print(f"new_query_string: {new_query_string}")
            return (f"{new_query_string}", user_unique_options, object_unique_options,
                    tab_content, x_options, y_options, creator_style)
        else:
            url=f"tab=home_tab"
            return url, [], [], html.Div(homepagecontent), [], [], creator_controls_style(tab)
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
        # The creator: the description of a chart to draw, kept in the store so several
        # can be held at once and carried in the URL. The charts themselves are drawn in
        # the Create tab below, where the other visualisations are, and these controls
        # are left in the layout rather than drawn by a callback so that a redraw never
        # takes the choices already made in them back.
        dcc.Store(id='created-charts', data=[]),
        html.Div(id='chart-creator-controls', children=[
            html.Span('Create a visualisation: ', style={'marginRight': '10px'}),
            dcc.Dropdown(
                id='chart-type',
                options=[{'label': chart_type, 'value': chart_type} for chart_type in CHART_TYPES],
                value='bar', clearable=False,
                style={'display': 'inline-block', 'width': '110px', 'marginRight': '10px'}
            ),
            dcc.Dropdown(
                id='chart-x', options=[], placeholder='on the x axis',
                style={'display': 'inline-block', 'width': '230px', 'marginRight': '10px'}
            ),
            dcc.Dropdown(
                id='chart-y', options=[], value=COUNT_LABEL, clearable=False,
                style={'display': 'inline-block', 'width': '230px', 'marginRight': '10px'}
            ),
            dcc.Dropdown(
                id='chart-aggregation',
                options=[{'label': label, 'value': name}
                         for name, label in AGGREGATION_LABELS.items()],
                value='count', clearable=False,
                style={'display': 'inline-block', 'width': '170px', 'marginRight': '10px'}
            ),
            html.Button('Add chart', id='chart-add', n_clicks=0),
            html.Span(id='chart-creator-status', children='', style={'marginLeft': '10px', 'color': '#555'}),
        ], style={'margin': '10px 0'}),
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
                dcc.Tab(label='xAPI Data', value='data_tab'),
                dcc.Tab(label='Create', value='create_tab')
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
