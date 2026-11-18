import base64
import dash
from dash import html, dash_table, dcc, callback, Output, Input, State, no_update
from dash.exceptions import PreventUpdate
import pandas as pd
import json
import TMonWidgets
from TMonWidgets.BrandAssets import (
    LOGO_SRC, WORDMARK_SRC, USER_ICON_SRC, POWER_ICON_SRC, INFO_ICON_SRC,
    CONTACT_ICON_SRC,
)
from TMonWidgets import I18n
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
from datetime import datetime

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

def render_homepage_content():
    """The default view before a dashboard tab has been chosen."""
    return [
        html.H2('T-Mon Home Page.'),
        html.H3(I18n.t('dashboard.no_tab_selected')),
    ]


def url_output(panel_style, query_string):
    """
    The URL to publish from the dashboard, or ``no_update`` while it is hidden.

    The query string written to ``url-t-mon.pathname`` is relative on purpose:
    once the dashboard is open, a new ``tab=...`` value replaces the previous
    one in place. Doing that while the dashboard is still hidden would instead
    resolve against the current path and overwrite its last segment, turning a
    simlet tile link's ``/simlet/1`` into ``/simlet/tab=home_tab``. Until a
    selection has been analysed the URL therefore belongs to the app, not the
    dashboard, and is left untouched.
    """
    if panel_style == {'display': 'block'}:
        return query_string
    return no_update


def simlet_field(simlet, *keys):
    """
    Read the first of ``keys`` a simlet object carries.

    The dashboard is fed both the raw SimVA objects (``simlet_id``/``simlet_name``
    and, on legacy servers, ``_id``/``_name``) and the normalised ones used by the
    browser grid (``id``/``name``). Metadata may also be nested under ``metadata``
    or ``info``. Looking in all of those places keeps one renderer for every
    source and tolerates the API adding a prefix later.

    Args:
        simlet (dict): A simlet object from the SimVA API.
        *keys: Field names to try, in order of preference.

    Returns:
        The first non-None value found, or None.
    """
    if not isinstance(simlet, dict):
        return None
    for source in (simlet, simlet.get("metadata"), simlet.get("info")):
        if not isinstance(source, dict):
            continue
        for key in keys:
            if source.get(key) is not None:
                return source[key]
    return None


def simlet_date(value):
    """
    Render a simlet timestamp as ``YYYY/MM/DD``.

    The SimVA API has shipped ISO strings, epoch numbers and nested date objects
    for these fields; all three are accepted, and anything unparseable becomes a
    dash rather than a traceback.

    Args:
        value: A timestamp in any of the supported representations.

    Returns:
        str: The date in ``YYYY/MM/DD`` form, or ``-`` when it is unknown.
    """
    if value in (None, ""):
        return "-"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        stamp = float(value)
        if abs(stamp) > 1e11:  # milliseconds, not seconds
            stamp /= 1000
        try:
            return datetime.fromtimestamp(stamp).strftime("%Y/%m/%d")
        except (ValueError, OSError, OverflowError):
            return "-"
    if isinstance(value, dict):
        return simlet_date(simlet_field(value, "date", "value", "timestamp"))
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return "-"
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).strftime("%Y/%m/%d")
        except ValueError:
            pass
        for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(text[:19], pattern).strftime("%Y/%m/%d")
            except ValueError:
                continue
    return "-"


def simlet_count(value):
    """
    Turn a count-like simlet field into an integer.

    The API may send a number, a count string, or the collection itself, so the
    length of a list/dict is used as the count in those cases.

    Args:
        value: The raw field value.

    Returns:
        int: The number of items, or 0 when there is nothing to count.
    """
    if value is None or isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, (list, tuple, set, dict, str)):
        return len(value)
    return 0


def tag_text_color(color):
    """
    Choose readable text for a tag chip of the given background colour.

    The API supplies the tag's own ``tag_color``, which can be light enough
    that white text disappears. A simple brightness check keeps the label
    legible on both dark and light chips.

    Args:
        color: The tag's CSS colour.

    Returns:
        str: A light or dark text colour.
    """
    if not isinstance(color, str):
        return TEXT_PRIMARY
    value = color.strip().lstrip('#')
    if len(value) == 3:
        value = ''.join(character * 2 for character in value)
    if len(value) not in (6, 8) or any(character not in '0123456789abcdefABCDEF'
                                      for character in value):
        return TEXT_PRIMARY
    red, green, blue = (int(value[index:index + 2], 16) for index in (0, 2, 4))
    brightness = (0.299 * red + 0.587 * green + 0.114 * blue) / 255
    return DARK_BACKGROUND if brightness > 0.65 else TEXT_PRIMARY


