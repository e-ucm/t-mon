import base64
import logging
import re
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
    MAX_TOTAL_FILTERS,
    PAGE_FILTER_PARAM,
    apply_page_filters,
    decode_filters,
    encode_filters,
    filter_options,
    filterable_columns,
    normalise_filter,
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
from TMonWidgets.UserRoles import is_admin
from urllib.parse import unquote, urlencode
from datetime import datetime
import uuid

# Query parameter carrying the activities left out of the view. The name is deliberately
# not `activity`: get_value_from_url matches substrings, so `activity=` would also be
# found inside `hidden-activity=` and would read back the wrong value.
HIDDEN_ACTIVITIES_PARAM = "hidden-activity"

# A user-defined visualisation page is a tab whose value starts with this prefix;
PAGE_TAB_PREFIX = "page:"

# Edit mode reveals the controls that change a dashboard: removing a tab or a
# visualisation, adding a tab, and editing a graph with its labels. In view mode the
# same nodes stay in the layout with display:none, so Dash ids exist on first render.
NEW_TAB_ADD_ID = "new-tab-add"


def edit_control_style(edit_mode):
    """Visibility shared by the first render and every later callback."""
    return {'display': 'block'} if edit_mode else {'display': 'none'}


def edit_button_style(edit_mode, margin='0'):
    """Small inline button style for a control that only exists in edit mode."""
    return {
        'display': 'inline-block' if edit_mode else 'none',
        'background': 'none', 'border': 'none', 'cursor': 'pointer',
        'color': BRAND_PRIMARY, 'fontSize': '14px', 'margin': margin,
    }

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
    """The tab bar of the deployed dashboard, or the compatibility tabs.

    Returns an empty list: T-Mon no longer ships default dashboard tabs
    (Progress, Videos, etc.). Users create their own tabs and pages.
    Only home_tab and create_tab are available as built-in system tabs.
    """
    return []


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


def render_default_page(tab, page, df, chart_df, selected, edit_mode=False,
                        admin=False, overrides=None, show_filters=True):
    """Draw a tab of the default definition from its own data and wording.

    An administrator in edit mode gets an Edit control on every graph the chart
    builder can redraw. A saved override replaces the figure but never the
    deployed JSON, so other users keep seeing the definition as written.
    """
    children = [html.H3(tab['title'])]
    if tab.get('markdown'):
        children.append(dcc.Markdown(tab['markdown'], dangerously_allow_html=False))
    if page.get('markdown'):
        children.append(dcc.Markdown(page['markdown'], dangerously_allow_html=False))
    if show_filters:
        children.append(render_definition_filter_controls(
            definition_filters(tab, page, selected), df))
    for graph in page.get('graphs') or []:
        key = default_graph_key(tab['id'], page['id'], graph['id'])
        override = (overrides or {}).get(key)
        figure = (build_chart(chart_df, override) if override
                  else GraphTypes.render_graph(chart_df, graph))
        node = dcc.Graph(
            id=f"default-{tab['id']}-{page['id']}-{graph['id']}",
            figure=figure,
        )
        if edit_mode and admin and default_graph_spec(graph) is not None:
            label = describe(override) if override else (
                graph.get('title') or str(graph.get('id')))
            node = html.Div([
                html.Div([
                    html.Span(label, style={'fontFamily': INTER_FONT,
                                            'fontSize': 13,
                                            'marginRight': '10px'}),
                    html.Button(I18n.t('edit.item'),
                                id={'type': 'default-graph-edit', 'index': key},
                                n_clicks=0, title=I18n.t('edit.graph'),
                                style=edit_button_style(True, margin='0 0 5px 0')),
                ]),
                node,
            ])
        children.append(node)
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


def url_output(panel_style, query_string, current_pathname=None):
    """
    The URL to publish from the dashboard, or ``no_update`` while it is hidden.

    The query string is appended to the current pathname so a tab redirect
    keeps the simlet/session path: ``/simlet/1/session/2/dashboard/ss`` becomes
    ``/simlet/1/session/2/dashboard/ss?tab=home_tab`` instead of replacing the
    last path segment with ``tab=home_tab``. Duplicate slashes in the base path
    are collapsed so ``dashboard//s`` never leaks into the redirect.
    """
    if panel_style == {'display': 'block'}:
        base = current_pathname.split('?')[0] if current_pathname else ''
        # Collapse duplicate slashes so ``dashboard//s`` never leaks into the
        # redirect (e.g. /simlet/1/session/1/dashboard//s?tab=home_tab).
        base = re.sub(r'/+', '/', base)
        return base + '?' + query_string
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

def _dashboard_name(dashboard):
    """Read a display name from a string or a config document."""
    if isinstance(dashboard, str):
        return dashboard
    if isinstance(dashboard, dict):
        for key in ("name", "title", "dashboard", "id"):
            value = dashboard.get(key)
            if value:
                return str(value)
    return str(dashboard)


def render_dashboard_tiles(dashboards, simlet_id=None, session_id=None):
    """
    Render a grid of dashboard tiles using TMON.figcraft design tokens.

    Each tile links to the dashboard named by the entry, so a session can
    expose several dashboards side by side (ADR 0025).

    Args:
        dashboards (list): Dashboard names or configuration documents.
        simlet_id: Optional simlet id used to build the dashboard URL.
        session_id: Optional session id used to build the dashboard URL.

    Returns:
        html.Div: A grid of dashboard tiles.
    """
    if not dashboards:
        return html.Div(I18n.t('dashboard.no_dashboards'),
                        style={'fontFamily': INTER_FONT, 'padding': '20px'})

    tiles = []
    for i, dashboard in enumerate(dashboards):
        name = _dashboard_name(dashboard)
        if simlet_id and session_id:
            href = f"/simlet/{simlet_id}/session/{session_id}/dashboard/{name}"
        elif simlet_id:
            href = f"/simlet/{simlet_id}/dashboard/{name}"
        else:
            href = f"/dashboard/{name}"

        # Remove button on non-default tiles (ADR 0025).
        remove_button = None
        if name != 'default':
            remove_index = (
                f"simlet_id:{simlet_id or ''}|session_id:{session_id or ''}|name:{name}"
                if (simlet_id is not None or session_id is not None)
                else f"name:{name}"
            )
            remove_button = html.Button(
                '×',
                id={'type': 'dashboard-remove', 'index': remove_index},
                n_clicks=0,
                title=I18n.t('dashboard.remove'),
                className='dashboard-remove-btn',
                style={
                    'background': 'rgba(240, 118, 103, 0.1)', 'border': 'none',
                    'color': '#f07667', 'cursor': 'pointer',
                    'fontSize': 20, 'fontWeight': 'bold',
                    'padding': '0',
                    'width': '24px', 'height': '24px',
                    'display': 'flex', 'alignItems': 'center', 'justifyContent': 'center',
                    'position': 'absolute', 'top': '8px', 'right': '8px',
                    'zIndex': 10,
                    'borderRadius': '4px',
                    'lineHeight': '1',
                })

        tile_content = html.Div([
            html.Div(
                name,
                style={
                    'fontFamily': INTER_FONT,
                    'fontSize': 14,
                    'fontWeight': '500',
                    'color': DARK_BACKGROUND,
                    'padding': '12px',
                    'height': '44px',
                    'boxSizing': 'border-box',
                    'display': 'flex',
                    'alignItems': 'center',
                    'whiteSpace': 'nowrap',
                    'overflow': 'hidden',
                    'textOverflow': 'ellipsis',
                    'borderBottom': '1px solid rgba(0,0,0,0.1)',
                }
            ),
            html.Div(
                I18n.t('dashboard.open'),
                style={
                    'fontFamily': INTER_FONT,
                    'fontSize': 12,
                    'color': TEXT_SECONDARY,
                    'padding': '8px 12px',
                }
            ),
        ],
            style={
                'backgroundColor': LIGHT_CARD,
                'border': '1px solid rgba(0,0,0,0.1)',
                'borderRadius': 8,
                'width': f'{SIMLET_TILE_WIDTH}px',
                'height': '120px',
                'boxSizing': 'border-box',
            }
        )

        if remove_button is not None:
            tile = html.Div([
                html.A(
                    tile_content,
                    href=href,
                    style={'textDecoration': 'none', 'color': 'inherit', 'height': '100%', 'display': 'block'},
                ),
                remove_button,
            ],
                style={
                    'display': 'inline-block',
                    'verticalAlign': 'top',
                    'margin': f'{SIMLET_TILE_MARGIN}px',
                    'position': 'relative',
                })
        else:
            tile = html.A(
                tile_content,
                href=href,
                style={'textDecoration': 'none', 'color': 'inherit', 'height': '100%', 'display': 'inline-block',
                       'verticalAlign': 'top', 'margin': f'{SIMLET_TILE_MARGIN}px'},
            )
        tiles.append(tile)

        if (i + 1) % 4 == 0 and i < len(dashboards) - 1:
            tiles.append(html.Div(style={'clear': 'both'}))

    # [+] tile to create a new dashboard (ADR 0025).
    add_index = (
        f"simlet_id:{simlet_id or ''}|session_id:{session_id or ''}"
        if (simlet_id is not None or session_id is not None)
        else 'new'
    )
    tiles.append(html.Button(
        '+',
        id={'type': 'dashboard-add', 'index': add_index},
        n_clicks=0,
        title=I18n.t('dashboard.new'),
        style={
            'width': f'{SIMLET_TILE_WIDTH}px',
            'height': '120px',
            'margin': f'{SIMLET_TILE_MARGIN}px',
            'backgroundColor': LIGHT_CARD,
            'border': f'2px dashed {BRAND_PRIMARY}',
            'borderRadius': 8,
            'fontSize': 32,
            'color': BRAND_PRIMARY,
            'cursor': 'pointer',
            'display': 'inline-block',
            'verticalAlign': 'top',
        }))

    return html.Div(tiles, style={'padding': '20px'})


