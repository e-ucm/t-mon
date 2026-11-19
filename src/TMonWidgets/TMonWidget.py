import base64
import hashlib
import logging
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
from TMonWidgets import DefaultDashboard, GraphTypes
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
from TMonWidgets.MultiSelector import (
    MAX_PAGE_FILTERS,
    PAGE_FILTER_PARAM,
    apply_page_filters,
    decode_filters,
    encode_filters,
    filter_options,
    filterable_columns,
    normalise_filter,
    searchValueFromMultiSelector,
)
from TMonWidgets.VisualizationCatalog import (
    GROUPED_VISUALS, VISUALS, build_named_visual, describe_named, game_ids,
    short_label, target_ids,
)
from TMonWidgets.PageConfig import (
    LAYOUT_KEYS,
    build_document,
    import_config,
    list_saved,
    load_named,
    save_named,
    delete_named,
    serialize as serialize_config,
)
from vis import xAPISGPlayersProgress, xAPISGVideosSeenSkipped
from urllib.parse import unquote, urlencode
from datetime import datetime
import uuid

# Query parameter carrying the activities left out of the view. The name is deliberately
# not `activity`: get_value_from_url matches substrings, so `activity=` would also be
# found inside `hidden-activity=` and would read back the wrong value.
HIDDEN_ACTIVITIES_PARAM = "hidden-activity"

# A user-defined visualisation page is a tab whose value starts with this prefix;
# the built-in Create tab keeps the plain ``create_tab`` value for old links.
PAGE_TAB_PREFIX = "page:"
CREATE_TAB_KEY = "create_tab"

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


# Tabs of the default dashboard carry the same icons as their legacy ids. A new
# id from a deployment file gets a plain one; the icon is chrome, not wording.
DEFAULT_TAB_ICON_PATH = 'M12 5v14M5 12h14'


def dashboard_tabs():
    """The tab bar of the deployed dashboard, or the compatibility tabs."""
    definition = DASHBOARD_DEFINITION
    if not definition:
        return DASHBOARD_TABS
    icons = {value: icon for value, _, icon in DASHBOARD_TABS}
    return [
        (tab['id'], tab['title'], icons.get(tab['id'], DEFAULT_TAB_ICON_PATH))
        for tab in definition['tabs']
    ]


def default_tab_page(tab):
    """The definition's tab and page for a tab value, if it has one."""
    if not DASHBOARD_DEFINITION:
        return None, None
    return DefaultDashboard.find_tab(tab, DASHBOARD_DEFINITION)


def definition_filters(tab, page, selected):
    """The general and page filters of a default tab, with the live selections."""
    if not tab:
        return []
    specs = DefaultDashboard.filters_for(
        tab['id'], page['id'] if page else None, DASHBOARD_DEFINITION)
    return DefaultDashboard.with_selected_values(specs, selected)


def render_definition_filter_controls(filters, df):
    """Filter row above a default page. Its labels come from the definition."""
    controls = []
    for spec in filters or []:
        values = list(spec.get('values') or [])
        controls.append(html.Div([
            html.Span(f"{spec['label']}: ", style={'marginRight': '6px'}),
            dcc.Dropdown(
                id={'type': 'definition-filter', 'index': spec['id']},
                options=filter_options(df, spec['column']),
                value=(values if spec['mode'] == 'multi'
                       else (values[0] if values else None)),
                multi=spec['mode'] == 'multi',
                clearable=True,
                style={'width': '260px', 'display': 'inline-block',
                       'marginRight': '12px'},
            ),
        ], style={'display': 'inline-block', 'marginBottom': '8px'}))
    return html.Div(controls, style={
        'display': 'flex', 'flexWrap': 'wrap', 'alignItems': 'center',
        'gap': '8px', 'marginBottom': '10px',
    }) if controls else html.Div()


def render_default_page(tab, page, df, chart_df, selected):
    """Draw a tab of the default definition from its own data and wording."""
    children = [html.H3(tab['title'])]
    if tab.get('markdown'):
        children.append(dcc.Markdown(tab['markdown'], dangerously_allow_html=False))
    if page.get('markdown'):
        children.append(dcc.Markdown(page['markdown'], dangerously_allow_html=False))
    children.append(render_definition_filter_controls(
        definition_filters(tab, page, selected), df))
    for graph in page.get('graphs') or []:
        children.append(dcc.Graph(
            id=f"default-{tab['id']}-{page['id']}-{graph['id']}",
            figure=GraphTypes.render_graph(chart_df, graph),
        ))
    return html.Div(children)


def render_xapi_data_tab(data_tab, df):
    """The reserved audit tab: the full flattened view, without dashboard filters."""
    table_df = flatten_for_display(df)
    data = table_df.where(pd.notna(table_df), None).to_dict('records')
    children = []
    if data_tab.get('markdown'):
        children.append(dcc.Markdown(data_tab['markdown'],
                                     dangerously_allow_html=False))
    children.extend([
        html.H3(f"Length table : {len(data)}"),
        dash_table.DataTable(
            id='table-all-xapi-data',
            columns=[{"name": column, "id": column} for column in table_df.columns],
            data=data,
            filter_action='native',
            sort_action="native",
            sort_mode="multi",
        ),
    ])
    return html.Div(children)


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
    Input('config-command', 'data'),
    [State('url-t-mon', 'pathname'), State('url', 'pathname')]
)
def update_tab(style, config_command, stateUrl, app_path=None):
    triggered_prop_id = (dash.callback_context.triggered or [{}])[0].get('prop_id', '')
    if 'config-command' in triggered_prop_id and (config_command or {}).get('config'):
        config = config_command['config']
        header = config.get('header') or {}
        return (
            config.get('active_tab') or None,
            list(header.get('actor.name') or []),
            list(header.get('object.id') or []),
        )
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


def page_filters_from_url(pathname):
    """Read the page filters a link asks for."""
    return decode_filters(get_value_from_url(pathname or "", f"{PAGE_FILTER_PARAM}="))


def new_page_id():
    """A short id for a user-defined page, unique enough for one session."""
    return uuid.uuid4().hex[:10]


def page_key(tab):
    """The item-store key for a tab value."""
    if isinstance(tab, str) and tab.startswith(PAGE_TAB_PREFIX):
        return tab
    return CREATE_TAB_KEY