def simlet_tags(simlet):
    """
    Read the tags of a simlet, keeping the colour each one was given in SimVA.

    A tag from the API looks like
    ``{"tag_id": 1, "tag_name": "test", "tag_color": "#3b82f6"}``. Plain
    strings and name-to-colour maps are accepted as well, so a tag still shows
    up when the API leaves out its colour.

    Args:
        simlet (dict): A simlet object from the SimVA API.

    Returns:
        list: ``{"name": ..., "color": ...}`` pairs, empty when there are none.
    """
    value = simlet_field(simlet, "tags", "tag", "simlet_tags")
    if value is None or value == "":
        return []
    if isinstance(value, str):
        return [{"name": part.strip(), "color": BRAND_PRIMARY}
                for part in value.split(",") if part.strip()]
    if isinstance(value, dict):
        return [{"name": str(name).strip(),
                 "color": str(color).strip() if color else BRAND_PRIMARY}
                for name, color in value.items() if str(name).strip()]
    if isinstance(value, (list, tuple, set)):
        tags = []
        for tag in value:
            if isinstance(tag, dict):
                name = simlet_field(tag, "tag_name", "name", "tag", "label", "value")
                color = simlet_field(tag, "tag_color", "color", "colour")
            else:
                name, color = tag, None
            if name is None or not str(name).strip():
                continue
            tags.append({
                "name": str(name).strip(),
                "color": str(color).strip() if color else BRAND_PRIMARY,
            })
        return tags
    return [{"name": str(value), "color": BRAND_PRIMARY}]


def simlet_participants(simlet):
    """
    Count the participants of a simlet.

    Some API versions publish a top-level participant count; others only list
    the groups. In the latter case the participants named by each group are
    added up. With neither, the count is zero.

    Args:
        simlet (dict): A simlet object from the SimVA API.

    Returns:
        int: The number of participants.
    """
    # SimvaBrowser calls /simlets/<id>/groups/participants/count while loading
    # the studies and annotates each one with `participants_count`.
    explicit = simlet_field(
        simlet, "participants_count", "participants", "participant_count",
        "nb_participants", "users")
    if explicit is not None:
        return simlet_count(explicit)
    groups = simlet_field(simlet, "groups", "group_count", "nb_groups")
    if isinstance(groups, (list, tuple, set)):
        return sum(
            simlet_count(simlet_field(group, "participants", "users", "members",
                                      "participant_ids"))
            for group in groups if isinstance(group, dict)
        )
    return 0


def simlet_tile_details(simlet):
    """
    Collect the metadata a simlet tile shows, whatever the API called its fields.

    Args:
        simlet (dict): A simlet object, raw or normalised.

    Returns:
        dict: The values to put on the tile.
    """
    return {
        "created": simlet_date(simlet_field(
            simlet, "created_at", "created", "creation_date", "creationDate", "createdAt")),
        "updated": simlet_date(simlet_field(
            simlet, "updated_at", "updated", "last_updated", "modified_at", "updatedAt")),
        "sessions": simlet_count(simlet_field(
            simlet, "sessions", "session_count", "nb_sessions", "total_sessions")),
        "groups": simlet_count(simlet_field(
            simlet, "groups", "group_count", "nb_groups")),
        "participants": simlet_participants(simlet),
        "tags": simlet_tags(simlet),
    }