# Aliases used by different callers.
render_dashboard_cards = render_dashboard_tiles
render_dashboards = render_dashboard_tiles


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
    [
        Output('t-mon-tabs', 'value'),
        Output('config-command', 'data', allow_duplicate=True),
    ],
    Input('output-t-mon', 'style'),
    Input('config-command', 'data'),
    [State('url-t-mon', 'pathname'), State('url', 'pathname')],
    prevent_initial_call=True,
)
def update_tab(style, config_command, stateUrl, app_path=None):
    triggered_prop_id = (dash.callback_context.triggered or [{}])[0].get('prop_id', '')
    if 'config-command' in triggered_prop_id and (config_command or {}).get('config'):
        config = config_command['config']
        header = config.get('header') or {}
        return (
            config.get('active_tab') or None,
            no_update,
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
        config_command_value = no_update
        if dashboard_data and urlValues:
            if urlValues == "default":
                # The default dashboard keeps its tab selected even for a session,
                # so `/dashboard/default` opens the default dashboard rather than
                # the session's no-tab view.
                new_tab = get_value_from_url(urlValues, "tab=") or "home_tab"
            elif get_value_from_url(urlValues, "tab=") is not None:
                new_tab = get_value_from_url(urlValues, "tab=")
            else:
                # Any other segment names a saved dashboard: load it and apply it.
                name = urlValues.split("&", 1)[0].strip()
                try:
                    parsed = load_named(name)
                except (ValueError, OSError):
                    parsed = None
                if isinstance(parsed, dict):
                    new_tab = parsed.get("active_tab") or "home_tab"
                    config_command_value = {
                        "action": "replace", "config": parsed,
                        "nonce": uuid.uuid4().hex,
                    }
                else:
                    new_tab = "home_tab"
        else:
            new_tab = "home_tab"
        # A session dashboard with no dashboard name in the URL opens with no
        # tab selected: the page shows the simlet/session names first. An
        # explicit name (`default` or a saved dashboard) opens that dashboard.
        if (app_path and '/session/' in app_path and '/dashboard' in app_path
                and (not urlValues or urlValues == "")):
            print(f"Session dashboard: no tab selected ({app_path})")
            return None, no_update
        tab = new_tab
        print(f"Tab: {tab} - URL : {urlValues}")
        return tab, config_command_value
    else:
        raise PreventUpdate


@callback(
    [Output('dashboard-create-modal', 'style'),
     Output('dashboard-create-context', 'data'),
     Output('dashboard-redirect', 'href')],
    [Input({'type': 'dashboard-add', 'index': dash.dependencies.ALL}, 'n_clicks'),
     Input('dashboard-create-cancel', 'n_clicks'),
     Input('dashboard-create-submit', 'n_clicks')],
    [State('dashboard-create-name', 'value'),
     State('dashboard-create-context', 'data'),
     State('url-t-mon', 'pathname')],
    prevent_initial_call=True,
)
def handle_dashboard_create_modal(add_clicks, cancel_n, submit_n, name, context, pathname):
    triggered = (dash.callback_context.triggered or [{}])[0].get('prop_id', '')
    hidden = {'display': 'none', 'position': 'fixed', 'inset': 0,
              'zIndex': 10000, 'justifyContent': 'center',
              'alignItems': 'center', 'backgroundColor': 'rgba(0,0,0,0.4)'}
    visible = {'display': 'flex', 'position': 'fixed', 'inset': 0,
               'zIndex': 10000, 'justifyContent': 'center',
               'alignItems': 'center', 'backgroundColor': 'rgba(0,0,0,0.4)'}
    if 'dashboard-create-submit' in triggered:
        if submit_n and name:
            # Read simlet_id/session_id from the store (set when "+" was clicked),
            # falling back to the URL pathname.
            simlet_id = (context or {}).get('simlet_id')
            session_id = (context or {}).get('session_id')
            if simlet_id is None and session_id is None and pathname and '/simlet/' in pathname:
                parts = pathname.strip('/').split('/')
                if len(parts) >= 2 and parts[0] == 'simlet':
                    simlet_id = parts[1]
                    if len(parts) >= 4 and parts[2] == 'session':
                        session_id = parts[3]
            try:
                save_named(str(name).strip(), build_document(),
                           simlet_id=simlet_id, session_id=session_id)
            except Exception:
                pass
            if simlet_id and session_id:
                return hidden, {}, f"/simlet/{simlet_id}/session/{session_id}/dashboard/{str(name).strip()}"
            elif simlet_id:
                return hidden, {}, f"/simlet/{simlet_id}/dashboard/{str(name).strip()}"
            else:
                return hidden, {}, f"/dashboard/{str(name).strip()}"
        return hidden, {}, dash.no_update
    if 'dashboard-create-cancel' in triggered:
        return hidden, {}, dash.no_update
    if any(int(click or 0) > 0 for click in (add_clicks or [])):
        # Store the simlet_id/session_id from the clicked "+" button's index,
        # so the dashboard is saved at the location nearest the closest session.
        simlet_id = None
        session_id = None
        prop_id = (dash.callback_context.triggered or [{}])[0].get('prop_id', '')
        if 'dashboard-add' in prop_id:
            try:
                btn_id = __import__('json').loads(prop_id.rsplit('.n_clicks', 1)[0])
                idx = btn_id.get('index', '')
                if isinstance(idx, str) and '|' in idx:
                    for part in idx.split('|'):
                        if ':' in part:
                            k, v = part.split(':', 1)
                            if v:
                                if k == 'simlet_id':
                                    simlet_id = v
                                elif k == 'session_id':
                                    session_id = v
            except Exception:
                pass
        # Fall back to URL pathname if the button index didn't carry context.
        if (simlet_id is None and session_id is None) and pathname and '/simlet/' in pathname:
            parts = pathname.strip('/').split('/')
            if len(parts) >= 2 and parts[0] == 'simlet':
                simlet_id = parts[1]
                if len(parts) >= 4 and parts[2] == 'session':
                    session_id = parts[3]
        return visible, {'simlet_id': simlet_id, 'session_id': session_id}, dash.no_update
    raise PreventUpdate


@callback(
    Output('dashboard-redirect', 'href', allow_duplicate=True),
    Input({'type': 'dashboard-remove', 'index': dash.dependencies.ALL}, 'n_clicks'),
    [State('url-t-mon', 'pathname'),
     State('url', 'pathname')],
    prevent_initial_call=True,
)
def delete_dashboard(remove_n_clicks, pathname, url_pathname):
    """Delete a saved dashboard from its tile and refresh the page."""
    if not any(int(click or 0) > 0 for click in remove_n_clicks):
        raise PreventUpdate

    triggered = (dash.callback_context.triggered or [{}])[0].get('prop_id', '')
    try:
        btn_id = __import__('json').loads(triggered.rsplit('.n_clicks', 1)[0])
        idx = btn_id.get('index', '')
    except Exception:
        raise PreventUpdate

    simlet_id = None
    session_id = None
    dname = None
    if isinstance(idx, str) and '|' in idx:
        for part in idx.split('|'):
            if ':' in part:
                k, v = part.split(':', 1)
                if v:
                    if k == 'simlet_id':
                        simlet_id = v
                    elif k == 'session_id':
                        session_id = v
                    elif k == 'name':
                        dname = v
    elif isinstance(idx, str) and idx.startswith('name:'):
        dname = idx[len('name:'):]

    if not dname:
        raise PreventUpdate

    try:
        delete_named(dname, simlet_id=simlet_id, session_id=session_id)
    except Exception:
        pass

    effective_path = pathname if (pathname and '/simlet/' in pathname) else url_pathname
    if not effective_path:
        effective_path = '/'
    if simlet_id and session_id:
        redirect = f"/simlet/{simlet_id}/session/{session_id}"
    elif simlet_id:
        redirect = f"/simlet/{simlet_id}"
    else:
        redirect = "/dashboard/"
    return redirect



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
    return None


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
    """Return the charts and filters held by the active page.

    A store may hold a scalar instead of a list if a config was hand-edited or
    imported from an older version; coerce to a list so unpacking never fails on
    an ``int`` or other scalar.
    """
    def as_list(value):
        return list(value) if isinstance(value, list) else []
    page = page_by_key(pages, key)
    if page is not None:
        return as_list(page.get("charts")), as_list(page.get("filters"))
    return as_list(charts), as_list(filters)


def default_graph_key(tab_id, page_id, graph_id):
    """A stable key for one graph defined by the default dashboard."""
    return f"{tab_id}:{page_id}:{graph_id}"


def default_graph_spec(graph):
    """
    Turn a default-dashboard graph definition into a chart spec.

    Only the types the chart builder can draw are editable through the popup, so
    a heatmap or a table comes back as None and keeps its definition untouched.
    """
    if not isinstance(graph, dict) or graph.get("type") not in CHART_TYPES:
        return None
    x = (graph.get("x") or {}).get("data")
    if not x:
        return None
    y = (graph.get("y") or {}).get("data")
    if not y or y == "count":
        y = COUNT_LABEL
    spec = {
        "type": graph["type"],
        "x": x,
        "y": y,
        "aggregation": (graph.get("aggregation")
                        or ("count" if y == COUNT_LABEL else "mean")),
    }
    for key, value in (("title", graph.get("title")),
                       ("x_label", (graph.get("x") or {}).get("label")),
                       ("y_label", (graph.get("y") or {}).get("label"))):
        if value:
            spec[key] = str(value)
    return normalise_spec(spec)


def find_default_graph(key, dashboard=None):
    """Return the graph definition a ``tab:page:graph`` key names."""
    if dashboard is None:
        dashboard = DASHBOARD_DEFINITION
    if dashboard is None:
        try:
            dashboard = DefaultDashboard.load()
        except Exception:  # noqa: BLE001 - a missing definition is not an edit
            return None
    tab_id, _, rest = str(key or "").partition(":")
    page_id, _, graph_id = rest.partition(":")
    for tab in (dashboard or {}).get("tabs") or []:
        if str(tab.get("id")) != tab_id:
            continue
        for page in tab.get("pages") or []:
            if str(page.get("id")) != page_id:
                continue
            for graph in page.get("graphs") or []:
                if str(graph.get("id")) == graph_id:
                    return graph
    return None


def _default_edit_key(edit_index):
    """The graph key an edit is for, or None when it edits a created chart."""
    raw = str((edit_index or {}).get("index") or "")
    return raw[len("default:"):] if raw.startswith("default:") else None


def render_filter_controls(filters, target, df, edit_mode=True,
                           include_add_slot=True):
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
                        n_clicks=0, title=I18n.t('edit.remove'),
                        style={'background': 'none', 'border': 'none',
                               'cursor': 'pointer', 'fontSize': '16px',
                               'display': 'inline-block' if edit_mode else 'none'}),
            html.Button(I18n.t('edit.item'), id={'type': 'item-edit',
                                               'index': f'filter:{index}'},
                        n_clicks=0, title=I18n.t('edit.filter'),
                        style=edit_button_style(edit_mode)),
        ], style={'display': 'inline-block', 'marginBottom': '8px'}))
    if edit_mode and include_add_slot:
        controls = list(controls) + [html.Button('+', id={'type': 'item-add-slot',
                                                          'index': target},
                                                  n_clicks=0,
                                                  title=I18n.t('visual.open'),
                                                  style={'width': '32px',
                                                         'height': '32px',
                                                         'fontSize': '18px',
                                                         'border': f'2px dashed {BRAND_PRIMARY}',
                                                         'background': LIGHT_CARD,
                                                         'color': BRAND_PRIMARY,
                                                         'cursor': 'pointer',
                                                         'borderRadius': '6px',
                                                         'display': 'block'})]
    return html.Div(controls, style={
        'display': 'flex', 'flexWrap': 'wrap', 'alignItems': 'center',
        'gap': '8px', 'marginBottom': '10px',
    }) if controls else html.Div()