def page_by_key(pages, key):
    """Find a stored custom page by its tab value or its id."""
    for page in pages or []:
        if not isinstance(page, dict):
            continue
        identifier = str(page.get("id") or "")
        if key in (identifier, f"{PAGE_TAB_PREFIX}{identifier}"):
            return page
    return None


def items_for_key(key, pages, charts, filters):
    """Return the charts and filters held by the active page."""
    page = page_by_key(pages, key)
    if page is not None:
        return list(page.get("charts") or []), list(page.get("filters") or [])
    return list(charts or []), list(filters or [])


def render_filter_controls(filters, target, df):
    """The row of page filters above a page's visualisations."""
    controls = []
    for index, spec in enumerate(filters or []):
        normalised = normalise_filter(spec, df)
        if normalised is None:
            continue
        options = filter_options(df, normalised["column"])
        controls.append(html.Div([
            html.Span(f"{normalised['column']}: ", style={'marginRight': '6px'}),
            dcc.Dropdown(
                id={'type': 'page-filter', 'index': f"{target}:{index}"},
                options=options,
                value=normalised["values"] if normalised["mode"] == "multi"
                else (normalised["values"][0] if normalised["values"] else None),
                multi=normalised["mode"] == "multi",
                clearable=True,
                style={'width': '260px', 'display': 'inline-block',
                       'marginRight': '12px'},
            ),
            html.Button('×', id={'type': 'item-remove', 'index': f'filter:{index}'},
                        n_clicks=0, title=I18n.t('page.delete'),
                        style={'background': 'none', 'border': 'none',
                               'cursor': 'pointer', 'fontSize': '16px'}),
        ], style={'display': 'inline-block', 'marginBottom': '8px'}))
    return html.Div(controls, style={
        'display': 'flex', 'flexWrap': 'wrap', 'alignItems': 'center',
        'gap': '8px', 'marginBottom': '10px',
    }) if controls else html.Div()


def render_item(spec, index, target, df, is_filter=False):
    """One created chart or filter, with its remove button."""
    label = 'Filter' if is_filter else describe(spec)
    return html.Div([
        html.Div([
            html.Span(label, style={'fontFamily': INTER_FONT, 'fontSize': 13,
                                    'marginRight': '10px'}),
            html.Button('Remove', id={'type': 'item-remove',
                                      'index': f'{"filter" if is_filter else "chart"}:{index}'},
                        n_clicks=0,
                        style={'backgroundColor': 'lightgray', 'marginBottom': '5px'}),
        ]),
        dcc.Graph(figure=build_chart(df, spec)),
    ])


def render_add_slot(target):
    """The single empty slot that opens the creation popup."""
    return html.Button('+', id={'type': 'item-add-slot', 'index': target},
                       n_clicks=0, title=I18n.t('visual.open'),
                       style={'width': '72px', 'height': '72px', 'fontSize': '28px',
                              'border': f'2px dashed {BRAND_PRIMARY}',
                              'background': LIGHT_CARD, 'color': BRAND_PRIMARY,
                              'cursor': 'pointer', 'borderRadius': '8px',
                              'margin': '10px'})


def render_page_items(df, charts, filters, target):
    """A page's contents: filter row, charts, then one + slot.

    Returned as a flat list so the layout controls can place each chart on the
    grid instead of treating the whole page as one item.
    """
    items = [render_filter_controls(filters, target, df)]
    for index, spec in enumerate(charts or []):
        items.append(render_item(spec, index, target, df))
    items.append(render_add_slot(target))
    return items


def dashboard_tab_children(pages):
    """Built-in tabs plus the user's named pages, in creation order."""
    tabs = [
        dcc.Tab(id=f'dashboard-tab-{value}', value=value,
                label=dashboard_tab_label(label, icon))
        for value, label, icon in dashboard_tabs()
    ]
    for page in pages or []:
        if not isinstance(page, dict) or not page.get("id"):
            continue
        identifier = str(page["id"])
        tabs.append(dcc.Tab(
            id={'type': 'custom-dashboard-tab', 'index': identifier},
            value=f"{PAGE_TAB_PREFIX}{identifier}",
            label=dashboard_tab_label(str(page.get("name") or I18n.t('page.unnamed')),
                                      'M12 5v14M5 12h14'),
        ))
    return tabs


def current_config(charts, filters, pages, layout, header, hidden, tab):
    """The document exported or saved from the dashboard's current state."""
    return build_document(
        charts=charts, filters=filters, pages=pages, layout=layout,
        header=header, hidden=hidden, active_tab=tab,
    )


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
        Input('config-command', 'data'),
    ],
    [
        State('activity-filter-hidden', 'data'),
        # The URL is read as a State, never as an Input: the dashboard writes its state
        # into the URL, so an Input here would close a loop back into this callback.
        State('url-t-mon', 'pathname'),
    ]
)
def update_activity_filter(button_n_clicks, all_n_clicks, none_n_clicks, lrs_data_version,
                           panel_style, config_command, hidden, pathname):
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
    if 'config-command' in triggered_prop_id and (config_command or {}).get('config'):
        hidden = [str(value) for value in
                  (config_command['config'].get('hidden_activities') or [])]
    elif 'output-t-mon' in triggered_prop_id and panel_style == {"display": "block"}:
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


def _pattern_index(prop_id, suffix):
    """Read the index of the pattern-matching component that triggered a callback."""
    try:
        return json.loads(prop_id.rsplit(suffix, 1)[0])['index']
    except (ValueError, KeyError, IndexError):
        return None