def render_simlet_tiles(studies):
    """
    Render a grid of simlet (simlet) tiles using TMON.figcraft design tokens.

    Each tile carries the simlet name together with its creation and update
    dates, the number of sessions, groups and participants, and its tags.

    Args:
        studies (list): List of simlet objects from the SimVA API.

    Returns:
        html.Div: A grid of simlet tiles.
    """
    if not studies:
        return html.Div(I18n.t('simlets.no_studies'))

    tiles = []
    for i, simlet in enumerate(studies):
        simlet_id = (simlet_field(simlet, "id", "simlet_id", "_id")
                     or simlet_field(simlet, "name", "simlet_name", "_name")
                     or f"simlet {i+1}")
        simlet_name = (simlet_field(simlet, "name", "simlet_name", "_name")
                       or str(simlet_id))
        details = simlet_tile_details(simlet)

        # The card is a light surface, so its text has to be dark; the light
        # tokens are only legible on the dark header.
        meta_style = {
            'fontFamily': INTER_FONT,
            'fontSize': 11,
            'lineHeight': '18px',
            'color': TEXT_SECONDARY,
            'whiteSpace': 'nowrap',
            'overflow': 'hidden',
            'textOverflow': 'ellipsis',
        }
        tag_chips = [
            html.Span(
                tag['name'],
                style={
                    'display': 'inline-block',
                    'backgroundColor': tag['color'],
                    'color': tag_text_color(tag['color']),
                    'fontFamily': INTER_FONT,
                    'fontSize': 10,
                    'lineHeight': '16px',
                    'padding': '0 8px',
                    'margin': '2px 4px 0 0',
                    'borderRadius': 10,
                    'whiteSpace': 'nowrap',
                },
            )
            for tag in details['tags']
        ]
        tile = html.A(
            html.Div([
                html.Div(
                    simlet_name[:50] + ("..." if len(simlet_name) > 50 else ""),
                    style={
                        'fontFamily': INTER_FONT,
                        'fontSize': 14,
                        'fontWeight': '500',
                        'color': DARK_BACKGROUND,
                        'padding': '12px 12px 8px',
                        'height': '44px',
                        'boxSizing': 'border-box',
                        'display': 'flex',
                        'alignItems': 'center',
                        'textOverflow': 'ellipsis',
                        'whiteSpace': 'nowrap',
                        'overflow': 'hidden',
                        'borderBottom': '1px solid rgba(0,0,0,0.1)',
                    }
                ),
                html.Div([
                    html.Div(f"{I18n.t('info.created_at')}: {details['created']}",
                             style=meta_style),
                    html.Div(f"{I18n.t('info.updated_at')}: {details['updated']}",
                             style=meta_style),
                    html.Div(f"{I18n.t('sessions.title')}: {details['sessions']}",
                             style=meta_style),
                    html.Div([
                        html.Span(f"{I18n.t('groups.title')}: {details['groups']}",
                                  style={'marginRight': '18px'}),
                        html.Span(f"{I18n.t('participants.title')}: "
                                  f"{details['participants']}"),
                    ], style=meta_style),
                    html.Div(f"{I18n.t('info.tags')}:",
                             style=dict(meta_style, marginTop='4px')),
                    html.Div(
                        tag_chips if tag_chips else html.Span(
                            I18n.t('info.tags.no_tags'), style={'color': TEXT_SECONDARY}),
                        style=dict(meta_style, whiteSpace='normal'),
                    ),
                ], style={'padding': '8px 12px 12px'}),
            ],
                style={
                    'backgroundColor': LIGHT_CARD,
                    'border': '1px solid rgba(0,0,0,0.1)',
                    'borderRadius': 8,
                    'width': f'{SIMLET_TILE_WIDTH}px',
                    'height': f'{SIMLET_TILE_HEIGHT}px',
                    'boxSizing': 'border-box',
                    'margin': f'{SIMLET_TILE_MARGIN}px',
                    'display': 'inline-block',
                    'verticalAlign': 'top',
                    'transition': 'transform 0.2s',
                }
            ),
            href=f"/simlet/{simlet_id}",
            style={
                'textDecoration': 'none',
                'color': 'inherit',
            }
        )
        tiles.append(tile)

        # Add row break after every 4 tiles
        if (i + 1) % 4 == 0 and i < len(studies) - 1:
            tiles.append(html.Div(style={'clear': 'both'}))

    # Fill remaining space if less than 4 in last row
    remaining = len(studies) % 4
    if remaining > 0:
        for _ in range(4 - remaining):
            tiles.append(html.Div(style={
                'width': f'{SIMLET_TILE_WIDTH}px',
                'height': f'{SIMLET_TILE_HEIGHT}px',
                'backgroundColor': 'transparent',
            }))

    return html.Div(tiles, style={'padding': '20px'})

@callback(
    Output('content', 'style'),
    Input('t-mon-tabs', 'value')
)
def show_interpretation_log_on_arrival(tab):
    """Keep the load/interpretation log only until a tab is chosen."""
    if tab is None or tab == '':
        return {'display': 'block'}
    return {'display': 'none'}


@callback(
    [Output('dashboard-tabs-wrapper', 'className'),
     Output('dashboard-tabs-toggle', 'children')],
    Input('dashboard-tabs-toggle', 'n_clicks')
)
def toggle_dashboard_tabs(n_clicks):
    """Switch the vertical tab bar between icons + names and icons only."""
    if (n_clicks or 0) % 2:
        return 'dashboard-tabs-compact', '▶'
    return 'dashboard-tabs-full', '◀'


@callback(
    Output('dashboard-title', 'children'),
    [Input('output-t-mon', 'style'),
     Input('current-simlet', 'children'),
     Input('current-test', 'children')]
)
def update_dashboard_title(style, simlet_name, session_name):
    """Name the open simlet and session in the dashboard header."""
    if style != {'display': 'block'}:
        return ''
    # Children may be empty Dash components rather than text; only real names
    # belong in the title.
    return ' / '.join(str(part) for part in (simlet_name, session_name)
                      if isinstance(part, str) and part)


@callback(
    Output('dashboard-tab-home_tab', 'style'),
    Input('url', 'pathname')
)
def hide_home_tab(pathname):
    """The HomePage grid has no place in a session or upload dashboard."""
    if pathname and '/dashboard' in pathname:
        if '/session/' in pathname or '/upload' in pathname:
            return {'display': 'none'}
    return {'display': 'block'}


@callback(
    [
        Output('t-mon-tabs', 'value'),
        Output("users-multi-dynamic-dropdown", "value"),
        Output("object-multi-dynamic-dropdown", "value")
    ],
    Input('output-t-mon', 'style'),
    [State('url-t-mon', 'pathname'), State('url', 'pathname')]
)
def update_tab(style, stateUrl, app_path):
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
        # A session dashboard opens with no tab selected: the page shows the
        # simlet/session names first and lets the user pick a visualisation.
        if app_path and '/session/' in app_path and '/dashboard' in app_path:
            tab = None
            user_value = []
            object_value = []
            print(f"Session dashboard: no tab selected ({app_path})")
            return tab, user_value, object_value
        tab=new_tab
        user_value=users.split(",") if users else []
        object_value=object.split(",") if object else []
        print(f"Tab: {tab} - URL : {urlValues} - user_value : {user_value} - object_value: {object_value}")
        return tab, user_value, object_value
    else:
        raise PreventUpdate