def render_item(spec, index, target, df, is_filter=False, edit_mode=True):
    """One created chart or filter, with its remove and edit buttons."""
    label = 'Filter' if is_filter else describe(spec)
    kind = 'filter' if is_filter else 'chart'
    return html.Div([
        html.Div([
            html.Span(label, style={'fontFamily': INTER_FONT, 'fontSize': 13,
                                    'marginRight': '10px'}),
            html.Button(I18n.t('edit.remove'), id={'type': 'item-remove',
                                                   'index': f'{kind}:{index}'},
                        n_clicks=0, title=I18n.t('edit.remove'),
                        style={'backgroundColor': 'lightgray', 'marginBottom': '5px',
                               'display': 'inline-block' if edit_mode else 'none'}),
            html.Button(I18n.t('edit.item'), id={'type': 'item-edit',
                                                 'index': f'{kind}:{index}'},
                        n_clicks=0, title=I18n.t('edit.graph' if kind == 'chart'
                                                else 'edit.filter'),
                        style=edit_button_style(edit_mode, margin='0 0 5px 4px')),
        ]),
        dcc.Graph(figure=build_chart(df, spec)),
    ])


def render_add_slot(target, edit_mode=True):
    """The single empty slot that opens the creation popup."""
    return html.Button('+', id={'type': 'item-add-slot', 'index': target},
                       n_clicks=0, title=I18n.t('visual.open'),
                       style={'width': '72px', 'height': '72px', 'fontSize': '28px',
                              'border': f'2px dashed {BRAND_PRIMARY}',
                              'background': LIGHT_CARD, 'color': BRAND_PRIMARY,
                              'cursor': 'pointer', 'borderRadius': '8px',
                              'margin': '10px',
                              'display': 'block' if edit_mode else 'none'})


def render_page_items(df, charts, filters, target, edit_mode=True,
                      show_filters=True):
    """A page's contents: charts, then one + slot.

    Filters are rendered in the dashboard's top bar (render_top_filter_bar),
    not here.
    """
    items = []
    for index, spec in enumerate(charts or []):
        items.append(render_item(spec, index, target, df, edit_mode=edit_mode))
    items.append(render_add_slot(target, edit_mode))
    return items


def dashboard_tab_children(pages, edit_mode=False):
    """HomePage, the user-defined tabs, then the new-tab +.

    The + is the last tab entry, after the built-in and all user pages. It
    stays in the DOM in view mode
    so its callback output always has a component to write to; the tab and its
    button are hidden until edit mode is on.
    """
    tabs = []
    # HomePage is the only built-in system tab; every other tab is a page the
    # user made (saved dashboard), so dashboards no longer open on an empty
    # "Create" canvas.
    tabs.append(dcc.Tab(id='dashboard-tab-home_tab', value='home_tab',
                        label=dashboard_tab_label('HomePage',
                            'M3 11l9-8 9 8v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z')))
    # The xAPI data table is always available in edit mode so administrators can
    # inspect raw statements.
    if edit_mode:
        tabs.append(dcc.Tab(id='dashboard-tab-xapi_data',
                            value=DefaultDashboard.XAPI_TAB_ID,
                            label=dashboard_tab_label(
                                'xAPI Data',
                                'M4 4h16v16H4zM4 10h16M10 4v16')))
    for page in pages or []:
        if not isinstance(page, dict) or not page.get("id"):
            continue
        identifier = str(page["id"])
        label = dashboard_tab_label(
            str(page.get("name") or I18n.t('page.unnamed')),
            page.get("icon", DEFAULT_TAB_ICON_PATH))
        if edit_mode:
            label.children = list(label.children) + [
                html.Button('×', id={'type': 'tab-remove', 'index': identifier},
                            n_clicks=0, title=I18n.t('edit.remove_tab'),
                            style=edit_button_style(True, margin='0 0 0 6px')),
            ]
        tabs.append(dcc.Tab(
            id={'type': 'custom-dashboard-tab', 'index': identifier},
            value=f"{PAGE_TAB_PREFIX}{identifier}",
            label=label,
        ))
    # The + is always the last tab, after the built-ins and every user page,
    # including pages added after the dashboard was first rendered.
    tabs.append(dcc.Tab(
        id='new-tab-add-tab',
        disabled=True,
        value='__new_tab__',
        style=edit_control_style(edit_mode),
        label=html.Button('+', id=NEW_TAB_ADD_ID, n_clicks=0,
                          title=I18n.t('edit.new_tab'),
                          style={'display': 'block' if edit_mode else 'none',
                                 'width': '100%',
                                 'border': f'1px dashed {BRAND_PRIMARY}',
                                 'background': LIGHT_CARD, 'color': BRAND_PRIMARY,
                                 'fontSize': '18px', 'cursor': 'pointer'}),
    ))
    return tabs


def current_config(charts, filters, pages, layout, header, hidden, tab,
                   default_overrides=None):
    """The document exported or saved from the dashboard's current state."""
    return build_document(
        charts=charts, filters=filters, pages=pages, layout=layout,
        header=header, hidden=hidden, active_tab=tab,
        default_graph_overrides=default_overrides,
    )


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