@callback(
    [
        Output('dashboard-pages', 'data'),
        Output('created-charts', 'data'),
        Output('page-filters', 'data'),
        Output('item-status', 'children'),
        Output('chart-creator-status', 'children'),
    ],
    [
        Input('page-add', 'n_clicks'),
        Input('page-rename', 'n_clicks'),
        Input({'type': 'page-delete', 'index': dash.dependencies.ALL}, 'n_clicks'),
        Input('item-add', 'n_clicks'),
        Input({'type': 'item-remove', 'index': dash.dependencies.ALL}, 'n_clicks'),
        Input({'type': 'page-filter', 'index': dash.dependencies.ALL}, 'value'),
        Input('chart-add', 'n_clicks'),
        Input({'type': 'chart-remove', 'index': dash.dependencies.ALL}, 'n_clicks'),
        # A new selection takes the Create tab's state from the link.
        Input('output-t-mon', 'style'),
        Input('config-command', 'data'),
    ],
    [
        State('t-mon-tabs', 'value'),
        State('item-modal-target', 'data'),
        State('page-name-input', 'value'),
        State('item-kind', 'value'),
        State('item-chart-type', 'value'),
        State('item-column', 'value'),
        State('item-game', 'value'),
        State('item-target', 'value'),
        State('item-mode', 'value'),
        State('chart-type', 'value'),
        State('chart-x', 'value'),
        State('chart-y', 'value'),
        State('chart-aggregation', 'value'),
        State('dashboard-pages', 'data'),
        State('created-charts', 'data'),
        State('page-filters', 'data'),
        State('url-t-mon', 'pathname'),
    ]
)
def update_page_state(page_add_n, page_rename_n, page_delete_n, item_add_n,
                      item_remove_n, filter_values, chart_add_n, chart_remove_n,
                      panel_style, config_command, tab, target, page_name,
                      item_kind, item_chart_type, item_column, item_game,
                      item_target, item_mode,
                      chart_type, chart_x, chart_y, chart_aggregation,
                      pages, charts, filters, pathname):
    """
    The single writer of the page, chart and filter stores.

    A user-defined page owns its charts and filters; the built-in Create tab owns
    the two legacy stores. All mutations go through this callback so a store and
    the buttons that draw it cannot disagree.
    """
    triggered = dash.callback_context.triggered
    triggered_prop_id = triggered[0]['prop_id'] if triggered else ''
    pages = [dict(page) for page in (pages or []) if isinstance(page, dict)]
    charts = [spec for spec in (charts or []) if isinstance(spec, dict)]
    filters = [spec for spec in (filters or []) if isinstance(spec, dict)]
    # The tab that is open owns the items, whether or not the popup was used.
    # The modal target is only a hint for where an added item belongs.
    key = page_key(tab)
    target_charts, target_filters = items_for_key(key, pages, charts, filters)
    status = ''

    if 'config-command' in triggered_prop_id and (config_command or {}).get('config'):
        config = config_command['config']
        imported_pages = list((config.get('tabs') or {}).get('custom') or [])
        imported_charts = list((config.get('create_tab') or {}).get('charts') or [])
        imported_filters = list((config.get('create_tab') or {}).get('filters') or [])
        if config_command.get('action') == 'append':
            known_ids = {str(page.get('id')) for page in pages}
            for page in imported_pages:
                page = dict(page)
                identifier = str(page.get('id') or new_page_id())
                if identifier in known_ids:
                    identifier = f"{identifier}-{new_page_id()[:4]}"
                page['id'] = identifier
                known_ids.add(identifier)
                pages.append(page)
            charts = charts + imported_charts
            # Filters describe the view, not a chart: adding the same one twice
            # would narrow nothing twice and clutter the row.
            known_filters = {json.dumps(spec, sort_keys=True) for spec in filters}
            for spec in imported_filters:
                fingerprint = json.dumps(spec, sort_keys=True)
                if fingerprint not in known_filters:
                    filters.append(spec)
                    known_filters.add(fingerprint)
        else:
            pages = imported_pages
            charts = imported_charts
            filters = imported_filters
        status = I18n.t('config.status')
        return (pages[:12], charts[:MAX_CREATED_CHARTS],
                filters[:MAX_PAGE_FILTERS], status, status)

    if 'output-t-mon' in triggered_prop_id and panel_style == {"display": "block"}:
        charts = created_charts_from_url(pathname)
        filters = page_filters_from_url(pathname)
        # The working copies are the ones written back at the end, so a shared
        # link must fill them too rather than being overwritten by stale ones.
        target_charts, target_filters = charts, filters
    elif 'page-add' in triggered_prop_id and int(page_add_n or 0) > 0:
        identifier = new_page_id()
        pages.append({
            'id': identifier,
            'name': str(page_name or f"{I18n.t('page.unnamed')} {len(pages) + 1}"),
            'charts': [], 'filters': [],
        })
        status = I18n.t('visual.added')
    elif 'page-rename' in triggered_prop_id and int(page_rename_n or 0) > 0:
        page = page_by_key(pages, key)
        if page is not None and page_name:
            page['name'] = str(page_name)[:80]
            status = I18n.t('visual.added')
    elif 'page-delete' in triggered_prop_id and page_delete_n and max(page_delete_n) > 0:
        # A single button deletes the page that is open, not a page named by the
        # button's index. The Create tab cannot be deleted.
        active_key = page_key(tab)
        page = page_by_key(pages, active_key)
        if page is not None:
            pages = [candidate for candidate in pages if candidate is not page]
            status = I18n.t('visual.added')
    elif 'item-remove' in triggered_prop_id and item_remove_n and max(item_remove_n) > 0:
        parts = str(_pattern_index(triggered_prop_id, '.n_clicks') or '').split(':')
        if len(parts) == 2 and parts[0] == 'chart':
            index = int(parts[1])
            if 0 <= index < len(target_charts):
                target_charts = target_charts[:index] + target_charts[index + 1:]
        elif len(parts) == 2 and parts[0] == 'filter':
            index = int(parts[1])
            if 0 <= index < len(target_filters):
                target_filters = target_filters[:index] + target_filters[index + 1:]
    elif 'page-filter' in triggered_prop_id and filter_values:
        raw_index = _pattern_index(triggered_prop_id, '.value')
        parts = str(raw_index or '').split(':')
        if len(parts) == 2 and parts[0] == key:
            index = int(parts[1])
            if 0 <= index < len(target_filters):
                spec = dict(target_filters[index])
                spec['values'] = ([value for value in filter_values or [] if value]
                                  if isinstance(filter_values, list)
                                  else [filter_values] if filter_values else [])
                target_filters[index] = normalise_filter(spec) or spec
    elif 'chart-remove' in triggered_prop_id and chart_remove_n and max(chart_remove_n) > 0:
        index = _pattern_index(triggered_prop_id, '.n_clicks')
        if isinstance(index, int) and 0 <= index < len(target_charts):
            target_charts = target_charts[:index] + target_charts[index + 1:]
    elif ('item-add' in triggered_prop_id and int(item_add_n or 0) > 0
          or 'chart-add' in triggered_prop_id and int(chart_add_n or 0) > 0):
        kind = item_kind or 'generic'
        if 'chart-add' in triggered_prop_id:
            spec = normalise_spec({
                'type': chart_type, 'x': chart_x, 'y': chart_y,
                'aggregation': chart_aggregation,
            })
        elif kind in VISUALS:
            spec = normalise_spec({
                'visual': kind, 'game': item_game,
                'target': item_target, 'mode': item_mode,
            })
        elif kind in ('filter-multi', 'filter-single'):
            spec = normalise_filter({
                'column': item_column,
                'mode': 'multi' if kind == 'filter-multi' else 'single',
            })
        else:
            spec = normalise_spec({
                'type': item_chart_type or 'bar', 'x': item_column,
                'y': COUNT_LABEL, 'aggregation': 'count',
            })
        if spec is None:
            status = I18n.t('visual.no_column')
        else:
            is_filter = 'column' in spec and 'mode' in spec
            current_filters = target_filters if is_filter else target_charts
            limit = MAX_PAGE_FILTERS if is_filter else MAX_CREATED_CHARTS
            if len(current_filters) >= limit:
                status = I18n.t('visual.max_filters' if is_filter else 'visual.max_charts')
            elif is_filter:
                target_filters = target_filters + [spec]
                status = I18n.t('visual.added')
            else:
                target_charts = target_charts + [spec]
                status = I18n.t('visual.added')

    if key != CREATE_TAB_KEY:
        page = page_by_key(pages, key)
        if page is not None:
            page['charts'] = target_charts[:MAX_CREATED_CHARTS]
            page['filters'] = target_filters[:MAX_PAGE_FILTERS]
    else:
        charts = target_charts[:MAX_CREATED_CHARTS]
        filters = target_filters[:MAX_PAGE_FILTERS]
    print(f"Pages: {len(pages)} - charts: {len(charts)} - filters: {len(filters)} "
          f"- triggered={triggered_prop_id}")
    return (pages[:12], charts[:MAX_CREATED_CHARTS],
            filters[:MAX_PAGE_FILTERS], status, status)


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
    # The filters of the open page and the named pages the user has made. Both
    # are reads here: the stores have a single writer in update_page_state.
    Input('page-filters', 'data'),
    Input('dashboard-pages', 'data'),
    # Selected values of the dashboard-definition filters. It is dialogue, not
    # user-page state, so changing one redraws only the definition's graphs.
    Input('definition-filters', 'data'),
)
def update_output(tab, user_search_value, user_value, object_search_value, object_value,
                  lrs_data_version=None, hidden_activities=None, created_charts=None,
                  panel_style=None, simlet_name=None, session_name=None,
                  app_path=None, graph_layout='one', graph_rows=3,
                  graph_columns=2, graph_page=1, split_x=2, split_y=2,
                  page_filters=None, dashboard_pages=None, definition_filter_values=None):
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
            or 'activity-filter-hidden' in triggered_prop_id or 'created-charts' in triggered_prop_id
            or 'page-filters' in triggered_prop_id or 'dashboard-pages' in triggered_prop_id
            or 'definition-filters' in triggered_prop_id):
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
            # A user-defined page keeps its own charts and filters in its store
            # entry; the built-in Create tab uses the two legacy stores. Both are
            # resolved here so the page-level filters narrow every chart on the
            # page while the header dropdowns still offer the whole session.
            active_charts, active_filters = items_for_key(
                page_key(tab), dashboard_pages, created_charts, page_filters)
            tab_def, page_def = default_tab_page(tab)
            selected = (definition_filter_values
                        if isinstance(definition_filter_values, dict) else {})
            if tab_def is not None and tab_def['id'] != DefaultDashboard.XAPI_TAB_ID:
                # A default page is narrowed in the ADR's order: statements,
                # header selectors, dashboard filters, tab filters, page filters.
                chart_df = DefaultDashboard.apply_filters(
                    filtered_df, definition_filters(tab_def, page_def, selected))
            elif tab == CREATE_TAB_KEY or tab.startswith(PAGE_TAB_PREFIX):
                chart_df = apply_page_filters(filtered_df, active_filters)
            else:
                chart_df = filtered_df
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
            elif tab_def is not None and tab_def['id'] == DefaultDashboard.XAPI_TAB_ID:
                # The audit tab ignores dashboard filters: it shows the full set
                # of statements the header and activity controls left in view.
                tab_content = render_xapi_data_tab(tab_def, filtered_df)
            elif tab_def is not None and tab_def['id'] == 'create_tab':
                # The Create tab and every user-defined page share one renderer:
                # a row of filters, the named charts, and one + slot to add more.
                tab_content = html.Div([
                    html.H3('Your visualisations'),
                    html.P(
                        "Every chart you create is listed here and drawn from the statements the "
                        "filters leave in the view. Add one with the + button below."
                    ),
                ] + render_page_items(chart_df, active_charts, active_filters,
                                      CREATE_TAB_KEY))
            elif tab_def is not None and page_def is not None:
                tab_content = render_default_page(
                    tab_def, page_def, filtered_df, chart_df, selected)
            elif tab in BUILTIN_TAB_VISUALS:
                # Only reached when the definition file could not be read. The
                # legacy catalogue renderer then supplies the built-in tabs.
                tab_content = render_builtin_tab(chart_df, tab)
            elif tab == 'data_tab':
                # Legacy link to the data tab when running on the fallback tabs.
                tab_content = render_xapi_data_tab(
                    {'markdown': ''}, filtered_df)
            elif tab == 'create_tab':
                # The Create tab and every user-defined page share one renderer:
                # a row of filters, the named charts, and one + slot to add more.
                # They all draw from chart_df, which the page filters narrowed.
                tab_content=html.Div([
                    html.H3('Your visualisations'),
                    html.P(
                        "Every chart you create is listed here and drawn from the statements the "
                        "filters leave in the view. Add one with the + button below."
                    ),
                ] + render_page_items(chart_df, active_charts, active_filters,
                                      CREATE_TAB_KEY))
            elif tab.startswith(PAGE_TAB_PREFIX):
                page = page_by_key(dashboard_pages, tab)
                name = str((page or {}).get('name') or I18n.t('page.unnamed'))
                tab_content=html.Div([html.H3(name)] + render_page_items(
                    chart_df, active_charts, active_filters, tab))
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
            if active_charts:
                # The charts a link carries, in the order they are drawn. Both
                # generic charts and named visualisations are encoded.
                encoded = [encode_spec(spec) for spec in active_charts]
                described = [value for value in encoded if value]
                if described:
                    new_query_params[CREATED_CHARTS_PARAM]=",".join(described)
            filters_in_url = encode_filters(active_filters)
            if filters_in_url:
                # The definition and the selected values travel in the link so
                # a shared page opens with the same narrowed view.
                new_query_params[PAGE_FILTER_PARAM]=filters_in_url
            print(f"Query param url:{new_query_params}")
            # Construct a new query string with unique parameters
            new_query_string = urlencode(new_query_params, safe=" ")
            print(f"new_query_string: {new_query_string}")
            if tab_def is not None and page_def is not None:
                # A definition page carries its own arrangement, or inherits it
                # from its tab and then the dashboard. The UI controls keep their
                # values for user-created pages, where they are the author's tool.
                arrangement = DefaultDashboard.layout_for(
                    page_def.get('layout'), DASHBOARD_DEFINITION, tab_def)
                graph_layout = arrangement['graph-layout']
                graph_rows = arrangement['graph-rows']
                graph_columns = arrangement['graph-columns']
                graph_page = arrangement['graph-page']
                split_x = arrangement['graph-split-x']
                split_y = arrangement['graph-split-y']
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

