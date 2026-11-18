"""
Query-parameter driven explorer for the simlet tiles.

The SimVA front end filters its simlet lists with ``status``, ``searchString``,
``searchTags``, ``skip``, ``limit``, ``orderBy`` and ``order``. T-Mon keeps the
same state in the browser URL so a filtered list can be shared as a link, and
applies it to the studies already loaded by the SimVA browser.
"""

from urllib.parse import parse_qs, urlencode

import dash
from dash import html, dcc, callback, Input, Output, State
from dash.exceptions import PreventUpdate

import TMonWidgets
from TMonWidgets.TMonWidget import render_simlet_tiles

DEFAULT_LIMIT = 9
MAX_LIMIT = 50

STATUS_OPTIONS = [
    {'label': 'Active', 'value': 'active'},
    {'label': 'Archived', 'value': 'archived'},
]

# The same seven choices the SimVA front end offers, with the sort direction
# carried alongside the column so one control covers `orderBy` and `order`.
SORT_OPTIONS = [
    ('id', 'asc', 'Default'),
    ('name', 'asc', 'Name (A-Z)'),
    ('name', 'desc', 'Name (Z-A)'),
    ('createdAt', 'desc', 'Creation date (Newest first)'),
    ('createdAt', 'asc', 'Creation date (Oldest first)'),
    ('updatedAt', 'desc', 'Update date (Newest first)'),
    ('updatedAt', 'asc', 'Update date (Oldest first)'),
]

ORDER_COLUMNS = ('id', 'name', 'createdAt', 'updatedAt')

DEFAULT_FILTERS = {
    'status': 'active',
    'searchString': '',
    'skip': 0,
    'limit': DEFAULT_LIMIT,
    'orderBy': 'id',
    'order': 'asc',
    'searchTags': [],
}


def _simlet_value(simlet, *keys, default=None):
    """Read the first present key from a raw or normalised simlet object."""
    for key in keys:
        if isinstance(simlet, dict) and simlet.get(key) is not None:
            return simlet[key]
    return default


def parse_simlet_query(search):
    """
    Read the explorer state from a URL query string.

    Unknown or malformed values fall back to the defaults, so a hand-edited
    link cannot break the grid.

    Args:
        search (str): The ``window.location.search`` value, with or without '?'.

    Returns:
        dict: The normalised filter values.
    """
    raw = parse_qs((search or '').lstrip('?'), keep_blank_values=True)

    def first(key, default=''):
        values = raw.get(key)
        return values[0] if values else default

    filters = dict(DEFAULT_FILTERS)
    status = first('status') or 'active'
    filters['status'] = status if status in ('active', 'archived') else 'active'
    filters['searchString'] = first('searchString')

    order_by = first('orderBy') or 'id'
    filters['orderBy'] = order_by if order_by in ORDER_COLUMNS else 'id'
    order = (first('order') or 'asc').lower()
    filters['order'] = order if order in ('asc', 'desc') else 'asc'

    for key in ('skip', 'limit'):
        try:
            value = int(first(key, str(DEFAULT_FILTERS[key])))
        except (TypeError, ValueError):
            value = DEFAULT_FILTERS[key]
        filters[key] = max(0, value)
    filters['limit'] = min(max(filters['limit'], 1), MAX_LIMIT)

    filters['searchTags'] = [tag for tag in first('searchTags').split(',')
                             if tag.strip()]
    return filters


def build_simlet_query(filters):
    """
    Build the URL query string for the explorer state.

    Empty values are left out, the same way the SimVA front end builds its API
    requests. With everything at its default this yields
    ``status=active&skip=0&limit=9&orderBy=id&order=asc``.

    Args:
        filters (dict): The explorer state.

    Returns:
        str: An encoded query string without the leading '?'.
    """
    params = [
        ('status', filters['status']),
        ('skip', str(filters['skip'])),
        ('limit', str(filters['limit'])),
        ('orderBy', filters['orderBy']),
        ('order', filters['order']),
    ]
    if filters['searchString']:
        params.append(('searchString', filters['searchString']))
    if filters['searchTags']:
        params.append(('searchTags', ','.join(str(tag) for tag in filters['searchTags'])))
    return urlencode(params, safe=',')