@callback(
    Output('dashboard-filter-bar', 'children'),
    [
        Input('t-mon-tabs', 'value'),
        Input('dashboard-pages', 'data'),
        Input('page-filters', 'data'),
        Input('definition-filters', 'data'),
        Input('activity-filter-hidden', 'data'),
        Input('lrs-data-version', 'data'),
        Input('edit-mode', 'data'),
        Input('output-t-mon', 'style'),
    ],
)
def render_top_filter_bar(tab, pages, filters, selected, hidden, lrs_version,
                          edit_mode, panel_style):
    """All filters of the open page, in the dashboard's top bar.

    Definition filters apply to all tabs of the dashboard or to one tab only;
    user filters belong to the open page. They share one row so a reader can
    see exactly what narrows the charts, with a filter + at the end in edit
    mode while the page has fewer than MAX_TOTAL_FILTERS filters.
    """
    if not TMonWidgets.xapiData or not tab:
        return html.Div()
    df = pd.json_normalize(TMonWidgets.xapiData)
    df = resolve_actor_name_column(df)
    df, _ = filter_df_by_activities(df, hidden or [])
    tab_def, page_def = default_tab_page(tab)
    definition_specs = definition_filters(tab_def, page_def, selected or {})
    key = page_key(tab)
    user_filters = items_for_key(key, pages, [], filters)[1]
    controls = []
    if definition_specs:
        controls.extend(render_definition_filter_controls(
            definition_specs, df).children)
    if user_filters:
        controls.append(render_filter_controls(
            user_filters, key, df, bool(edit_mode), include_add_slot=False))
    if edit_mode and key and (len(definition_specs) + len(user_filters)
                      < MAX_TOTAL_FILTERS):
        controls.append(html.Button(
            '+', id={'type': 'filter-add-slot', 'index': key}, n_clicks=0,
            title=I18n.t('filter.add'),
            style={'width': '32px', 'height': '32px', 'fontSize': '18px',
                   'border': f'2px dashed {BRAND_PRIMARY}',
                   'background': LIGHT_CARD, 'color': BRAND_PRIMARY,
                   'cursor': 'pointer', 'borderRadius': '6px'},
        ))
    return html.Div(controls, style={'display': 'flex', 'flexWrap': 'wrap',
                                     'alignItems': 'center', 'gap': '8px'})


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
    ],
    [
        Input('page-add', 'n_clicks'),
        Input('page-rename', 'n_clicks'),
        Input({'type': 'page-delete', 'index': dash.dependencies.ALL}, 'n_clicks'),
        Input('item-add', 'n_clicks'),
        Input({'type': 'item-remove', 'index': dash.dependencies.ALL}, 'n_clicks'),
        Input({'type': 'page-filter', 'index': dash.dependencies.ALL}, 'value'),
        # A new selection takes the Create tab's state from the link.
        Input('output-t-mon', 'style'),
        Input('config-command', 'data'),
        # Edit mode: a confirmed tab removal and the always-visible new tab.
        Input({'type': 'tab-remove', 'index': dash.dependencies.ALL}, 'n_clicks'),
        Input('tab-remove-confirm', 'n_clicks'),
        Input(NEW_TAB_ADD_ID, 'n_clicks'),
    ],
    [
        State('t-mon-tabs', 'value'),
        State('edit-floater-target', 'data'),
        State('page-name-input', 'value'),
        State('page-icon-input', 'value'),
        State('item-kind', 'value'),
        State('item-chart-type', 'value'),
        State('item-column', 'value'),
        State('item-game', 'value'),
        State('item-target', 'value'),
        State('item-mode', 'value'),
        State('dashboard-pages', 'data'),
        State('created-charts', 'data'),
        State('page-filters', 'data'),
        State('url-t-mon', 'pathname'),
        # Which tab or item the edit-mode controls are acting on. Added after the
        # existing states so old direct callers keep their positional arguments.
        State('tab-remove-pending', 'data'),
        State('item-edit-index', 'data'),
        State('item-title', 'value'),
        State('item-xlabel', 'value'),
        State('item-ylabel', 'value'),
        State('item-y', 'value'),
        State('item-aggregation', 'value'),
    ]
)
def update_page_state(page_add_n, page_rename_n, page_delete_n, item_add_n,
                      item_remove_n, filter_values, panel_style, config_command,
                      # Dash passes every Input before every State. These three
                      # belong here, with the other Inputs, not after the States.
                      tab_remove_clicks, confirm_remove_n, new_tab_n,
                      tab, target, page_name, page_icon,
                      item_kind, item_chart_type, item_column, item_game,
                      item_target, item_mode,
                      pages, charts, filters, pathname,
                      pending_remove=None, item_edit_index=None,
                      item_title=None, item_xlabel=None, item_ylabel=None,
                      item_y=None, item_aggregation=None):
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
    has_data = False

    if 'config-command' in triggered_prop_id and (config_command or {}).get('config'):
        config = config_command['config']
        imported_pages = list((config.get('tabs') or {}).get('custom') or [])
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
            # Filters describe the view, not a chart: adding the same one twice
            # would narrow nothing twice and clutter the row.
            known_filters = {json.dumps(spec, sort_keys=True) for spec in filters}
        else:
            pages = imported_pages
        status = I18n.t('config.status')
        return (pages[:12], charts[:MAX_CREATED_CHARTS],
                filters[:MAX_PAGE_FILTERS], status)

    if ('tab-remove-confirm' in triggered_prop_id
            and int(confirm_remove_n or 0) > 0 and pending_remove):
        # Only user-defined pages can be removed: built-in and reserved tabs have
        # no remove control, and the guard keeps a forged id from deleting them.
        removed = str(pending_remove)
        if removed not in (DefaultDashboard.XAPI_TAB_ID,):
            pages = [page for page in pages if str(page.get('id')) != removed]
            status = I18n.t('config.status')
        return (pages[:12], charts[:MAX_CREATED_CHARTS],
                filters[:MAX_PAGE_FILTERS], status, status)

    if 'output-t-mon' in triggered_prop_id and panel_style == {"display": "block"}:
        charts = created_charts_from_url(pathname)
        filters = page_filters_from_url(pathname)
        # The working copies are the ones written back at the end, so a shared
        # link must fill them too rather than being overwritten by stale ones.
        target_charts, target_filters = charts, filters
    elif ('page-add' in triggered_prop_id and int(page_add_n or 0) > 0
          or NEW_TAB_ADD_ID in triggered_prop_id and int(new_tab_n or 0) > 0):
        # The header button and the + always shown in edit mode create the same
        # empty named page, so there is only one creation path to maintain.
        identifier = new_page_id()
        pages.append({
            'id': identifier,
            'name': str(page_name or f"{I18n.t('page.unnamed')} {len(pages) + 1}"),
            'icon': page_icon or DEFAULT_TAB_ICON_PATH,
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
    elif ('item-add' in triggered_prop_id and int(item_add_n or 0) > 0
          and not _default_edit_key(item_edit_index)):
        # A default graph is edited into the override store, not into the page's
        # charts, so this writer leaves the stores exactly as they were.
        kind = item_kind or 'generic'
        labels = {'title': item_title, 'x_label': item_xlabel,
                  'y_label': item_ylabel}
        if kind in ('filter-multi', 'filter-single'):
            spec = normalise_filter({
                'column': item_column,
                'mode': 'multi' if kind == 'filter-multi' else 'single',
            })
        else:
            # The floater's chosen chart type is the kind itself. The hidden
            # item-chart-type keeps the other creation paths working.
            chart_kind = kind if kind in CHART_TYPES else (item_chart_type or 'bar')
            spec = normalise_spec({
                'type': chart_kind, 'x': item_column,
                'y': item_y or COUNT_LABEL,
                'aggregation': item_aggregation or 'count',
                **labels,
            })
        if spec is None:
            status = I18n.t('visual.no_column')
        else:
            is_filter = 'column' in spec and 'mode' in spec
            current = target_filters if is_filter else target_charts
            limit = MAX_PAGE_FILTERS if is_filter else MAX_CREATED_CHARTS
            edit = item_edit_index if isinstance(item_edit_index, dict) else {}
            edit_kind, separator, raw_index = str(edit.get('index') or '').partition(':')
            if separator and edit_kind in ('chart', 'filter'):
                # Editing replaces the item in place; the cap that applies to an
                # add does not reject changing one that is already there.
                try:
                    index = int(raw_index)
                except ValueError:
                    index = -1
                if 0 <= index < len(current):
                    current[index] = spec
                    status = I18n.t('visual.added')
                else:
                    status = I18n.t('visual.no_column')
                if is_filter:
                    target_filters = current
                else:
                    target_charts = current
            elif is_filter and (len(current) + len(definition_filters(
                    *default_tab_page(tab), {})) >= MAX_TOTAL_FILTERS):
                # Definition filters (all-tabs and this-tab) count towards the
                # same per-page cap as the ones a user adds.
                status = I18n.t('visual.max_filters')
            elif len(current) >= limit:
                status = I18n.t('visual.max_filters' if is_filter else 'visual.max_charts')
            elif is_filter:
                target_filters = current + [spec]
                status = I18n.t('visual.added')
            else:
                target_charts = current + [spec]
                status = I18n.t('visual.added')

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
            filters[:MAX_PAGE_FILTERS], status)


def filterObjectIdDependingTab(df, value, tab):
    """Filter object ids by the activity type defined in the tab definition.

    Reads the ``object_filter`` field from the tab definition in
    DASHBOARD_DEFINITION instead of hardcoding tab ids to activity types.
    """
    tab_def, _ = default_tab_page(tab)
    object_type = None
    if tab_def is not None:
        object_type = tab_def.get("object_filter")
    if object_type is not None:
        vals = df.loc[df["object.definition.type"] == object_type]["object.id"].unique()
    else:
        vals = value
    return vals

@callback(
    [
        Output('url-t-mon', 'pathname'),
        Output('tabs-content', 'children'),
     ],
     Input('t-mon-tabs', 'value'),
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
    State('url-t-mon', 'pathname'),
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
    # Entering or leaving edit mode changes which controls the page renders.
    Input('edit-mode', 'data'),
    # An administrator's edits of the default graphs, applied instead of the
    # definition's own figure without rewriting the deployed JSON file.
    Input('default-graph-overrides', 'data'),
)
def update_output(tab, lrs_data_version=None, hidden_activities=None, created_charts=None,
                  panel_style=None, simlet_name=None, session_name=None,
                  app_path=None, graph_layout='one', graph_rows=3,
                  graph_columns=2, graph_page=1, split_x=2, split_y=2,
                  page_filters=None, dashboard_pages=None, definition_filter_values=None,
                  edit_mode=False, default_overrides=None, current_pathname=None):
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
        return (no_update, content)

    def publish_url(query):
        # An uploaded file is local to this page; writing a relative tab query
        # would replace `/dashboard/upload` in the URL and reset the tab on the
        # next load. Leave the dashboard URL alone in that mode.
        if app_path and '/dashboard/upload' in app_path:
            return no_update
        return url_output(panel_style, query, current_pathname)
    # Normalize the JSON data to a pandas DataFrame
    if ('t-mon-tabs' in triggered_prop_id or 'lrs-data-version' in triggered_prop_id
            or 'activity-filter-hidden' in triggered_prop_id or 'created-charts' in triggered_prop_id
            or 'page-filters' in triggered_prop_id or 'dashboard-pages' in triggered_prop_id
            or 'definition-filters' in triggered_prop_id or 'edit-mode' in triggered_prop_id
            or 'default-graph-overrides' in triggered_prop_id):
        # Default empty values when no statements are available.
        df = pd.DataFrame()
        filtered_df = pd.DataFrame()
        activity_ids = []
        active_charts, active_filters = [], []
        tab_def, page_def = None, None
        selected = (definition_filter_values
                    if isinstance(definition_filter_values, dict) else {})
        chart_df = pd.DataFrame()
        has_data = False

        if app_path:
            # Even when no data is available yet, parse charts/filters from URL
            # so they persist in the page for when data arrives later.
            active_charts = created_charts_from_url(app_path)
            active_filters = page_filters_from_url(app_path)

        if len(TMonWidgets.xapiData) > 0:
            df = pd.json_normalize(TMonWidgets.xapiData)
            df = resolve_actor_name_column(df)
            # Narrow the data to the activities that are on before anything reads it, so
            # the charts, the table and the choice lists of the dropdowns all describe
            # the same view instead of the whole session.
            df, activity_ids = filter_df_by_activities(df, hidden_activities)
            # The dashboard's own filters (definition filters and page filters)
            # narrow the view from here on; there is no header selector dictating
            # a second narrowing on the same columns.
            filtered_df = df
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
            elif tab.startswith(PAGE_TAB_PREFIX):
                chart_df = apply_page_filters(filtered_df, active_filters)
            else:
                chart_df = filtered_df
            has_data = True

        if tab == 'home_tab':
            # The simlet grid lives in the SIMVA browser's studies list,
            # never in a dashboard. A local upload has no SimVA studies.
            tab_content = html.Div(render_homepage_content())
        elif len(df) == 0 and has_data:
            # Deactivating the last activity empties the view on purpose. Say so
            # rather than opening a tab of empty charts with no hint why. The link
            # still carries the choice, since that is what brings the view back.
            new_query_params = {'tab': tab}
            if hidden_activities:
                new_query_params[HIDDEN_ACTIVITIES_PARAM] = ",".join(hidden_activities)
            return (
                publish_url(urlencode(new_query_params)),
                html.Div(html.Div([
                    html.H3('No activity is on'),
                    html.P(
                        f"All {len(activity_ids)} activities of this session are deactivated, so there "
                        "is nothing to plot. Use the All button above to bring them back."
                    ),
                ])),
            )
        elif tab_def is not None and tab_def['id'] == DefaultDashboard.XAPI_TAB_ID:
            # The audit tab ignores dashboard filters: it shows the full set
            # of statements the header and activity controls left in view.
            tab_content = render_xapi_data_tab(tab_def, filtered_df)
        elif tab == 'data_tab':
            # Legacy link to the data tab when running on the fallback tabs.
            tab_content = render_xapi_data_tab(
                {'markdown': ''}, filtered_df)
        elif tab == 'create_tab':
            # The Create tab is an empty canvas: show the visualisations heading
            # so the user knows where their charts appear, even with no data yet.
            tab_content = html.Div(
                [html.H3('Your visualisations')]
                + render_page_items(
                    chart_df, active_charts, active_filters, tab, edit_mode,
                    show_filters=False))
        elif tab == DefaultDashboard.XAPI_TAB_ID:
            # xAPI data table is always available in edit mode so administrators
            # can inspect raw statements. Load the definition directly since
            # DASHBOARD_DEFINITION may be None.
            xapi_def = DefaultDashboard.load().get("xapi_data_tab", {})
            tab_content = render_xapi_data_tab(xapi_def, filtered_df)
        elif tab_def is not None:
            # Only render default definition tabs that the user has saved
            # in their dashboard pages. User-created dashboards start empty;
            # default tabs (Progress, Videos, etc.) are not shown unless the
            # user explicitly adds them.
            saved_page_ids = {p.get("id") for p in (dashboard_pages or [])}
            if tab_def.get("id") in saved_page_ids:
                # A default definition tab (progress, video, etc.) uses the
                # render_default_page renderer with its own graphs and filters.
                tab_content = render_default_page(
                    tab_def, page_def, filtered_df, chart_df, selected,
                    edit_mode=edit_mode, admin=is_admin(),
                    overrides=default_overrides, show_filters=False)
            else:
                tab_content = html.Div()
        elif tab.startswith(PAGE_TAB_PREFIX):
            page = page_by_key(dashboard_pages, tab)
            name = str((page or {}).get('name') or I18n.t('page.unnamed'))
            tab_content=html.Div([html.H3(name)] + render_page_items(
                chart_df, active_charts, active_filters, tab, edit_mode,
                show_filters=False))
        else:
            tab_content = html.Div()
        new_query_params = { 'tab': tab }
        if hidden_activities and len(hidden_activities)>0:
            # Only written when something is hidden, so a link to a whole session
            # stays the short one it is without the parameter.
            new_query_params[HIDDEN_ACTIVITIES_PARAM]=",".join(hidden_activities)
        if active_charts:
            # The charts a link carries, in the order they are drawn.
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
        # Changing tabs in edit mode must not churn the URL: publishing a new
        # query string here would re-run the URL sync and drop the tab the
        # user just chose, which made the dashboard look stuck on the previous
        # tab.
        if 't-mon-tabs' in triggered_prop_id:
            published_url = no_update
        else:
            published_url = publish_url(new_query_string)
        return (published_url, tab_content)
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
    ('data_tab', 'xAPI Data', 'M4 4h16v16H4zM4 10h16M10 4v16')
]