# One renderer serves every built-in tab. Each mapping names the visuals whose
# source notebooks belong to the tab; their targets are discovered from the
# loaded statements, so the same figure can also be created on a user page.
# The first two headings keep their historical wording for existing links and
# tests; the new ones are translation keys.
BUILTIN_TAB_VISUALS = {
    'progress_tab': {
        'heading': 'Player Progress Throw Serious game',
        'visuals': ('progress-line', 'progress-origin', 'progress-pie'),
    },
    'video_tab': {
        'heading': 'Video Seen/Skipped',
        'visuals': ('video-seen-skipped',),
    },
    'completable_tab': {
        'heading_key': 'visual.group.completables',
        'visuals': ('completable-progress-change', 'completable-progress',
                    'completable-scores', 'completable-times'),
    },
    'alternative_tab': {
        'heading_key': 'visual.group.alternatives',
        'visuals': ('correct-incorrect-by-player', 'correct-incorrect-by-question',
                    'alternatives-selected'),
    },
    'interaction_tab': {
        'heading_key': 'visual.group.interactions',
        'visuals': ('item-interaction-time', 'item-interaction-heatmap',
                    'item-interaction-count', 'item-action-type-count'),
    },
    'accessible_tab': {
        'heading_key': 'visual.group.accessibles',
        'visuals': ('accessible-time', 'accessible-heatmap', 'accessible-count'),
    },
    'menu_tab': {
        'heading_key': 'visual.group.menus',
        'visuals': ('menu-selection-count',),
    },
}