def available_tag_options(studies):
    """
    List the tags assigned to the loaded simlets, as dropdown options.

    Args:
        studies (list): Simlet objects loaded from the SimVA API.

    Returns:
        list: ``{'label': ..., 'value': ...}`` options, ordered by tag id.
    """
    tags = {}
    for simlet in studies or []:
        for tag in _simlet_value(simlet, 'tags', default=[]) or []:
            if isinstance(tag, dict):
                tag_id = _simlet_value(tag, 'tag_id', 'id')
                name = _simlet_value(tag, 'tag_name', 'name', default=str(tag_id))
            else:
                tag_id, name = tag, str(tag)
            if tag_id is not None:
                tags[str(tag_id)] = str(name)
    ordered = sorted(tags.items(),
                     key=lambda item: int(item[0]) if item[0].isdigit() else item[0])
    return [{'label': name, 'value': tag_id} for tag_id, name in ordered]


def apply_simlet_filters(studies, filters):
    """
    Filter, sort and paginate the loaded simlets for one page of the grid.

    Args:
        studies (list): Simlet objects loaded from the SimVA API.
        filters (dict): The explorer state.

    Returns:
        tuple: ``(page, total)`` where ``page`` is the slice to show and
        ``total`` is the number of simlets matching the filters.
    """
    archived = filters['status'] == 'archived'
    term = filters['searchString'].strip().lower()
    wanted_tags = {str(tag) for tag in filters['searchTags']}
    selected = []
    for simlet in studies or []:
        if bool(_simlet_value(simlet, 'simlet_archived', 'archived', default=False)) != archived:
            continue
        if term:
            name = str(_simlet_value(simlet, 'simlet_name', 'name', default=''))
            description = str(_simlet_value(
                simlet, 'simlet_description', 'description', default=''))
            if term not in name.lower() and term not in description.lower():
                continue
        if wanted_tags:
            tag_ids = set()
            for tag in _simlet_value(simlet, 'tags', default=[]) or []:
                if isinstance(tag, dict):
                    tag_ids.add(str(_simlet_value(tag, 'tag_id', 'id', default='')))
                else:
                    tag_ids.add(str(tag))
            if not tag_ids & wanted_tags:
                continue
        selected.append(simlet)

    order_by = filters['orderBy']
    columns = {
        'id': ('simlet_id', 'id'),
        'name': ('simlet_name', 'name'),
        'createdAt': ('createdAt', 'created_at'),
        'updatedAt': ('updatedAt', 'updated_at'),
    }[order_by]

    def sort_key(simlet):
        value = _simlet_value(simlet, *columns, default='')
        if order_by == 'id':
            try:
                return (0, int(value))
            except (TypeError, ValueError):
                return (1, str(value))
        return str(value)

    selected.sort(key=sort_key, reverse=filters['order'] == 'desc')
    total = len(selected)
    skip = filters['skip']
    return selected[skip:skip + filters['limit']], total