# Make studies available to the dashboard
TMonWidgets.accepted_studies = getattr(TMonWidgets, "accepted_studies", [])
# Sessions of the currently open simlet, published by the SIMVA browser so the
# sessions list can draw them without making its own API calls.
TMonWidgets.accepted_sessions = getattr(TMonWidgets, "accepted_sessions", [])


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
    # ids of another simlet in the next link written out.
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
    # The dashboard is hidden until a selection is analysed. Until then it must not
    # write a relative query string into the URL: that would resolve against the
    # current path and overwrite the simlet id of a `/simlet/<id>` tile link.
    State('output-t-mon', 'style'),
    State('current-simlet', 'children'),
    State('current-test', 'children'),
    State('url', 'pathname'),
    Input('graph-layout', 'value'),
    Input('graph-rows', 'value'),
    Input('graph-columns', 'value'),
    Input('graph-page', 'value'),
    Input('graph-split-x', 'value'),
    Input('graph-split-y', 'value'),
)
def update_output(tab, user_search_value, user_value, object_search_value, object_value,
                  lrs_data_version=None, hidden_activities=None, created_charts=None,
                  panel_style=None, simlet_name=None, session_name=None,
                  app_path=None, graph_layout='one', graph_rows=3,
                  graph_columns=2, graph_page=1, split_x=2, split_y=2):
    ctx = dash.callback_context
    triggered=ctx.triggered
    triggered_prop_id = ctx.triggered[0]['prop_id']
    res=f"Triggered : {triggered} - {triggered_prop_id}"
    print(res)
    if tab is None or tab == '':
        # No visualization chosen yet: show where the user is and wait. The
        # activity buttons stay above this panel. A chosen tab must always fall
        # through, including in the upload dashboard.
        content = html.Div(render_homepage_content(), style={'padding': '20px'})
        return (no_update, [], [], content, [], [], creator_controls_style(tab))

    def publish_url(query):
        # An uploaded file is local to this page; writing a relative tab query
        # would replace `/dashboard/upload` in the URL and reset the tab on the
        # next load. Leave the dashboard URL alone in that mode.
        if app_path and '/dashboard/upload' in app_path:
            return no_update
        return url_output(panel_style, query)
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
                    publish_url(urlencode(new_query_params)),
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
                # The simlet grid lives in the SIMVA browser's studies list,
                # never in a dashboard. A local upload has no SimVA studies.
                tab_content = html.Div(render_homepage_content())
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
            tab_content = arrange_graphs(
                tab_content, graph_layout, graph_rows, graph_columns, graph_page,
                split_x, split_y)
            return (publish_url(new_query_string), user_unique_options,
                    object_unique_options, tab_content, x_options, y_options, creator_style)
        else:
            return (publish_url("tab=home_tab"), [], [],
                    html.Div(render_homepage_content()), [], [],
                    creator_controls_style(tab))
    else:
        raise PreventUpdate
    
# Design tokens from TMON.figcraft
# Brand colors
BRAND_PRIMARY = "#078493"
BRAND_SOFT = "#8ec8c7"
# The orange of the T-Mon logo, used for the top bar.
BRAND_ORANGE = "#ff8f22"
TEXT_PRIMARY = "#fff"
TEXT_SECONDARY = "#3c6d7a"
SURFACE_SUNKEN = "#e8e5e2"

# Original design tokens
# Figma design tokens from TMON.figcraft
DARK_BACKGROUND = "#1e1e1e"
LIGHT_CARD = "#fcfcfc"
INTER_FONT = "Inter"
SIDEBAR_HEIGHT = 108
# Enough room for the logo and wordmark alongside the login controls.
TOP_BAR_HEIGHT = 40  # compact version of the SIMVA front-end's 3rem bar
# Dark text on a white button reads well on the orange bar.
HEADER_BUTTON_STYLE = {
    'backgroundColor': '#fff',
    'border': f'1px solid {DARK_BACKGROUND}',
    'borderRadius': '4px',
    'color': DARK_BACKGROUND,
    'fontFamily': INTER_FONT,
    'fontSize': 13,
    'padding': '6px 14px',
    'cursor': 'pointer',
}

# The SIMVA-style header treats its controls as plain nav items, not raised
# buttons. Kept here so the Account callback can restate the style when it
# hides or shows the control.
HEADER_NAV_BUTTON_STYLE = {
    'background': 'none',
    'border': 'none',
    'color': '#000',
    'fontFamily': 'sans-serif',
    'fontSize': 14,
    'fontWeight': 'bold',
    'padding': '0',
    'cursor': 'pointer',
    'whiteSpace': 'nowrap',
}

# Simlet tiles design
SIMLET_TILE_WIDTH = 250
# The tile now carries the simlet metadata as well as its name, so it needs room
# for the dates, counts and tags below the heading.
SIMLET_TILE_HEIGHT = 240
SIMLET_TILE_MARGIN = 16
SIMLET_TITLE_MAX_LINES = 2

# The brand in the header links back to the T-Mon landing page.
TMON_HOME_URL = "https://tmon.external.test/"