# The deployed JSON file is the source of the default dashboard. The two tables
# above stay available only when that file is missing or invalid, so a bad
# deployment is loud but does not leave the application without any tabs.
try:
    DASHBOARD_DEFINITION = DefaultDashboard.load()
except DefaultDashboard.DashboardDefinitionError as error:
    logging.getLogger(__name__).warning(
        "Default dashboard definition could not be loaded; using compatibility tabs: %s",
        error)
    DASHBOARD_DEFINITION = None

# A tab with many games or levels would become a wall of charts. Four targets
# per tab keep it readable and match the twelve-graph ceiling of a user page.
MAX_BUILTIN_TARGETS = 4
MAX_BUILTIN_FIGURES = 12


def builtin_graph_id(tab, visual, target):
    """A stable Dash id for one built-in figure, unique across tabs and targets."""
    digest = hashlib.sha1(
        f"{tab}|{visual}|{target or ''}".encode('utf-8')).hexdigest()[:12]
    return f"builtin-{visual}-{digest}"


def _figure_has_no_data(figure):
    """Whether a builder returned the shared empty figure rather than a chart."""
    if figure is None or not getattr(figure, 'data', ()):
        return True
    return any(
        'no data' in str(getattr(annotation, 'text', '')).lower()
        for annotation in (getattr(figure.layout, 'annotations', ()) or ())
    )


def render_builtin_tab(df, tab):
    """Draw a built-in tab from the catalogue, one titled figure per target."""
    mapping = BUILTIN_TAB_VISUALS.get(tab)
    if mapping is None:
        return html.Div()
    heading = (I18n.t(mapping['heading_key']) if 'heading_key' in mapping
               else mapping['heading'])
    content = [html.H3(heading)]
    targets_by_kind = {}
    shown = 0
    for visual in mapping['visuals']:
        entry = VISUALS[visual]
        if entry.target_kind:
            if entry.target_kind not in targets_by_kind:
                targets_by_kind[entry.target_kind] = target_ids(df, entry.target_kind)
            targets = targets_by_kind[entry.target_kind][:MAX_BUILTIN_TARGETS]
        else:
            targets = ['']
        if not targets:
            targets = ['']
            empty_tab = True
        else:
            empty_tab = False
        for target in targets:
            spec = {'visual': visual, 'target': target}
            if entry.needs_game:
                spec['game'] = target
            if entry.modes:
                spec['mode'] = entry.modes[0]
            figure = build_named_visual(df, spec)
            content.append(html.H4(describe_named(spec)))
            children = []
            if empty_tab or _figure_has_no_data(figure):
                children.append(html.Span(I18n.t('figure.no-data'),
                                          style={'marginRight': '10px'}))
            children.append(dcc.Graph(
                id=builtin_graph_id(tab, visual, target), figure=figure))
            content.append(html.Div(children))
            shown += 1
            if shown >= MAX_BUILTIN_FIGURES:
                return html.Div(content)
    return html.Div(content)


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


def _is_graph_item(item):
    """A chart is a bare graph or a wrapper holding one (created charts have a
    title and a remove button beside the figure)."""
    if isinstance(item, dcc.Graph):
        return True
    if isinstance(item, html.Div):
        children = item.children
        children = children if isinstance(children, (list, tuple)) else [children]
        return any(_is_graph_item(child) for child in children)
    return False


def _is_add_slot(item):
    """The + button that opens the creation popup."""
    identifier = getattr(item, 'id', None)
    return (isinstance(item, html.Button) and isinstance(identifier, dict)
            and identifier.get('type') == 'item-add-slot')