def render_simlet_controls(filters, studies):
    """
    Build the row of filter controls above the simlet grid.

    Args:
        filters (dict): Current explorer state, used for the initial values.
        studies (list): Loaded simlets, used to populate the tag selector.

    Returns:
        html.Div: The controls, with ids in the ``simlet-explorer-*`` family.
    """
    sort_value = f"{filters['orderBy']}:{filters['order']}"
    info_start = filters['skip'] + 1 if filters['limit'] else 0
    return html.Div([
        dcc.Dropdown(
            id='simlet-explorer-status', options=STATUS_OPTIONS,
            value=filters['status'], clearable=False,
            style={'width': '140px', 'marginRight': '10px'}),
        dcc.Input(
            id='simlet-explorer-search', type='text', debounce=True,
            value=filters['searchString'],
            placeholder='Search a SIMLET by name or description',
            style={'width': '260px', 'marginRight': '10px', 'padding': '6px'}),
        dcc.Dropdown(
            id='simlet-explorer-sort',
            options=[{'label': label, 'value': f'{column}:{direction}'}
                     for column, direction, label in SORT_OPTIONS],
            value=sort_value, clearable=False,
            style={'width': '230px', 'marginRight': '10px'}),
        dcc.Dropdown(
            id='simlet-explorer-tags', multi=True,
            options=available_tag_options(studies), value=filters['searchTags'],
            placeholder='Tags',
            style={'width': '220px', 'marginRight': '10px', 'flex': '1 1 220px'}),
        dcc.Input(
            id='simlet-explorer-limit', type='number', min=1, max=MAX_LIMIT,
            debounce=True, value=filters['limit'],
            style={'width': '70px', 'marginRight': '10px'}),
        html.Button('Previous', id='simlet-explorer-prev', n_clicks=0,
                    style={'marginRight': '5px'}),
        html.Button('Next', id='simlet-explorer-next', n_clicks=0),
        html.Span(id='simlet-explorer-info',
                  children=f"{info_start}-{filters['skip'] + filters['limit']}",
                  style={'marginLeft': '12px', 'fontFamily': 'Inter', 'fontSize': 12}),
    ], style={'display': 'flex', 'alignItems': 'center', 'flexWrap': 'wrap',
              'gap': '4px', 'margin': '10px 20px'})


@callback(
    [Output('simlet-browser-grid', 'children'),
     Output('simlet-explorer-info', 'children'),
     Output('url', 'search')],
    [Input('simlet-explorer-status', 'value'),
     Input('simlet-explorer-search', 'value'),
     Input('simlet-explorer-sort', 'value'),
     Input('simlet-explorer-tags', 'value'),
     Input('simlet-explorer-limit', 'value'),
     Input('simlet-explorer-prev', 'n_clicks'),
     Input('simlet-explorer-next', 'n_clicks'),
     Input('current-path', 'children'),
     Input('main-login', 'children')],
    [State('url', 'search')]
)
def update_simlet_explorer(status, search, sort, tags, limit, previous, following,
                           current_path, main_login, url_search):
    """Redraw the grid from the controls and publish the state in the URL."""
    # The panel stays in the layout but is hidden once a simlet is open, so
    # there is no grid to redraw in that state.
    if status is None and search is None:
        raise PreventUpdate

    filters = parse_simlet_query(url_search)
    if status in ('active', 'archived'):
        filters['status'] = status
    filters['searchString'] = search or ''
    if sort:
        order_by, order = sort.split(':', 1)
        filters['orderBy'] = order_by if order_by in ORDER_COLUMNS else 'id'
        filters['order'] = order if order in ('asc', 'desc') else 'asc'
    filters['searchTags'] = [str(tag) for tag in (tags or [])]
    if limit:
        try:
            filters['limit'] = min(max(int(limit), 1), MAX_LIMIT)
        except (TypeError, ValueError):
            pass

    studies = getattr(TMonWidgets, 'accepted_studies', []) or []
    triggered = dash.callback_context.triggered
    source = triggered[0]['prop_id'] if triggered else ''
    if 'simlet-explorer-next' in source:
        filters['skip'] += filters['limit']
    elif 'simlet-explorer-prev' in source:
        filters['skip'] = max(0, filters['skip'] - filters['limit'])
    else:
        # Any change of filter starts again from the first page.
        filters['skip'] = 0

    page, total = apply_simlet_filters(studies, filters)
    if filters['skip'] >= total and total:
        filters['skip'] = max(0, ((total - 1) // filters['limit']) * filters['limit'])
        page, total = apply_simlet_filters(studies, filters)

    first = filters['skip'] + 1 if total else 0
    last = min(filters['skip'] + filters['limit'], total)
    info = f"{first}-{last} of {total}"
    return render_simlet_tiles(page), info, '?' + build_simlet_query(filters)