def build_header(with_login=False, lang=None):
    """
    Build the sticky top bar shared by the T-Mon apps.

    The bar follows the SIMVA front-end header: bold black sans-serif text on
    an orange strip, logo and product name on the left, and a right-hand nav
    with Contact us, the signed-in user, Account and a black Login/Logout pill.
    The callback-owned ids are kept exactly as before, so the SIMVA login
    callbacks work wherever those controls sit in the layout.

    Args:
        with_login (bool): Include the SIMVA login/account controls.

    Returns:
        html.Div: The header, pinned to the top of the viewport.
    """
    link_style = {
        'display': 'flex', 'alignItems': 'center', 'height': '100%',
        'textDecoration': 'none', 'color': '#000', 'fontWeight': 'bold',
        'fontFamily': 'sans-serif', 'fontSize': 12, 'whiteSpace': 'nowrap',
    }
    icon_style = {'height': '1.2rem', 'width': 'auto', 'marginRight': '0.35rem'}
    item_style = {
        'display': 'flex', 'alignItems': 'center', 'height': '100%',
        'padding': '0 0.5rem', 'borderLeft': '1px solid #000',
    }

    brand = html.Div([
        html.A(I18n.t('navigation.return'), id='return-button', href='',
               style={'display': 'none', 'marginRight': '14px',
                      'fontFamily': 'sans-serif', 'fontSize': 12,
                      'fontWeight': 'bold', 'color': '#000',
                      'textDecoration': 'none'}),
        html.A([
            html.Img(
                src=LOGO_SRC, alt='T-Mon logo',
                style={'height': '1.6rem', 'width': 'auto', 'marginRight': '0.35rem'},
            ),
            html.Span('Txmon - The xAPI Trace Monitor', style={
                'fontFamily': 'sans-serif', 'fontSize': 12,
                'fontWeight': 'bold', 'color': '#000', 'whiteSpace': 'nowrap',
            }),
        ], href=TMON_HOME_URL, style=dict(link_style, border='none', padding='0')),
    ], className='header-left',
        style={'display': 'flex', 'alignItems': 'center', 'height': '100%'})

    # No value at build time: the language callback fills it from the session
    # (or the `lng` URL) so a remembered choice is shown as selected.
    language = lang
    items = [
        html.Li(dcc.Dropdown(
            id='header-language', clearable=False,
            options=[{'label': label, 'value': code}
                     for code, label in I18n.SUPPORTED_LANGUAGES.items()],
            value=language,
            style={'width': '110px', 'fontSize': 12}),
            style=dict(item_style, borderLeft='none', paddingRight='0.5rem')),
        html.Li(html.A([
            html.Img(src=CONTACT_ICON_SRC, style=icon_style),
            html.Span(I18n.t('header.contact.title'), id='header-contact-label'),
        ], href='https://www.e-ucm.es/es/people/', target='_blank',
            rel='noopener noreferrer', style=link_style),
            style=dict(item_style, paddingRight='0.5rem')),
    ]

    # Keep these ids exactly: the login/account callbacks in SimvaBrowserWidget
    # target them, wherever the controls are placed in the layout. The account
    # item shows only the username and is hidden while logged out.
    if with_login:
        items.append(html.Li([
            html.Img(src=USER_ICON_SRC, style=icon_style),
            html.Button('', id='account-button', n_clicks=0,
                        className='header-account-button',
                        style=dict(HEADER_NAV_BUTTON_STYLE, fontSize=12)),
            html.Div(id='account', children=[]),
        ], id='header-account-item', style=item_style))

    items.append(html.Li([
        html.Img(src=POWER_ICON_SRC, style=dict(icon_style, filter='invert(100%)',
                                                marginRight='0.35rem')),
        html.Button(I18n.t('header.login.title') if not with_login else I18n.t('header.logout.title'),
                    id='login-logout-button', n_clicks=0,
                    className='header-login-button',
                    style=dict(HEADER_NAV_BUTTON_STYLE, color='#fff', fontSize=12)),
    ], className='login' if not with_login else 'logout', style={
        'display': 'flex', 'alignItems': 'center', 'height': '100%',
        'backgroundColor': '#000', 'color': '#fff', 'borderLeft': '1px solid #000',
        'padding': '0 0.7rem 0 0.5rem',
    }))

    right_children = [html.Ul(items, style={
        'display': 'flex', 'alignItems': 'center', 'height': '100%',
        'listStyle': 'none', 'margin': 0, 'padding': 0,
    })]
    if with_login:
        right_children.append(html.Div(
            id='main-login', children=[
                html.Div(id='login-logout'),
                # Kept for the existing status callback, never shown: the
                # username now lives in the account item above.
                html.Div(id='connection-status', children='',
                         style={'display': 'none'}),
            ], style={'display': 'none'}))

    children = [
        brand,
        html.Div(right_children, className='header-right', style={
            'display': 'flex', 'alignItems': 'center', 'height': '100%',
            'marginLeft': '1rem', 'textAlign': 'center',
        }),
    ]

    return html.Div(children, className='header', style={
        'position': 'sticky',
        'top': 0,
        'zIndex': 100,
        'display': 'flex',
        'alignItems': 'center',
        'justifyContent': 'space-between',
        'flexWrap': 'nowrap',
        'height': f'{TOP_BAR_HEIGHT}px',
        'padding': '0.5rem',
        'backgroundColor': BRAND_ORANGE,
        'color': '#000',
        'margin': '0',
        'boxShadow': '0px 0px 0.3rem 0.15rem rgba(0,0,0,0.3)',
    })