# The deployed JSON file is the sole source of the default dashboard's graphs.
# The tab ids above stay available only when that file is missing or invalid, so
# a bad deployment is loud but does not leave the application without any tabs.
try:
    DASHBOARD_DEFINITION = DefaultDashboard.load()
except DefaultDashboard.DashboardDefinitionError as error:
    logging.getLogger(__name__).warning(
        "Default dashboard definition could not be loaded; using compatibility tabs: %s",
        error)
    DASHBOARD_DEFINITION = None

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
        if isinstance(item, str):
            continue
        # Dash components have no `style` attribute at all until one is set,
        # so the title (a plain H3) must be given one here to span the grid.
        item.style = dict(getattr(item, 'style', None) or {},
                          gridColumn='1 / -1')
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
        # The creation slots follow the layout: a one-graph layout shows one
        # large +, a 1 x 2 grid shows two + side by side. An empty new page
        # fills every cell of its layout with a + so there is something to
        # click straight away. Each copy gets its own id so Dash can tell
        # which + was pressed; the page key is kept before the '|' separator.
        import copy
        template = add_slots[-1]
        raw_target = str((getattr(template, 'id', None) or {}).get('index', ''))
        slot_count = page_size if not graphs else max(1, page_size - len(shown))
        copies = []
        for index in range(slot_count):
            button = copy.deepcopy(template)
            button.n_clicks = 0
            button.id = {'type': 'item-add-slot',
                         'index': f"{raw_target}|{index}" if slot_count > 1
                         else raw_target}
            style = dict(button.style or {})
            if not graphs:
                # An empty new page shows its slots even before edit mode.
                style['display'] = 'block'
            if not graphs or (columns_n == 1 and slot_count == 1):
                # A new page, or a single-column layout, gets a full-cell
                # affordance instead of the small in-grid button.
                style.update({'width': '100%', 'height': '180px',
                              'fontSize': '40px'})
            button.style = style
            copies.append(button)
        children.extend(copies)
    if not graphs:
        # An empty page has no "x of y" line to show.
        return html.Div(children, style=grid)
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
    """Grouped choices of the + popup: generic charts and filters."""
    return [
        {
            'label': I18n.t('visual.group.generic'),
            'options': [{'label': name, 'value': name} for name in CHART_TYPES],
        },
        {
            'label': I18n.t('visual.group.filters'),
            'options': [
                {'label': I18n.t('visual.mode.multi'), 'value': 'filter-multi'},
                {'label': I18n.t('visual.mode.single'), 'value': 'filter-single'},
            ],
        },
    ]


def edit_floater_create_panel():
    """The create/edit form, keeping the ids the mutation callbacks already use."""
    return html.Div(
        id='edit-floater-create', style={'display': 'none'},
        children=[
            html.H3(I18n.t('visual.open'), id='item-modal-title',
                    style={'marginTop': 0}),
            dcc.Dropdown(id='item-kind', options=visual_kind_options(),
                         value='bar',
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
            html.Div(id='item-value-div', children=[
                html.Span(I18n.t('visual.y'), style={'marginRight': '6px'}),
                dcc.Dropdown(id='item-y', options=[], style={'marginRight': '8px'}),
                dcc.Dropdown(id='item-aggregation',
                             options=[{'label': label, 'value': name}
                                      for name, label in AGGREGATION_LABELS.items()],
                             value='count', clearable=False),
            ], style={'display': 'none', 'marginBottom': '10px'}),
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
            # User-authored wording lives on the graph spec, not in i18n. These
            # inputs are shown for charts (creation and editing alike) and hidden
            # for filters, which have no graph labels.
            html.Div(id='item-labels-div', children=[
                html.Div([
                    html.Span(I18n.t('edit.label.title'),
                              style={'marginRight': '6px'}),
                    dcc.Input(id='item-title', type='text',
                              placeholder=I18n.t('edit.label.title'),
                              style={'width': '100%', 'marginBottom': '6px'}),
                ]),
                html.Div([
                    html.Span(I18n.t('edit.label.x'), style={'marginRight': '6px'}),
                    dcc.Input(id='item-xlabel', type='text',
                              placeholder=I18n.t('edit.label.x'),
                              style={'width': '100%', 'marginBottom': '6px'}),
                ]),
                html.Div([
                    html.Span(I18n.t('edit.label.y'), style={'marginRight': '6px'}),
                    dcc.Input(id='item-ylabel', type='text',
                              placeholder=I18n.t('edit.label.y'),
                              style={'width': '100%', 'marginBottom': '6px'}),
                ]),
            ], style={'display': 'none', 'marginBottom': '10px'}),
            html.Div([
                html.Button(I18n.t('visual.add'), id='item-add', n_clicks=0,
                            style={'marginRight': '8px'}),
                html.Button(I18n.t('visual.cancel'), id='item-cancel', n_clicks=0),
                html.Span(id='item-status', children='',
                          style={'marginLeft': '10px', 'color': '#555'}),
            ]),
        ],
    )


def edit_floater_pages_panel():
    """Page title and layout together, used on create and on Edit page.

    The page name (title), icon and the graph layout are one panel: a new page is
    created with the same controls used to rename and rearrange an existing one
    (ADR 0024).
    """
    label_style = {'fontSize': 12, 'marginRight': '4px'}
    ICON_OPTIONS = [
        ('M12 5v14M5 12h14', 'Document'),
        ('M12 2L2 7l10 5 10-5-10-5z', 'Chart'),
        ('M2 12h20l-5-5-5-5-5 5-5 5z', 'Bar Chart'),
        ('M12 2L2 12l10 10 10-10z', 'Pie Chart'),
        ('M2 3h20v14H2z', 'Table'),
        ('M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z', 'Chart Circle'),
        ('M14 2H6c-1.1 0-1.99.9-1.99 2L4 14c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm0-3h-3V6h2V5H8V3H6v6H2v2h18V8H6z', 'Dashboard'),
        ('M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-1 16H6v-2h12v2zm0-4H6V8l6 4 6-4v6z', 'Board'),
        ('M5 5h14v3H5zM5 9h14v5H5zM5 16h14v3H5z', 'Layers'),
    ]
    return html.Div(
        id='edit-floater-pages', style={'display': 'none'},
        children=[
            html.H3(I18n.t('edit.page'), style={'marginTop': 0}),
            html.Div([
                html.Span(I18n.t('page.name'), style={'marginRight': '6px'}),
                dcc.Input(id='page-name-input', type='text',
                          placeholder=I18n.t('page.name'),
                          style={'width': '200px', 'marginRight': '6px'}),
                html.Span(I18n.t('page.icon'), style={'marginRight': '6px'}),
                dcc.Dropdown(
                    id='page-icon-input',
                    options=[{'label': label, 'value': path}
                             for path, label in ICON_OPTIONS],
                    value=DEFAULT_TAB_ICON_PATH,
                    clearable=False,
                    style={'width': '160px', 'marginRight': '6px'}),
                html.Button(I18n.t('page.add'), id='page-add', n_clicks=0,
                            style={'marginRight': '4px'}),
                html.Button(I18n.t('page.rename'), id='page-rename', n_clicks=0,
                            style={'marginRight': '4px'}),
                html.Button(I18n.t('page.delete'),
                            id={'type': 'page-delete', 'index': 'current'},
                            n_clicks=0),
            ], style={'marginBottom': '12px',
                      'borderBottom': f'1px solid {BRAND_SOFT}',
                      'paddingBottom': '10px'}),
            html.Div(id='edit-floater-layout-section', children=[
                html.H3(I18n.t('edit.layout'), style={'marginTop': 0}),
                html.Div([
                    html.Span(I18n.t('graphs.layout'), style=label_style),
                    dcc.Dropdown(
                        id='graph-layout', clearable=False, value='one',
                        options=[{'label': I18n.t(key), 'value': value}
                                 for value, key in GRAPH_LAYOUT_OPTIONS],
                        style={'width': '150px', 'marginRight': '10px'}),
                    html.Span(I18n.t('graphs.rows'), style=label_style),
                    dcc.Input(id='graph-rows', type='number', min=1,
                              max=MAX_GRAPHS_PER_PAGE, value=3,
                              style={'width': '60px', 'marginRight': '10px'}),
                    html.Span(I18n.t('graphs.columns'), style=label_style),
                    dcc.Input(id='graph-columns', type='number', min=1,
                              max=MAX_GRAPHS_PER_PAGE, value=2,
                              style={'width': '60px', 'marginRight': '10px'}),
                    html.Span(I18n.t('graphs.page'), style=label_style),
                    dcc.Input(id='graph-page', type='number', min=1, value=1,
                              style={'width': '60px'}),
                    html.Span(I18n.t('graphs.split_x'), style=label_style),
                    dcc.Input(id='graph-split-x', type='number', min=0,
                              max=MAX_GRAPHS_PER_PAGE, value=2,
                              style={'width': '60px', 'marginRight': '10px'}),
                    html.Span(I18n.t('graphs.split_y'), style=label_style),
                    dcc.Input(id='graph-split-y', type='number', min=0,
                              max=MAX_GRAPHS_PER_PAGE, value=2,
                              style={'width': '60px'}),
                ]),
            ]),
        ],
    )


def edit_floater_config_panel():
    """The Get/load/export configuration panel of the floater (ADR 0024)."""
    return html.Div(
        id='edit-floater-config', style={'display': 'none'},
        children=[
            html.H3(I18n.t('edit.config'), style={'marginTop': 0}),
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
            ]),
        ],
    )