def arrange_graphs(content, layout, rows, columns, page, split_x=2, split_y=2):
    """
    Lay out a tab's graphs and show at most twelve of them per page.

    Non-graph elements (headings and the filter row) stay above the graphs on the
    first page; the + slot stays below them so a new chart can always be added.
    Created charts are wrappers around a figure, so they count as graphs too.
    """
    node = content
    while isinstance(node, html.Div) and isinstance(node.children, html.Div):
        node = node.children
    items = node.children if isinstance(node.children, (list, tuple)) else [node]
    headings = [item for item in items
                if not _is_graph_item(item) and not _is_add_slot(item)]
    add_slots = [item for item in items if _is_add_slot(item)]
    graphs = [item for item in items if _is_graph_item(item)]
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
    if add_slots:
        # The creation slot is available on every page of the layout, below the
        # charts it belongs to.
        children.extend(add_slots)
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


def visual_kind_options():
    """Grouped choices of the + popup: named visuals, generic charts, filters."""
    groups = [
        {'label': I18n.t(group), 'options': [
            {'label': VISUALS[identifier].label, 'value': identifier}
            for identifier in identifiers
        ]}
        for group, identifiers in GROUPED_VISUALS
    ]
    groups.append({
        'label': I18n.t('visual.group.generic'),
        'options': [{'label': name, 'value': name} for name in CHART_TYPES],
    })
    groups.append({
        'label': I18n.t('visual.group.filters'),
        'options': [
            {'label': I18n.t('visual.mode.multi'), 'value': 'filter-multi'},
            {'label': I18n.t('visual.mode.single'), 'value': 'filter-single'},
        ],
    })
    return groups


def item_modal_layout():
    """The popup opened by a page's + slot to add a chart or a filter."""
    return html.Div(
        id='item-modal', style={'display': 'none', 'position': 'fixed',
                                'top': '15%', 'left': '25%', 'width': '50%',
                                'background': LIGHT_CARD, 'border': f'2px solid {BRAND_PRIMARY}',
                                'borderRadius': '8px', 'padding': '20px', 'zIndex': 2000,
                                'boxShadow': '0 4px 16px rgba(0,0,0,0.2)'},
        children=[
            html.H3(I18n.t('visual.open'), style={'marginTop': 0}),
            dcc.Dropdown(id='item-kind', options=visual_kind_options(),
                         placeholder=I18n.t('visual.open'), clearable=False,
                         style={'marginBottom': '10px'}),
            # The game choice only makes sense for the progress figures, and the
            # column choice only for a generic chart or a filter. A callback
            # shows the pair that the selected kind needs.
            html.Div(id='item-game-div', children=[
                html.Span(I18n.t('visual.game'), style={'marginRight': '6px'}),
                dcc.Dropdown(id='item-game', options=[], clearable=False),
            ], style={'marginBottom': '10px'}),
            html.Div(id='item-column-div', children=[
                html.Span(I18n.t('visual.column'), style={'marginRight': '6px'}),
                dcc.Dropdown(id='item-column', options=[]),
            ], style={'marginBottom': '10px'}),
            # Target-based notebook figures offer the relevant activity ids
            # instead of a column. The callback shows this row only for them.
            html.Div(id='item-target-div', children=[
                html.Span(I18n.t('visual.target'), style={'marginRight': '6px'}),
                dcc.Dropdown(id='item-target', options=[]),
            ], style={'marginBottom': '10px'}),
            # Only the progress-change figure has more than one time mode.
            html.Div(id='item-mode-div', children=[
                html.Span(I18n.t('visual.option'), style={'marginRight': '6px'}),
                dcc.Dropdown(id='item-mode', options=[], clearable=False),
            ], style={'marginBottom': '10px'}),
            # Kept for the state of the legacy generic chart creator.
            dcc.Dropdown(id='item-chart-type', options=[
                {'label': name, 'value': name} for name in CHART_TYPES
            ], value='bar', style={'display': 'none'}),
            html.Div([
                html.Button(I18n.t('visual.add'), id='item-add', n_clicks=0,
                            style={'marginRight': '8px'}),
                html.Button(I18n.t('visual.cancel'), id='item-cancel', n_clicks=0),
                html.Span(id='item-status', children='',
                          style={'marginLeft': '10px', 'color': '#555'}),
            ]),
        ],
    )


def config_confirm_layout():
    """The Replace / Append / Cancel choice shown before an import is applied."""
    return html.Div(
        id='config-confirm-modal',
        style={'display': 'none', 'position': 'fixed', 'top': '25%',
               'left': '35%', 'width': '30%', 'background': LIGHT_CARD,
               'border': f'2px solid {BRAND_PRIMARY}', 'borderRadius': '8px',
               'padding': '20px', 'zIndex': 2000},
        children=[
            html.H3(I18n.t('config.confirm'), style={'marginTop': 0}),
            html.Button(I18n.t('config.replace'), id='config-confirm-replace',
                        n_clicks=0, style={'marginRight': '8px'}),
            html.Button(I18n.t('config.append'), id='config-confirm-append',
                        n_clicks=0, style={'marginRight': '8px'}),
            html.Button(I18n.t('visual.cancel'), id='config-confirm-cancel', n_clicks=0),
        ],
    )