# Kept for the local file-upload app, which needs the brand but no login controls.
TMonHeader = build_header()
# The SIMVA app shares the same bar with its login controls attached.
TMonSimvaHeader = build_header(with_login=True)

TMonSidebar=html.Div(id='sidebar', children=[])  # Will be populated by callbacks


def tab_icon(path):
    """A monochrome SVG data URI for a dashboard tab, in the SIMVA icon style."""
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'fill="none" stroke="#1e1e1e" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        f'<path d="{path}"/></svg>'
    )
    return 'data:image/svg+xml;base64,' + base64.b64encode(
        svg.encode('utf-8')).decode('ascii')


# value, label key (English default), SVG path. The HomePage tab is only shown
# outside a session dashboard, but it stays in the layout so callbacks keep
# targeting a stable id.
DASHBOARD_TABS = [
    ('home_tab', 'HomePage', 'M3 11l9-8 9 8v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z'),
    ('progress_tab', 'Progress', 'M4 19V9m6 10V5m6 14v-7m4 7H2'),
    ('video_tab', 'Videos', 'M4 5h12v14H4zM16 10l5-3v10l-5-3'),
    ('completable_tab', 'Completable', 'M9 11l3 3 8-8M5 12l3 3 3-3'),
    ('alternative_tab', 'Alternatives', 'M6 6h12v12H6zM10 10h4v4h-4z'),
    ('interaction_tab', 'Interactions',
     'M8 12a3 3 0 100-6 3 3 0 000 6zm8 0a3 3 0 100-6 3 3 0 000 6M2 20v-2a4 4 0 014-4h4a4 4 0 014 4v2'),
    ('accessible_tab', 'Accessible',
     'M12 2a2 2 0 110 4 2 2 0 010-4zm-5 7h10l2 6h-3l2 7m-10-7h3l2 7'),
    ('menu_tab', 'Menu', 'M4 6h16M4 12h16M4 18h16'),
    ('data_tab', 'xAPI Data', 'M4 4h16v16H4zM4 10h16M10 4v16'),
    ('create_tab', 'Create', 'M12 5v14M5 12h14'),
]


def return_target(pathname):
    """The page one level up from ``pathname``, or None at the studies list."""
    if not pathname or pathname == '/':
        return None
    if '/dashboard/upload' in pathname:
        return '/'
    if pathname.startswith('/simlet/'):
        parts = [part for part in pathname.split('/') if part and '=' not in part]
        if '/session/' in pathname and len(parts) >= 4:
            return f'/simlet/{parts[1]}'
        return '/'
    # Analysis paths are /<simlet>/<session>/...; go back to the simlet.
    parts = [part for part in pathname.split('/')
             if part and '=' not in part and part not in ('dashboard', 'default')]
    if len(parts) >= 2:
        return f'/simlet/{parts[0]}'
    if len(parts) == 1:
        return '/'
    return None


def live_updates_style(pathname):
    """Show the footer poll controls only in a SIMVA dashboard, not elsewhere."""
    if not pathname or '/dashboard' not in pathname:
        return {'display': 'none'}
    if '/dashboard/upload' in pathname:
        return {'display': 'none'}
    return {'display': 'flex', 'alignItems': 'center'}


GRAPH_LAYOUT_OPTIONS = [
    ('one', 'graphs.one'),
    ('vertical', 'graphs.vertical'),
    ('horizontal', 'graphs.horizontal'),
    ('grid', 'graphs.grid'),
    ('split', 'graphs.split'),
]

MAX_GRAPHS_PER_PAGE = 12