def edit_floater_layout():
    """The simva-front floating window: backdrop, centred card and × close.

    The DOM mirrors `partials/iframe.ejs` and the `.iframe_floating` rules of
    simva-front: a fixed full-viewport container, a `.backdrop`, a `.floater`
    card (width `calc(100vw - 32px)`, white, rounded, scrollable), the close
    button in its top-right corner, and the form content with a 48px top
    padding. Styles are inline because a deployed proxy may not serve
    `/assets/...` (ADR 0011); the class names keep the structure recognisable
    (ADR 0024).
    """
    return html.Div(
        id='edit-floater',
        className='iframe_floating new_element floating',
        style={'display': 'none', 'position': 'fixed', 'inset': 0,
               'zIndex': 9999, 'justifyContent': 'center',
               'alignItems': 'center'},
        children=[
            # .backdrop
            html.Div(className='backdrop', style={
                'position': 'fixed', 'inset': 0,
                'background': 'rgba(0,0,0,0.5)', 'zIndex': 0,
            }),
            # .floater
            html.Div(
                id='edit-floater-card', className='floater',
                style={'position': 'relative', 'zIndex': 1,
                       'width': 'calc(100vw - 32px)',
                       'display': 'flex', 'flexDirection': 'column',
                       'background': '#fff', 'borderRadius': '8px',
                       'overflow': 'hidden', 'height': 'auto',
                       'maxHeight': 'calc(100vh - 32px)'},
                children=[
                    # .iframe_floating_close — top-right of the card
                    html.Button(
                        '×', id='edit-floater-close', n_clicks=0,
                        className='iframe_floating_close',
                        **{'aria-label': 'Close'},
                        style={'position': 'absolute', 'top': '8px',
                               'right': '8px', 'zIndex': 10,
                               'fontSize': '1.4rem', 'lineHeight': 1,
                               'width': '32px', 'height': '32px',
                               'display': 'flex', 'alignItems': 'center',
                               'justifyContent': 'center', 'border': 'none',
                               'borderRadius': '4px', 'background': 'none',
                               'cursor': 'pointer', 'color': '#666'},
                    ),
                    # .iframe_content — where simva-front injects its forms
                    html.Div(
                        id='edit-floater-body', className='iframe_content',
                        style={'display': 'flex', 'flexDirection': 'column',
                               'flex': '1 1 auto', 'minHeight': 0,
                               'overflow': 'auto',
                               'padding': '48px 20px 20px 20px'},
                        children=[
                            edit_floater_create_panel(),
                            edit_floater_pages_panel(),
                            edit_floater_config_panel(),
                        ],
                    ),
                ],
            ),
        ],
    )


@callback(
    Output('item-modal-title', 'children'),
    [Input('item-edit-index', 'data')],
    [State('item-kind', 'value')],
)
def update_item_modal_title(edit_index, kind):
    """Rename the popup when it edits an existing item instead of adding one."""
    if not isinstance(edit_index, dict) or not edit_index.get('index'):
        return I18n.t('visual.open')
    index = str(edit_index['index'])
    if index.startswith('filter:') or kind in ('filter-multi', 'filter-single'):
        return I18n.t('edit.filter')
    return I18n.t('edit.visualisation')


@callback(
    Output('item-kind', 'options'),
    [Input('item-edit-index', 'data')],
)
def update_item_kind_options(edit_index):
    """Drop the group labels when editing an existing item.

    The "Generic charts" / "Filters" headings only help when choosing a kind
    from scratch; an edit already knows what it is editing, so a flat list is
    clearer and avoids implying a fresh choice.
    """
    if isinstance(edit_index, dict) and edit_index.get('index'):
        options = [{'label': name, 'value': name} for name in CHART_TYPES]
        options += [
            {'label': I18n.t('visual.mode.multi'), 'value': 'filter-multi'},
            {'label': I18n.t('visual.mode.single'), 'value': 'filter-single'},
        ]
        return options
    return visual_kind_options()


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


def tab_remove_confirm_layout():
    """The confirmation shown before a named tab with content is removed."""
    return html.Div(
        id='tab-remove-confirm-modal',
        style={'display': 'none', 'position': 'fixed', 'top': '30%',
               'left': '35%', 'width': '30%', 'background': LIGHT_CARD,
               'border': f'2px solid {BRAND_PRIMARY}', 'borderRadius': '8px',
               'padding': '20px', 'zIndex': 2000},
        children=[
            html.H3(I18n.t('edit.remove_tab'), style={'marginTop': 0}),
            html.P(I18n.t('edit.confirm_tab')),
            html.Button(I18n.t('edit.remove'), id='tab-remove-confirm',
                        n_clicks=0, style={'marginRight': '8px'}),
            html.Button(I18n.t('visual.cancel'), id='tab-remove-cancel', n_clicks=0),
        ],
    )


# Floater for creating a new named dashboard (ADR 0025).
def dashboard_create_modal_layout():
    return html.Div(
        html.Div([
            html.H3(I18n.t('dashboard.new'), style={'fontFamily': INTER_FONT}),
            dcc.Input(id='dashboard-create-name', type='text',
                      placeholder=I18n.t('dashboard.name'),
                      style={'width': '100%', 'margin': '8px 0'}),
            html.Div([
                html.Button(I18n.t('dashboard.create'),
                            id='dashboard-create-submit', n_clicks=0,
                            style={'marginRight': '8px'}),
                html.Button(I18n.t('visual.cancel'),
                            id='dashboard-create-cancel', n_clicks=0),
            ], style={'marginTop': '8px'}),
        ], style={'backgroundColor': '#fff', 'padding': '16px',
                 'borderRadius': '8px', 'width': '320px'}),
        id='dashboard-create-modal',
        style={'display': 'none', 'position': 'fixed', 'inset': 0,
               'zIndex': 10000, 'justifyContent': 'center',
               'alignItems': 'center', 'backgroundColor': 'rgba(0,0,0,0.4)'},
    )