TMonBody=html.Div([
    dcc.Location(id='url-t-mon', refresh=False), # Location component for URL handling
    # Written only when the header language changes; the reload picks up lng.
    dcc.Location(id='i18n-location', refresh=True),
    html.Div(id='output-t-mon', style={'display': 'none'}, children=[
        dcc.Store(id='activity-filter-hidden', data=[]),
        dcc.Store(id='created-charts', data=[]),
        # Named pages and the filters of the open page. The stores have one
        # writer (update_page_state) and many readers, so a chart and the row
        # of filters above it always describe the same view.
        dcc.Store(id='dashboard-pages', data=[]),
        dcc.Store(id='page-filters', data=[]),
        # Selected values of the filters declared by the default dashboard. The
        # definition supplies their labels and columns; this store only holds
        # what the user has chosen in the row above a page's graphs.
        dcc.Store(id='definition-filters',
                  data=(DefaultDashboard.initial_filter_values(DASHBOARD_DEFINITION)
                        if DASHBOARD_DEFINITION else {})),
        # Which page the creation popup belongs to, and the last import waiting
        # for the user to choose Replace, Append or Cancel.
        dcc.Store(id='item-modal-target', data=None),
        dcc.Store(id='config-pending', data=None),
        # A loaded/imported configuration is announced here; callbacks that
        # own a tab, a hidden-activity list, a page or the layout listen to it.
        dcc.Store(id='config-command', data=None),
        dcc.Download(id='config-download'),
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
            # A page is a named tab with its own charts and filters. The name
            # input feeds New page and Rename page; Delete page removes the
            # open one. These controls live in the header so they are reachable
            # whatever visualisation page is being viewed.
            html.Div([
                dcc.Input(id='page-name-input', type='text',
                          placeholder=I18n.t('page.name'),
                          style={'width': '200px', 'marginRight': '6px'}),
                html.Button(I18n.t('page.add'), id='page-add', n_clicks=0,
                            style={'marginRight': '4px'}),
                html.Button(I18n.t('page.rename'), id='page-rename', n_clicks=0,
                            style={'marginRight': '4px'}),
                html.Button(I18n.t('page.delete'),
                            id={'type': 'page-delete', 'index': 'current'},
                            n_clicks=0),
            ], style={'margin': '4px 0'}),
            # Configuration travels either as a downloaded file or as a named
            # save kept on the server for this user. Upload must ask before it
            # replaces what is on screen, hence the confirm popup below.
            html.Div([
                dcc.Input(id='config-name-input', type='text',
                          placeholder=I18n.t('config.name'),
                          style={'width': '180px', 'marginRight': '6px'}),
                html.Button(I18n.t('config.save'), id='config-save', n_clicks=0,
                            style={'marginRight': '4px'}),
                html.Button(I18n.t('config.load'), id='config-load', n_clicks=0,
                            style={'marginRight': '4px'}),
                html.Button(I18n.t('config.delete'), id='config-delete', n_clicks=0,
                            style={'marginRight': '4px'}),
                html.Button(I18n.t('config.refresh'), id='config-refresh', n_clicks=0,
                            style={'marginRight': '4px'}),
                html.Button(I18n.t('config.export'), id='config-export', n_clicks=0,
                            style={'marginRight': '4px'}),
                dcc.Dropdown(id='config-saved-dropdown', options=[], value=None,
                             placeholder=I18n.t('config.load'),
                             style={'width': '200px', 'display': 'inline-block',
                                    'verticalAlign': 'middle', 'marginRight': '6px'}),
                dcc.Upload(id='config-import', children=I18n.t('config.import'),
                           accept='.json,application/json',
                           style={'display': 'inline-block', 'padding': '5px 10px',
                                  'border': f'1px solid {BRAND_PRIMARY}',
                                  'borderRadius': '4px', 'cursor': 'pointer'}),
                html.Span(id='config-status', children='',
                          style={'marginLeft': '10px', 'color': '#555'}),
            ], style={'margin': '4px 0', 'display': 'flex', 'alignItems': 'center',
                      'flexWrap': 'wrap'}),
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
                        for value, label, icon in dashboard_tabs()
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
                item_modal_layout(),
                config_confirm_layout(),
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


# The creation and confirmation popups share one style object each so no two
# callbacks write the same Output property.
_MODAL_VISIBLE = {'display': 'block'}
_MODAL_HIDDEN = {'display': 'none'}


@callback(
    Output('t-mon-tabs', 'children'),
    Input('dashboard-pages', 'data'),
)
def render_dashboard_tabs(pages):
    """Rebuild the tab bar when a named page is added, renamed or imported."""
    return dashboard_tab_children(pages)


@callback(
    Output('definition-filters', 'data'),
    Input({'type': 'definition-filter', 'index': dash.dependencies.ALL}, 'value'),
    State('definition-filters', 'data'),
)
def update_definition_filter_values(values, current):
    """Remember the choice made in one of the dashboard definition's filters."""
    triggered = dash.callback_context.triggered
    if not triggered or not triggered[0].get('prop_id'):
        raise PreventUpdate
    identifier = _pattern_index(triggered[0]['prop_id'], '.value')
    if identifier is None:
        raise PreventUpdate
    value = triggered[0].get('value')
    selected = list(value) if isinstance(value, (list, tuple)) else (
        [value] if value else [])
    updated = dict(current or {})
    updated[str(identifier)] = selected
    return updated


@callback(
    [Output('item-modal', 'style'), Output('item-modal-target', 'data')],
    [
        Input({'type': 'item-add-slot', 'index': dash.dependencies.ALL}, 'n_clicks'),
        Input('item-cancel', 'n_clicks'),
        Input('item-add', 'n_clicks'),
    ],
    [State('t-mon-tabs', 'value')],
)
def toggle_item_modal(slot_clicks, cancel_clicks, add_clicks, tab):
    """Open the + popup for the page whose slot was clicked; close it after an add."""
    triggered = dash.callback_context.triggered
    prop_id = triggered[0]['prop_id'] if triggered else ''
    if 'item-add-slot' in prop_id and any(slot_clicks or []):
        target = _pattern_index(prop_id, '.n_clicks')
        return _MODAL_VISIBLE, str(target) if target else page_key(tab)
    if 'item-add' in prop_id or 'item-cancel' in prop_id:
        return _MODAL_HIDDEN, no_update
    raise PreventUpdate


@callback(
    [
        Output('item-game', 'options'),
        Output('item-column', 'options'),
        Output('item-target', 'options'),
        Output('item-target', 'value'),
        Output('item-mode', 'options'),
        Output('item-mode', 'value'),
        Output('item-game-div', 'style'),
        Output('item-column-div', 'style'),
        Output('item-target-div', 'style'),
        Output('item-mode-div', 'style'),
    ],
    [
        Input('item-kind', 'value'),
        Input('lrs-data-version', 'data'),
        Input('output-t-mon', 'style'),
    ],
)
def update_item_modal_fields(kind, lrs_version, panel_style):
    """Offer the games, targets, modes and columns the selected visual needs."""
    if panel_style != {'display': 'block'} or not TMonWidgets.xapiData:
        return ([], [], [], None, [], None,
                _MODAL_HIDDEN, _MODAL_HIDDEN, _MODAL_HIDDEN, _MODAL_HIDDEN)
    df = pd.json_normalize(TMonWidgets.xapiData)
    df = resolve_actor_name_column(df)
    games = [{'label': game, 'value': game} for game in game_ids(df)]
    columns = [{'label': column, 'value': column}
               for column in filterable_columns(df)]

    entry = VISUALS.get(kind)
    targets = []
    target_value = None
    if entry is not None and entry.target_kind and not entry.needs_game:
        identifiers = target_ids(df, entry.target_kind)
        targets = [{'label': short_label(identifier), 'value': identifier}
                   for identifier in identifiers]
        target_value = identifiers[0] if identifiers else None

    modes = []
    mode_value = None
    if entry is not None and entry.modes:
        modes = [{'label': I18n.t(f'visual.mode.{mode}'), 'value': mode}
                 for mode in entry.modes]
        mode_value = entry.modes[0]

    game_style = _MODAL_VISIBLE if entry is not None and entry.needs_game else _MODAL_HIDDEN
    column_style = (_MODAL_VISIBLE if kind in CHART_TYPES
                    or kind in ('filter-multi', 'filter-single') else _MODAL_HIDDEN)
    target_style = (_MODAL_VISIBLE if targets or entry is not None and entry.target_kind
                    and not entry.needs_game else _MODAL_HIDDEN)
    mode_style = _MODAL_VISIBLE if entry is not None and entry.modes else _MODAL_HIDDEN
    return (games, columns, targets, target_value, modes, mode_value,
            game_style, column_style, target_style, mode_style)


@callback(
    [
        Output('graph-layout', 'value'),
        Output('graph-rows', 'value'),
        Output('graph-columns', 'value'),
        Output('graph-page', 'value'),
        Output('graph-split-x', 'value'),
        Output('graph-split-y', 'value'),
    ],
    [Input('config-command', 'data')],
)
def apply_config_layout(command):
    """Restore the layout controls carried by an imported configuration."""
    if not command or not command.get('config'):
        raise PreventUpdate
    layout = command['config'].get('layout') or {}
    return tuple(layout.get(key, no_update) for key in LAYOUT_KEYS)


@callback(
    [
        Output('config-download', 'data'),
        Output('config-command', 'data'),
        Output('config-pending', 'data'),
        Output('config-confirm-modal', 'style'),
        Output('config-saved-dropdown', 'options'),
        Output('config-status', 'children'),
    ],
    [
        Input('config-export', 'n_clicks'),
        Input('config-save', 'n_clicks'),
        Input('config-import', 'contents'),
        Input('config-load', 'n_clicks'),
        Input('config-delete', 'n_clicks'),
        Input('config-refresh', 'n_clicks'),
        Input('config-confirm-replace', 'n_clicks'),
        Input('config-confirm-append', 'n_clicks'),
        Input('config-confirm-cancel', 'n_clicks'),
        Input('output-t-mon', 'style'),
    ],
    [
        State('config-name-input', 'value'),
        State('config-saved-dropdown', 'value'),
        State('config-pending', 'data'),
        State('created-charts', 'data'),
        State('page-filters', 'data'),
        State('dashboard-pages', 'data'),
        State('t-mon-tabs', 'value'),
        State('graph-layout', 'value'),
        State('graph-rows', 'value'),
        State('graph-columns', 'value'),
        State('graph-page', 'value'),
        State('graph-split-x', 'value'),
        State('graph-split-y', 'value'),
        State('users-multi-dynamic-dropdown', 'value'),
        State('object-multi-dynamic-dropdown', 'value'),
        State('activity-filter-hidden', 'data'),
    ],
)
def handle_config_actions(export_n, save_n, import_contents, load_n, delete_n,
                          refresh_n, replace_n, append_n, cancel_n, panel_style,
                          name, selected, pending, charts, filters, pages, tab,
                          graph_layout, graph_rows, graph_columns, graph_page,
                          split_x, split_y, users, objects, hidden):
    """Export, save, load, delete and import a dashboard configuration."""
    triggered = dash.callback_context.triggered
    prop_id = triggered[0]['prop_id'] if triggered else ''

    def result(status='', command=no_update, pending_value=no_update,
               options=no_update, download=no_update, modal=no_update):
        return (download, command, pending_value, modal, options, status)

    def document():
        return current_config(
            charts, filters, pages,
            {
                'graph-layout': graph_layout, 'graph-rows': graph_rows,
                'graph-columns': graph_columns, 'graph-page': graph_page,
                'graph-split-x': split_x, 'graph-split-y': split_y,
            },
            {'actor.name': users or [], 'object.id': objects or []},
            hidden or [], tab,
        )

    if 'config-export' in prop_id and int(export_n or 0) > 0:
        return result(
            download={'content': serialize_config(document()),
                      'filename': 'tmon-dashboard.json'},
            status=I18n.t('config.status'),
        )
    if 'config-save' in prop_id and int(save_n or 0) > 0:
        try:
            safe = save_named(name or 'dashboard', document())
            status = f"{I18n.t('config.status')}: {safe}"
        except ValueError as error:
            status = str(error)
        return result(status=status,
                      options=[{'label': item, 'value': item}
                               for item in list_saved()])
    if 'config-import' in prop_id and import_contents:
        try:
            parsed = import_config(import_contents)
        except ValueError as error:
            return result(status=str(error), modal=_MODAL_HIDDEN)
        return result(pending_value=parsed, modal=_MODAL_VISIBLE)
    if 'config-load' in prop_id and int(load_n or 0) > 0:
        if not selected:
            return result(status=I18n.t('config.name'))
        try:
            parsed = load_named(selected)
        except ValueError as error:
            return result(status=str(error))
        return result(
            command={'action': 'replace', 'config': parsed,
                     'nonce': uuid.uuid4().hex},
            status=I18n.t('config.status'),
        )
    if 'config-delete' in prop_id and int(delete_n or 0) > 0:
        if selected:
            try:
                delete_named(selected)
            except ValueError as error:
                return result(status=str(error))
        return result(
            status=I18n.t('config.status'),
            options=[{'label': item, 'value': item} for item in list_saved()],
        )
    if ('config-confirm-replace' in prop_id and int(replace_n or 0) > 0
            or 'config-confirm-append' in prop_id and int(append_n or 0) > 0):
        action = 'replace' if 'config-confirm-replace' in prop_id else 'append'
        if not pending:
            return result(modal=_MODAL_HIDDEN)
        return result(
            command={'action': action, 'config': pending,
                     'nonce': uuid.uuid4().hex},
            pending_value=None, modal=_MODAL_HIDDEN,
            status=I18n.t('config.status'),
        )
    if 'config-confirm-cancel' in prop_id and int(cancel_n or 0) > 0:
        return result(pending_value=None, modal=_MODAL_HIDDEN)
    if 'output-t-mon' in prop_id and panel_style == {'display': 'block'}:
        return result(options=[{'label': item, 'value': item}
                               for item in list_saved()])
    raise PreventUpdate