def arrange_graphs(content, layout, rows, columns, page, split_x=2, split_y=2):
    """
    Lay out a tab's graphs and show at most twelve of them per page.

    Non-graph elements (headings) stay above the graphs on the first page.
    """
    node = content
    while isinstance(node, html.Div) and isinstance(node.children, html.Div):
        node = node.children
    items = node.children if isinstance(node.children, (list, tuple)) else [node]
    headings = [item for item in items if not isinstance(item, dcc.Graph)]
    graphs = [item for item in items if isinstance(item, dcc.Graph)]
    if not graphs:
        return content

    try:
        rows_n = min(MAX_GRAPHS_PER_PAGE, max(1, int(rows or 1)))
        columns_n = min(MAX_GRAPHS_PER_PAGE, max(1, int(columns or 1)))
        page_n = max(1, int(page or 1))
    except (TypeError, ValueError):
        rows_n, columns_n, page_n = 1, 1, 1

    if layout == 'one':
        page_size, columns_n = 1, 1
    elif layout == 'vertical':
        page_size, columns_n = rows_n, 1
    elif layout == 'horizontal':
        page_size, rows_n = columns_n, 1
    elif layout == 'split':
        try:
            first = min(MAX_GRAPHS_PER_PAGE, max(0, int(split_x or 0)))
            second = min(MAX_GRAPHS_PER_PAGE, max(0, int(split_y or 0)))
        except (TypeError, ValueError):
            first, second = 2, 2
        if first + second == 0:
            first = 1
        page_size = min(MAX_GRAPHS_PER_PAGE, first + second)
        columns_n = 2
    else:
        page_size = min(MAX_GRAPHS_PER_PAGE, rows_n * columns_n)

    start = (page_n - 1) * page_size
    shown = graphs[start:start + page_size]
    if not shown:
        shown = graphs[:page_size]
        start = 0

    grid = {
        'display': 'grid',
        'gridTemplateColumns': f'repeat({columns_n}, minmax(0, 1fr))',
        'gap': '12px',
    }
    children = list(headings) if page_n == 1 else []
    for item in children:
        if hasattr(item, 'style'):
            item.style = dict(item.style or {}, gridColumn='1 / -1')
    if layout == 'split':
        # One graph stack per column: x in the first, y in the others.
        first_count = min(first, len(shown))
        column_style = {'display': 'flex', 'flexDirection': 'column',
                        'gap': '12px', 'minWidth': 0}
        children.extend([
            html.Div(shown[:first_count], style=column_style),
            html.Div(shown[first_count:], style=column_style),
        ])
    else:
        children.extend(shown)
    info = html.Span(
        f"{start + 1}-{start + len(shown)} of {len(graphs)}",
        style={'gridColumn': '1 / -1', 'fontFamily': INTER_FONT,
               'fontSize': 12, 'color': TEXT_SECONDARY})
    return html.Div([info] + children, style=grid)


def dashboard_tab_label(label, icon_path):
    """The label of a dashboard tab: an icon beside a hideable name."""
    return html.Span([
        html.Img(src=tab_icon(icon_path),
                 style={'height': '16px', 'width': '16px', 'marginRight': '8px'}),
        html.Span(label, className='tab-name'),
    ], style={'display': 'inline-flex', 'alignItems': 'center'})