TMonBody=html.Div([
    dcc.Location(id='url-t-mon', refresh=False), # Location component for URL handling
    dcc.Location(id='dashboard-redirect', refresh=True),
    dcc.Store(id='dashboard-create-context', data={}),
    # Written only when the header language changes; the reload picks up lng.
    dcc.Location(id='i18n-location', refresh=True),
    # Standalone simva-front-style overlay at the app level: it lives outside
    # output-t-mon so it is above the whole page, not only the dashboard.
    edit_floater_layout(),
    dashboard_create_modal_layout(),
    html.Div(id='output-t-mon', style={'display': 'none'}, children=[
        dcc.Store(id='activity-filter-hidden', data=[]),
        dcc.Store(id='created-charts', data=[]),
        # Edit mode and the item/tab being changed. They are transient UI state:
        # only the mutations they enable are saved in an ADR 0015 configuration.
        dcc.Store(id='edit-mode', data=False),
        dcc.Store(id='item-edit-index', data=None),
        dcc.Store(id='tab-remove-pending', data=None),
        # An administrator's overrides of the graphs in the default definition,
        # keyed by tab:page:graph. The deployed JSON file is never modified.
        dcc.Store(id='default-graph-overrides', data={}),
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
        # Which page the floater acts on, which of its panels is open, and the
        # last import waiting for Replace, Append or Cancel. All transient.
        dcc.Store(id='edit-floater-target', data=None),
        dcc.Store(id='edit-floater-mode', data=None),
        # Which kind the create panel starts with: filter + opens a filter,
        # every other creation entry point opens a chart.
        dcc.Store(id='floater-item-kind', data=None),
        dcc.Store(id='config-pending', data=None),
        # A loaded/imported configuration is announced here; callbacks that
        # own a tab, a hidden-activity list, a page or the layout listen to it.
        dcc.Store(id='config-command', data=None),
        dcc.Download(id='config-download'),
        # Dashboard header: where the user is, the activity selector and the
        # filters of the open page. This replaces the SIMVA browser while a
        # dashboard is open, so those controls no longer depend on the browser
        # being visible.
        html.Div(id='dashboard-header', children=[
            html.H3(id='dashboard-title',
                    style={'fontFamily': INTER_FONT, 'fontSize': 16,
                           'margin': '0 0 6px'}),
            html.Div(id='activity-filter-controls', style={'display': 'none'}, children=[
                html.Span('Activities: ', style={'marginRight': '10px'}),
                html.Button('All', id='activity-filter-all', n_clicks=0,
                            style={'marginRight': '5px'}),
                html.Button('None', id='activity-filter-none', n_clicks=0,
                            style={'marginRight': '15px'}),
                html.Span(id='activity-filter-info', children='', style={'color': '#555'}),
            ]),
            html.Div(id='activity-filter-div', children=[], style={'margin': '5px 0'}),
            # All filters of the open page — all-tabs, this-tab and page ones —
            # are drawn in the top bar, with the filter + after them in edit mode.
            html.Div(id='dashboard-filter-bar', children=[],
                     style={'display': 'flex', 'flexWrap': 'wrap',
                            'alignItems': 'center', 'gap': '8px',
                            'margin': '5px 0'}),
            html.Div([
                html.Button(I18n.t('edit.mode.enable'), id='edit-toggle', n_clicks=0),
                # Page name, icon and layout are one panel, so one button opens it
                # for both adding/renaming a page and rearranging its graphs.
                html.Button(I18n.t('edit.page'), id='edit-page-button', n_clicks=0,
                            style={'marginLeft': '6px', 'display': 'none'}),
                html.Button(I18n.t('edit.config'), id='edit-config-button', n_clicks=0,
                            style={'marginLeft': '6px', 'display': 'none'}),
            ], style={'margin': '4px 0'}),
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
                    # Includes the hidden new-tab + at the end of the bar, so
                    # its callback output exists on the first render.
                    children=dashboard_tab_children([]),
                ),
            ], id='dashboard-tabs-wrapper', className='dashboard-tabs-full',
                style={'display': 'flex', 'alignItems': 'flex-start',
                       'flex': '0 0 auto'}),
            html.Div(id='dashboard-content', children=[
                # Loader/upload log, including the file name and date, belongs
                # beside the visualisations rather than above the tab bar.
                html.Div(id='content', children=[]),
                # Creation, titles, pages, layout and configuration are all in
                # the floater window; only confirmations stay inline (ADR 0024).
                config_confirm_layout(),
                tab_remove_confirm_layout(),
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
# A Dash style callback replaces the whole style dict, so the floater's
# overlay properties must be written back on every show/hide, not just once in
# the initial layout — otherwise it drops out of fixed positioning and lands
# in the document flow at the top of the page.
_FLOATER_OVERLAY = {
    'position': 'fixed', 'inset': 0, 'zIndex': 9999,
    'justifyContent': 'center', 'alignItems': 'center',
}
_FLOATER_VISIBLE = {**_FLOATER_OVERLAY, 'display': 'flex'}
_FLOATER_HIDDEN = {**_FLOATER_OVERLAY, 'display': 'none'}


@callback(
    Output('t-mon-tabs', 'children'),
    [Input('dashboard-pages', 'data'), Input('edit-mode', 'data')],
)
def render_dashboard_tabs(pages, edit_mode):
    """Rebuild the tab bar when a named page changes or edit mode is toggled."""
    return dashboard_tab_children(pages, bool(edit_mode))


@callback(
    [
        Output('edit-floater-create', 'style'),
        Output('edit-floater-pages', 'style'),
        Output('edit-floater-config', 'style'),
    ],
    [Input('edit-floater-mode', 'data')],
)
def render_edit_floater_panels(mode):
    """Show only the panel the floater was opened for (ADR 0024).

    Page title and layout share one panel; 'layout' is an alias for it so the
    Edit layout button opens the same controls.
    """
    active = 'pages' if mode == 'layout' else mode
    panels = ('create', 'pages', 'config')
    return tuple(_MODAL_VISIBLE if active == panel else _MODAL_HIDDEN
                 for panel in panels)


@callback(
    [
        Output('tab-remove-pending', 'data'),
        Output('tab-remove-confirm-modal', 'style'),
    ],
    [
        Input({'type': 'tab-remove', 'index': dash.dependencies.ALL}, 'n_clicks'),
        Input('tab-remove-confirm', 'n_clicks'),
        Input('tab-remove-cancel', 'n_clicks'),
    ],
    [State('tab-remove-pending', 'data')],
)
def handle_tab_remove_request(remove_clicks, confirm_n, cancel_n, pending):
    """Ask before removing a tab; the single writer applies a confirmed removal."""
    triggered = dash.callback_context.triggered
    prop_id = triggered[0]['prop_id'] if triggered else ''
    if prop_id.startswith('{') and 'tab-remove' in prop_id and any(remove_clicks or []):
        return str(_pattern_index(prop_id, '.n_clicks') or ''), _MODAL_VISIBLE
    if 'tab-remove-confirm' in prop_id or 'tab-remove-cancel' in prop_id:
        return None, _MODAL_HIDDEN
    raise PreventUpdate


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
    updated = dict(current if isinstance(current, dict) else {})
    updated[str(identifier)] = selected
    return updated


@callback(
    [
        # One state machine owns edit mode and the floater, so no two callbacks
        # write the same output (ADR 0024).
        Output('edit-mode', 'data'),
        Output('edit-toggle', 'children'),
        Output('edit-page-button', 'style'),
        Output('edit-config-button', 'style'),
        Output(NEW_TAB_ADD_ID, 'style'),
        Output('edit-floater', 'style'),
        Output('edit-floater-mode', 'data'),
        Output('edit-floater-target', 'data'),
        Output('item-edit-index', 'data'),
        Output('floater-item-kind', 'data'),
    ],
    [
        Input('edit-toggle', 'n_clicks'),
        Input('edit-floater-close', 'n_clicks'),
        Input('edit-page-button', 'n_clicks'),
        Input('edit-config-button', 'n_clicks'),
        Input({'type': 'item-add-slot', 'index': dash.dependencies.ALL}, 'n_clicks'),
        Input({'type': 'filter-add-slot', 'index': dash.dependencies.ALL}, 'n_clicks'),
        Input('item-cancel', 'n_clicks'),
        Input('item-add', 'n_clicks'),
        Input({'type': 'item-edit', 'index': dash.dependencies.ALL}, 'n_clicks'),
        Input({'type': 'default-graph-edit', 'index': dash.dependencies.ALL},
              'n_clicks'),
        Input(NEW_TAB_ADD_ID, 'n_clicks'),
        Input('t-mon-tabs', 'value'),
    ],
    [State('edit-mode', 'data')],
)
def toggle_edit_floater(edit_n, close_n, page_n, config_n,
                        slot_clicks, filter_clicks, cancel_n, add_n, edit_clicks,
                        default_edit_clicks, new_tab_n, tab, enabled):
    """Edit mode and the floater are controlled separately here.

    The Edit button only toggles edit mode. The section buttons open their
    panels; a + slot or an item's Edit opens creation, and the top bar's filter
    + opens the same create panel with a filter preselected. The floater's ×
    and the panel's Cancel only close the window (ADR 0024).
    """
    triggered = dash.callback_context.triggered
    prop_ids = [entry.get('prop_id', '') or '' for entry in triggered]
    prop_id = prop_ids[0] if prop_ids else ''
    on = bool(enabled)

    def clicked(fragment):
        return any(fragment in item for item in prop_ids)

    def trigger_prop(fragment):
        """The prop id of the specific input that fired, for pattern indices."""
        for entry in triggered:
            if fragment in (entry.get('prop_id') or ''):
                return entry.get('prop_id') or ''
        return prop_id

    def clicked_n(fragment):
        """True only when that component was actually clicked.

        A pattern-matching ALL input also fires when new components appear (a
        new page renders new + slots). Checking `any(n_clicks)` from older
        clicks would then open the wrong panel, so use the triggered value.
        """
        for entry in triggered:
            if fragment in (entry.get('prop_id') or ''):
                try:
                    return int(entry.get('value') or 0) > 0
                except (TypeError, ValueError):
                    return False
        return False

    def tab_style(active):
        return {'display': 'block' if active else 'none', 'width': '100%',
                'border': f'1px dashed {BRAND_PRIMARY}',
                'background': LIGHT_CARD, 'color': BRAND_PRIMARY,
                'fontSize': '18px', 'cursor': 'pointer'}

    def btn_style(active):
        return {'display': 'none'} if not active else {'marginLeft': '6px'}

    def open_panel(mode, kind=None):
        # Turning a panel on also switches edit mode on: show the edit buttons
        # and the tab (+), then reveal the floater.
        return (True,
                I18n.t('edit.mode.disable'),
                btn_style(True), btn_style(True),
                tab_style(True), _FLOATER_VISIBLE, mode, None, None, kind)

    def close_panel():
        # Closing the floater keeps edit mode on but hides the window; buttons
        # and tab reflect the current edit mode.
        return (on, no_update, btn_style(on), btn_style(on),
                tab_style(on), _FLOATER_HIDDEN, None, None, None, None)

    if clicked('edit-toggle.n_clicks'):
        if int(edit_n or 0) <= 0:
            raise PreventUpdate
        on = not on
        return (on,
                I18n.t('edit.mode.disable' if on else 'edit.mode.enable'),
                btn_style(on), btn_style(on),
                tab_style(on), _FLOATER_HIDDEN, None, None, None, None)
    if (clicked('edit-floater-close.n_clicks') and int(close_n or 0) > 0
            or clicked('item-cancel.n_clicks') and int(cancel_n or 0) > 0):
        return close_panel()
    if clicked(NEW_TAB_ADD_ID + '.n_clicks') and int(new_tab_n or 0) > 0:
        # Creating a page opens the combined title + layout panel.
        return open_panel('pages')
    if clicked('t-mon-tabs.value'):
        # Visiting a tab never opens the floater.
        return close_panel()
    if clicked('edit-page-button.n_clicks') and int(page_n or 0) > 0:
        return open_panel('pages')
    if clicked('edit-config-button.n_clicks') and int(config_n or 0) > 0:
        return open_panel('config')
    if not on:
        raise PreventUpdate
    if clicked('filter-add-slot') and clicked_n('filter-add-slot'):
        raw_target = _pattern_index(trigger_prop('filter-add-slot'), '.n_clicks')
        target = str(raw_target) if raw_target else page_key(tab)
        if target and not target.startswith(PAGE_TAB_PREFIX):
            target = PAGE_TAB_PREFIX + target
        return (on, no_update, no_update, no_update,
                no_update, _FLOATER_VISIBLE, 'create', target, None,
                'filter-multi')
    if clicked('item-add-slot') and clicked_n('item-add-slot'):
        raw_target = _pattern_index(trigger_prop('item-add-slot'), '.n_clicks')
        target = str(raw_target).rsplit('|', 1)[0] if raw_target else ''
        return (on, no_update, no_update, no_update,
                no_update, _FLOATER_VISIBLE, 'create', target or page_key(tab), None, None)
    if clicked('item-edit') and clicked_n('item-edit'):
        return (on, no_update, no_update, no_update,
                no_update, _FLOATER_VISIBLE, 'create', page_key(tab),
                {'index': _pattern_index(trigger_prop('item-edit'), '.n_clicks')},
                None)
    if clicked('default-graph-edit') and clicked_n('default-graph-edit'):
        return (on, no_update, no_update, no_update,
                no_update, _FLOATER_VISIBLE, 'create', no_update,
                {'index': f"default:{_pattern_index(trigger_prop('default-graph-edit'), '.n_clicks')}"},
                None)
    if clicked('item-add.n_clicks') and int(add_n or 0) > 0:
        return (on, no_update, no_update, no_update,
                no_update, _FLOATER_VISIBLE, 'create', no_update, None, None)
    raise PreventUpdate


@callback(
    [
        Output('item-kind', 'value'),
        Output('item-column', 'value'),
        Output('item-chart-type', 'value'),
        Output('item-title', 'value'),
        Output('item-xlabel', 'value'),
        Output('item-ylabel', 'value'),
        Output('item-y', 'value'),
        Output('item-aggregation', 'value'),
    ],
    [Input('item-edit-index', 'data'), Input('floater-item-kind', 'data')],
    [
        State('edit-floater-target', 'data'),
        State('created-charts', 'data'),
        State('page-filters', 'data'),
        State('dashboard-pages', 'data'),
        State('default-graph-overrides', 'data'),
    ],
)
def prefill_item_modal(edit_index, floater_kind, target, charts, filters, pages,
                       overrides=None):
    """Fill the popup with the graph and labels being edited, not with defaults."""
    if not isinstance(edit_index, dict) or not edit_index.get('index'):
        # A fresh add starts with empty wording. The top-bar filter + chooses a
        # filter kind; every other entry point starts with a bar chart so the
        # column, value and label inputs are visible immediately.
        return floater_kind or 'bar', None, no_update, '', '', '', None, no_update
    if str(edit_index['index']).startswith('default:'):
        key = str(edit_index['index'])[len('default:'):]
        spec = default_graph_spec(find_default_graph(key))
        if spec is None:
            raise PreventUpdate
        override = (overrides or {}).get(key)
        if isinstance(override, dict):
            merged = normalise_spec({**spec, **override})
            if merged is not None:
                spec = merged
        return (spec['type'], spec['x'], spec['type'],
                spec.get('title') or '', spec.get('x_label') or '',
                spec.get('y_label') or '', spec.get('y') or COUNT_LABEL,
                spec.get('aggregation') or 'count')
    kind, separator, raw_index = str(edit_index['index']).partition(':')
    if not separator:
        raise PreventUpdate
    try:
        index = int(raw_index)
    except ValueError:
        raise PreventUpdate
    target_charts, target_filters = items_for_key(
        str(target), pages, charts, filters)
    if kind == 'filter':
        if not (0 <= index < len(target_filters)):
            raise PreventUpdate
        spec = target_filters[index]
        mode = spec.get('mode') if isinstance(spec, dict) else None
        return ('filter-single' if mode == 'single' else 'filter-multi',
                spec.get('column') if isinstance(spec, dict) else None,
                no_update, '', '', '', None, no_update)
    if not (0 <= index < len(target_charts)):
        raise PreventUpdate
    spec = target_charts[index] if isinstance(target_charts[index], dict) else {}
    chart_type = spec.get('type') if spec.get('type') in CHART_TYPES else 'bar'
    return (chart_type, spec.get('x'), chart_type,
            spec.get('title') or '', spec.get('x_label') or '',
            spec.get('y_label') or '', spec.get('y') or COUNT_LABEL,
            spec.get('aggregation') or 'count')


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
        Output('item-labels-div', 'style'),
        Output('item-y', 'options'),
        Output('item-value-div', 'style'),
    ],
    [
        Input('item-kind', 'value'),
        Input('lrs-data-version', 'data'),
        Input('output-t-mon', 'style'),
    ],
)
def update_item_modal_fields(kind, lrs_version, panel_style):
    """Offer the columns a generic chart or filter needs.

    The game, target and mode pickers belonged to the removed named-visual
    catalogue. They stay in the layout with stable ids but are never populated.
    """
    if panel_style != {'display': 'block'} or not TMonWidgets.xapiData:
        return ([], [], [], None, [], None,
                _MODAL_HIDDEN, _MODAL_HIDDEN, _MODAL_HIDDEN, _MODAL_HIDDEN,
                _MODAL_HIDDEN, [], _MODAL_HIDDEN)
    df = pd.json_normalize(TMonWidgets.xapiData)
    df = resolve_actor_name_column(df)
    columns = [{'label': column, 'value': column}
               for column in filterable_columns(df)]
    column_style = (_MODAL_VISIBLE if kind in CHART_TYPES
                    or kind in ('filter-multi', 'filter-single') else _MODAL_HIDDEN)
    labels_style = _MODAL_VISIBLE if kind in CHART_TYPES else _MODAL_HIDDEN
    y_options = ([{'label': COUNT_LABEL, 'value': COUNT_LABEL}] + [
        {'label': column, 'value': column} for column in numeric_columns(df)])
    return ([], columns, [], None, [], None,
            _MODAL_HIDDEN, column_style, _MODAL_HIDDEN, _MODAL_HIDDEN,
            labels_style, y_options, labels_style)


@callback(
    Output('default-graph-overrides', 'data'),
    [
        Input('item-add', 'n_clicks'),
        Input('config-command', 'data'),
    ],
    [
        State('item-edit-index', 'data'),
        State('default-graph-overrides', 'data'),
        State('item-kind', 'value'),
        State('item-column', 'value'),
        State('item-y', 'value'),
        State('item-aggregation', 'value'),
        State('item-title', 'value'),
        State('item-xlabel', 'value'),
        State('item-ylabel', 'value'),
    ],
)
def update_default_graph_overrides(add_n, command, edit_index, overrides,
                                   kind, column, y, aggregation,
                                   title, x_label, y_label):
    """Save an admin's edit of a default graph, and load overrides from a config."""
    if not is_admin():
        # Only an administrator may change what the default dashboard shows.
        raise PreventUpdate
    triggered = dash.callback_context.triggered
    prop_id = triggered[0]['prop_id'] if triggered else ''
    if ('config-command' in prop_id and isinstance(command, dict)
            and command.get('config')):
        imported = dict(command['config'].get('default_graph_overrides') or {})
        if command.get('action') == 'append':
            merged = dict(overrides or {})
            merged.update(imported)
            return merged
        return imported
    key = _default_edit_key(edit_index)
    if 'item-add' not in prop_id or int(add_n or 0) <= 0 or not key:
        raise PreventUpdate
    spec = normalise_spec({
        'type': kind, 'x': column, 'y': y or COUNT_LABEL,
        'aggregation': aggregation or 'count',
        'title': title, 'x_label': x_label, 'y_label': y_label,
    })
    if spec is None:
        raise PreventUpdate
    updated = dict(overrides or {})
    updated[key] = spec
    return updated


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
        State('activity-filter-hidden', 'data'),
        State('default-graph-overrides', 'data'),
    ],
)
def handle_config_actions(export_n, save_n, import_contents, load_n, delete_n,
                          refresh_n, replace_n, append_n, cancel_n, panel_style,
                          name, selected, pending, charts, filters, pages, tab,
                          graph_layout, graph_rows, graph_columns, graph_page,
                          split_x, split_y, hidden,
                          default_overrides=None):
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
            {'actor.name': [], 'object.id': []},
            hidden or [], tab, default_overrides,
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