TMonBody=html.Div([
    dcc.Location(id='url-t-mon', refresh=False), # Location component for URL handling
    # Written only when the header language changes; the reload picks up lng.
    dcc.Location(id='i18n-location', refresh=True),
    html.Div(id='output-t-mon', style={'display': 'none'}, children=[
        dcc.Store(id='activity-filter-hidden', data=[]),
        dcc.Store(id='created-charts', data=[]),
        # Dashboard header: where the user is, the filters and the activity
        # selector. This replaces the SIMVA browser while a dashboard is open,
        # so those controls no longer depend on the browser being visible.
        html.Div(id='dashboard-header', children=[
            html.H3(id='dashboard-title',
                    style={'fontFamily': INTER_FONT, 'fontSize': 16,
                           'margin': '0 0 6px'}),
            html.Div([
                dcc.Dropdown(id='users-multi-dynamic-dropdown', multi=True,
                             style={'width': '260px'}),
                dcc.Dropdown(id='object-multi-dynamic-dropdown', multi=True,
                             style={'width': '260px'}),
            ], style={'display': 'flex', 'gap': '10px', 'marginBottom': '6px'}),
            html.Div(id='activity-filter-controls', style={'display': 'none'}, children=[
                html.Span('Activities: ', style={'marginRight': '10px'}),
                html.Button('All', id='activity-filter-all', n_clicks=0,
                            style={'marginRight': '5px'}),
                html.Button('None', id='activity-filter-none', n_clicks=0,
                            style={'marginRight': '15px'}),
                html.Span(id='activity-filter-info', children='', style={'color': '#555'}),
            ]),
            html.Div(id='activity-filter-div', children=[], style={'margin': '5px 0'}),
        ], style={'padding': '8px 20px', 'borderBottom': '1px solid #ddd'}),
        # The tab bar is a sidebar for the dashboard; the visualisations sit to
        # its right. The app header and footer stay outside this panel.
        html.Div([
            html.Div([
                html.Button('◀', id='dashboard-tabs-toggle', n_clicks=0,
                            title='Show icons only / show tab names',
                            style={'background': 'none', 'border': 'none',
                                   'cursor': 'pointer', 'fontSize': '16px',
                                   'padding': '6px'}),
                dcc.Tabs(
                    id='t-mon-tabs', value=None, vertical=True,
                    className='dashboard-tabs',
                    children=[
                        dcc.Tab(id=f'dashboard-tab-{value}', value=value,
                                label=dashboard_tab_label(label, icon))
                        for value, label, icon in DASHBOARD_TABS
                    ],
                ),
            ], id='dashboard-tabs-wrapper', className='dashboard-tabs-full',
                style={'display': 'flex', 'alignItems': 'flex-start',
                       'flex': '0 0 auto'}),
            html.Div(id='dashboard-content', children=[
                # Loader/upload log, including the file name and date, belongs
                # beside the visualisations rather than above the tab bar.
                html.Div(id='content', children=[]),
                html.Div(id='chart-creator-controls', children=[
                    html.Span('Create a visualisation: ', style={'marginRight': '10px'}),
                    dcc.Dropdown(
                        id='chart-type',
                        options=[{'label': chart_type, 'value': chart_type}
                                 for chart_type in CHART_TYPES],
                        value='bar', clearable=False,
                        style={'display': 'inline-block', 'width': '110px',
                               'marginRight': '10px'}
                    ),
                    dcc.Dropdown(
                        id='chart-x', options=[], placeholder='on the x axis',
                        style={'display': 'inline-block', 'width': '230px',
                               'marginRight': '10px'}
                    ),
                    dcc.Dropdown(
                        id='chart-y', options=[], value=COUNT_LABEL, clearable=False,
                        style={'display': 'inline-block', 'width': '230px',
                               'marginRight': '10px'}
                    ),
                    dcc.Dropdown(
                        id='chart-aggregation',
                        options=[{'label': label, 'value': name}
                                 for name, label in AGGREGATION_LABELS.items()],
                        value='count', clearable=False,
                        style={'display': 'inline-block', 'width': '170px',
                               'marginRight': '10px'}
                    ),
                    html.Button('Add chart', id='chart-add', n_clicks=0),
                    html.Span(id='chart-creator-status', children='',
                              style={'marginLeft': '10px', 'color': '#555'}),
                ], style={'margin': '10px 0'}),
                html.Div([
                    html.Span(I18n.t('graphs.layout'),
                              style={'marginRight': '6px', 'fontSize': 12}),
                    dcc.Dropdown(
                        id='graph-layout', clearable=False, value='one',
                        options=[{'label': I18n.t(key), 'value': value}
                                 for value, key in GRAPH_LAYOUT_OPTIONS],
                        style={'width': '150px', 'marginRight': '10px'}),
                    html.Span(I18n.t('graphs.rows'), style={'marginRight': '4px',
                                                            'fontSize': 12}),
                    dcc.Input(id='graph-rows', type='number', min=1,
                              max=MAX_GRAPHS_PER_PAGE, value=3,
                              style={'width': '60px', 'marginRight': '10px'}),
                    html.Span(I18n.t('graphs.columns'),
                              style={'marginRight': '4px', 'fontSize': 12}),
                    dcc.Input(id='graph-columns', type='number', min=1,
                              max=MAX_GRAPHS_PER_PAGE, value=2,
                              style={'width': '60px', 'marginRight': '10px'}),
                    html.Span(I18n.t('graphs.page'), style={'marginRight': '4px',
                                                            'fontSize': 12}),
                    dcc.Input(id='graph-page', type='number', min=1, value=1,
                              style={'width': '60px'}),
                    html.Span(I18n.t('graphs.split_x'),
                              style={'marginLeft': '10px', 'marginRight': '4px',
                                     'fontSize': 12}),
                    dcc.Input(id='graph-split-x', type='number', min=0,
                              max=MAX_GRAPHS_PER_PAGE, value=2,
                              style={'width': '60px', 'marginRight': '10px'}),
                    html.Span(I18n.t('graphs.split_y'),
                              style={'marginRight': '4px', 'fontSize': 12}),
                    dcc.Input(id='graph-split-y', type='number', min=0,
                              max=MAX_GRAPHS_PER_PAGE, value=2,
                              style={'width': '60px'}),
                ], style={'display': 'flex', 'alignItems': 'center',
                          'gap': '2px', 'margin': '6px 0'}),
                html.Div(id="tabs-content"),
            ], style={'flex': '1 1 auto', 'minWidth': 0, 'padding': '10px 20px'}),
        ], style={'display': 'flex', 'alignItems': 'flex-start'}),
    ])
])
TMonFooter=html.Div([
    html.Hr(style={'margin': '0 0 8px 0'}),
    # Live updates only apply to statements read from SIMVA/LRS. Local uploads
    # have no source to poll, so this row is hidden unless the SIMVA app shows it.
    html.Div([
        dcc.Checklist(
            id='lrs-poll-enabled',
            options=[{'label': ' Live updates', 'value': 'on'}],
            value=[],
            style={'display': 'inline-block', 'marginRight': '15px'}
        ),
        dcc.Dropdown(
            id='lrs-poll-rate',
            options=[{'label': f'{s} seconds', 'value': s}
                     for s in (5, 10, 30, 60, 300)],
            value=10, clearable=False,
            style={'display': 'inline-block', 'width': '140px'}
        ),
        html.Span(id='lrs-poll-count', children='',
                  style={'marginLeft': '15px'}),
        html.Span(id='lrs-poll-status', children='',
                  style={'fontSize': '0.85em', 'color': '#555',
                         'marginLeft': '15px'}),
    ], id='live-updates-footer', style={'display': 'none', 'alignItems': 'center'}),
    html.H4(children='T-MON, by eUCM research team',
            style={'margin': '0', 'fontFamily': INTER_FONT, 'fontSize': 14}),
], style={
    # `marginTop: auto` in the page's flex column puts it at the bottom even on a
    # short page; sticky bottom keeps it in view while a long page scrolls.
    'position': 'sticky',
    'bottom': 0,
    'zIndex': 999,
    'marginTop': 'auto',
    'padding': '8px 20px',
    'backgroundColor': '#fff',
    'borderTop': '1px solid rgba(0,0,0,0.1)',
})
