"""
Sessions list for a simlet, styled after the SimVA front-end Sessions tab.

The list is shown when a simlet is open. Its sessions come from the browser's
current selection, and the controls use the same parameter names and sort
choices as the SimVA API. Activities are deliberately not drawn here: they are
shown only once a session has been opened.
"""

from urllib.parse import parse_qs, urlencode

import dash
from dash import html, dcc, callback, Input, Output, State, no_update
from dash.exceptions import PreventUpdate

import TMonWidgets
from TMonWidgets.SimletExplorer import MAX_LIMIT, ORDER_COLUMNS
from TMonWidgets import I18n

DEFAULT_LIMIT = 4  # SESSIONS_SHOW_AT_ONCE in simva-front

# The seven choices from the SimVA Sessions tab. "Default" is `id:asc`, so the
# initial value must be one of these or the dropdown renders empty.
SESSION_SORT_OPTIONS = [
    ('id', 'asc', 'filters.sort_by.id'),
    ('name', 'asc', 'filters.sort_by.name.asc'),
    ('name', 'desc', 'filters.sort_by.name.desc'),
    ('createdAt', 'desc', 'filters.sort_by.created_at.desc'),
    ('createdAt', 'asc', 'filters.sort_by.created_at.asc'),
    ('updatedAt', 'desc', 'filters.sort_by.updated_at.desc'),
    ('updatedAt', 'asc', 'filters.sort_by.updated_at.asc'),
]
SORT_VALUES = {f'{column}:{direction}' for column, direction, _ in SESSION_SORT_OPTIONS}

DEFAULT_FILTERS = {
    'status': '',  # All / active / inactive (Paused) / terminated (Finished)
    'searchString': '',
    'skip': 0,
    'limit': DEFAULT_LIMIT,
    'orderBy': 'id',
    'order': 'asc',
    'searchTags': [],
}

STATUS_OPTIONS = [
    ('filters.status.all', ''),
    ('sessions.status.active.title', 'active'),
    ('sessions.status.paused.title', 'inactive'),
    ('sessions.status.finished.title', 'terminated'),
]

STATUS_LABELS = {
    'active': ('sessions.status.active.title', '#8ec26d'),
    'inactive': ('sessions.status.paused.title', '#fbfd68'),
    'terminated': ('sessions.status.finished.title', '#f07667'),
}


def _session_value(session, *keys, default=None):
    for key in keys:
        if isinstance(session, dict) and session.get(key) is not None:
            return session[key]
    return default


def is_simlet_path(path, base='output/'):
    """Whether a browser path names a simlet but no session below it."""
    if not isinstance(path, str):
        return False
    remainder = path.replace(base, '', 1).strip('/')
    return bool(remainder) and '/' not in remainder


def parse_session_query(search):
    """Read the session list state from a URL query string."""
    raw = parse_qs((search or '').lstrip('?'), keep_blank_values=True)

    def first(key, default=''):
        values = raw.get(key)
        return values[0] if values else default

    filters = dict(DEFAULT_FILTERS)
    status = first('status')
    filters['status'] = status if status in ('', 'active', 'inactive', 'terminated') else ''
    filters['searchString'] = first('searchString')
    order_by = first('orderBy') or 'id'
    filters['orderBy'] = order_by if order_by in ORDER_COLUMNS else 'id'
    order = (first('order') or 'asc').lower()
    filters['order'] = order if order in ('asc', 'desc') else 'asc'
    # A link carried over from the simlets list can hold `id:desc`, which is
    # not a choice here. Keep the value one the dropdown can actually show.
    if f"{filters['orderBy']}:{filters['order']}" not in SORT_VALUES:
        filters['orderBy'], filters['order'] = 'id', 'asc'
    for key in ('skip', 'limit'):
        try:
            value = int(first(key, str(DEFAULT_FILTERS[key])))
        except (TypeError, ValueError):
            value = DEFAULT_FILTERS[key]
        filters[key] = max(0, value)
    filters['limit'] = min(max(filters['limit'], 1), MAX_LIMIT)
    filters['searchTags'] = [tag for tag in first('searchTags').split(',') if tag.strip()]
    return filters


def build_session_query(filters):
    """Build the query string for the session list state."""
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


def session_tag_options(sessions):
    """Dropdown options for the tags assigned to the loaded sessions."""
    tags = {}
    for session in sessions or []:
        for tag in _session_value(session, 'tags', default=[]) or []:
            if isinstance(tag, dict):
                tag_id = _session_value(tag, 'tag_id', 'id')
                name = _session_value(tag, 'tag_name', 'name', default=str(tag_id))
            else:
                tag_id, name = tag, str(tag)
            if tag_id is not None:
                tags[str(tag_id)] = str(name)
    ordered = sorted(tags.items(),
                     key=lambda item: int(item[0]) if item[0].isdigit() else item[0])
    return [{'label': name, 'value': tag_id} for tag_id, name in ordered]


def _session_status(value):
    """Normalise the status a session object carries to the API's three values."""
    text = str(value or '').strip().lower()
    return {
        'paused': 'inactive',
        'finished': 'terminated',
    }.get(text, text)


def apply_session_filters(sessions, filters):
    """Filter, sort and paginate a simlet's sessions for one list page."""
    selected = []
    for session in sessions or []:
        status = _session_status(_session_value(
            session, 'session_status', 'status', default=''))
        if filters['status'] and status != filters['status']:
            continue
        term = filters['searchString'].strip().lower()
        if term:
            name = str(_session_value(session, 'session_name', 'name', default=''))
            description = str(_session_value(
                session, 'session_description', 'description', default=''))
            if term not in name.lower() and term not in description.lower():
                continue
        wanted = {str(tag) for tag in filters['searchTags']}
        if wanted:
            ids = set()
            for tag in _session_value(session, 'tags', default=[]) or []:
                if isinstance(tag, dict):
                    ids.add(str(_session_value(tag, 'tag_id', 'id', default='')))
                else:
                    ids.add(str(tag))
            if not ids & wanted:
                continue
        selected.append(session)

    columns = {
        'id': ('session_id', 'id'),
        'name': ('session_name', 'name'),
        'createdAt': ('createdAt', 'created_at'),
        'updatedAt': ('updatedAt', 'updated_at'),
    }[filters['orderBy']]

    def sort_key(session):
        value = _session_value(session, *columns, default='')
        if filters['orderBy'] == 'id':
            try:
                return (0, int(value))
            except (TypeError, ValueError):
                return (1, str(value))
        return str(value)

    selected.sort(key=sort_key, reverse=filters['order'] == 'desc')
    total = len(selected)
    return selected[filters['skip']:filters['skip'] + filters['limit']], total


def _format_date(value):
    """Show an API timestamp as YYYY/MM/DD, or '-' when it is missing."""
    if not value:
        return '-'
    text = str(value)[:10]
    if len(text) == 10 and text[4] == '-' and text[7] == '-':
        return f"{text[:4]}/{text[5:7]}/{text[8:10]}"
    return '-'


def render_session_cards(page):
    """
    Render session cards like the SimVA Sessions tab, without activities.

    Each card is a folder button so the existing browser callback opens the
    session when it is clicked.
    """
    if not page:
        return html.Div(I18n.t('filters.search.no_matches.message'),
                        style={'fontFamily': 'Inter', 'padding': '20px'})

    cards = []
    for session in page:
        session_id = _session_value(session, 'session_id', 'id')
        name = _session_value(session, 'session_name', 'name', default=str(session_id))
        description = _session_value(session, 'session_description', 'description', default='')
        status = _session_status(_session_value(
            session, 'session_status', 'status', default=''))
        label_key, color = STATUS_LABELS.get(status, ('', '#e8e5e2'))
        label = I18n.t(label_key) if label_key else ''

        def style(size, color_value, weight='400', extra=None):
            value = {
                'fontFamily': 'Inter', 'fontSize': size, 'color': color_value,
                'fontWeight': weight, 'whiteSpace': 'nowrap',
                'overflow': 'hidden', 'textOverflow': 'ellipsis',
            }
            value.update(extra or {})
            return value

        tags = []
        for tag in _session_value(session, 'tags', default=[]) or []:
            if isinstance(tag, dict):
                tag_name = _session_value(tag, 'tag_name', 'name', default='')
                tag_color = _session_value(tag, 'tag_color', 'color', default='#078493')
            else:
                tag_name, tag_color = str(tag), '#078493'
            tags.append(html.Span(tag_name, style=style(10, '#fff', extra={
                'backgroundColor': tag_color, 'borderRadius': '10px',
                'padding': '1px 8px', 'marginRight': '4px'})))
        activities = _session_value(session, 'activities', default=[]) or []
        participants = _session_value(session, 'participants',
                                      'completeParticipants', default=[]) or []

        cards.append(html.Div([
            html.Button(
                html.Div([
                    html.Div([
                        html.Div(name, style=style(15, '#1e1e1e', '600',
                                                 {'flex': '1 1 auto'})),
                        html.Div(label, style=style(11, '#1e1e1e', '600', {
                            'backgroundColor': color, 'borderRadius': '25px',
                            'padding': '2px 12px', 'textAlign': 'center',
                            'width': '100px'})),
                    ], style={'display': 'flex', 'alignItems': 'center'}),
                    html.Div(description, style=style(12, '#3c6d7a', extra={
                        'whiteSpace': 'normal', 'margin': '4px 0'})),
                    html.Div(f"{I18n.t('info.created_at')}: "
                             f"{_format_date(_session_value(session, 'createdAt'))}",
                             style=style(11, '#3c6d7a')),
                    html.Div([
                        html.Span(f"{I18n.t('activities.title')}: "
                                  f"{len(activities) if hasattr(activities, '__len__') else 0}",
                                  style={'marginRight': '18px'}),
                        html.Span(f"{I18n.t('participants.title')}: "
                                  f"{len(participants) if hasattr(participants, '__len__') else 0}"),
                    ], style=style(11, '#3c6d7a')),
                    html.Div(tags or [html.Span(I18n.t('info.tags.no_tags'),
                                               style=style(11, '#3c6d7a'))],
                             style={'marginTop': '6px'}),
                ], style={'backgroundColor': '#fcfcfc',
                          'border': '1px solid rgba(0,0,0,0.1)',
                          'borderRadius': '8px', 'padding': '12px',
                          'textAlign': 'left', 'boxShadow': '0 1px 3px rgba(0,0,0,.3)'}),
                id={'type': 'folder-button', 'index': f'{session_id}/'},
                n_clicks=0,
                style={'display': 'block', 'width': '100%', 'cursor': 'pointer',
                       'background': 'none', 'border': 'none', 'padding': '0'},
            ),
            # Shortcut to the same whole-session analysis as the "Complete
            # session" (Analysis) folder entry.
            html.Button(I18n.t('sessions.view_dashboard'),
                        id={'type': 'session-dashboard-button',
                            'index': str(session_id)},
                        n_clicks=0,
                        style={'marginTop': '-8px', 'marginBottom': '10px',
                               'padding': '4px 12px', 'cursor': 'pointer'}),
        ]))
    return html.Div(cards, style={'padding': '10px 20px'})


def render_session_controls(filters, sessions):
    """Build the filter row above the session cards."""
    sort_value = f"{filters['orderBy']}:{filters['order']}"
    return html.Div([
        dcc.Input(
            id='session-explorer-search', type='text', debounce=True,
            value=filters['searchString'],
            placeholder=I18n.t('sessions.search_bar.placeholder'),
            style={'width': '260px', 'marginRight': '10px', 'padding': '6px'}),
        html.Span(I18n.t('filters.sort_by.title'),
                  style={'fontFamily': 'Inter', 'fontSize': 12,
                         'marginRight': '5px'}),
        dcc.Dropdown(
            id='session-explorer-sort',
            options=[{'label': I18n.t(key), 'value': f'{column}:{direction}'}
                     for column, direction, key in SESSION_SORT_OPTIONS],
            value=sort_value, clearable=False,
            style={'width': '230px', 'marginRight': '10px'}),
        html.Span(I18n.t('filters.status.title'),
                  style={'fontFamily': 'Inter', 'fontSize': 12,
                         'marginRight': '5px'}),
        dcc.Dropdown(
            id='session-explorer-status',
            options=[{'label': I18n.t(key), 'value': value}
                     for key, value in STATUS_OPTIONS],
            value=filters['status'], clearable=False,
            style={'width': '130px', 'marginRight': '10px'}),
        dcc.Dropdown(
            id='session-explorer-tags', multi=True,
            options=session_tag_options(sessions), value=filters['searchTags'],
            placeholder=I18n.t('info.tags'),
            style={'width': '220px', 'marginRight': '10px', 'flex': '1 1 220px'}),
        dcc.Input(
            id='session-explorer-limit', type='number', min=1, max=MAX_LIMIT,
            debounce=True, value=filters['limit'],
            style={'width': '70px', 'marginRight': '10px'}),
        html.Button(I18n.t('simlets.previous'), id='session-explorer-prev', n_clicks=0,
                    style={'marginRight': '5px'}),
        html.Button(I18n.t('simlets.next'), id='session-explorer-next', n_clicks=0),
        html.Span(id='session-explorer-info',
                  style={'marginLeft': '12px', 'fontFamily': 'Inter', 'fontSize': 12}),
    ], style={'display': 'flex', 'alignItems': 'center', 'flexWrap': 'wrap',
              'gap': '4px', 'margin': '10px 20px'})


def render_session_explorer_panel(sessions=None, search='', style=None):
    """The persistent panel holding the session controls and their cards."""
    return html.Div([
        html.H3(I18n.t('sessions.title'),
                style={'margin': '0 0 4px 20px', 'fontFamily': 'Inter'}),
        dcc.Store(id='session-explorer-state', data={'skip': 0}),
        render_session_controls(parse_session_query(search), sessions or []),
        html.Div(id='session-browser-cards'),
    ], id='session-explorer-panel',
        style=style if style is not None else {'display': 'none'})


@callback(
    [Output('session-explorer-panel', 'style'),
     Output('session-browser-cards', 'children'),
     Output('session-explorer-info', 'children'),
     Output('session-explorer-state', 'data')],
    [Input('current-path', 'children'),
     Input('main-login', 'children'),
     Input('session-explorer-status', 'value'),
     Input('session-explorer-search', 'value'),
     Input('session-explorer-sort', 'value'),
     Input('session-explorer-tags', 'value'),
     Input('session-explorer-limit', 'value'),
     Input('session-explorer-prev', 'n_clicks'),
     Input('session-explorer-next', 'n_clicks'),
     Input('session-explorer-state', 'data')]
)
def update_session_explorer(path, main, status, search, sort, tags, limit,
                            previous, following, state):
    """Show the sessions list only on a simlet, and redraw it on a change."""
    if not is_simlet_path(path):
        raise PreventUpdate

    filters = dict(DEFAULT_FILTERS)
    if status in ('', 'active', 'inactive', 'terminated'):
        filters['status'] = status
    filters['searchString'] = search or ''
    if sort:
        order_by, order = sort.split(':', 1)
        if f'{order_by}:{order}' in SORT_VALUES:
            filters['orderBy'], filters['order'] = order_by, order
    filters['searchTags'] = [str(tag) for tag in (tags or [])]
    if limit:
        try:
            filters['limit'] = min(max(int(limit), 1), MAX_LIMIT)
        except (TypeError, ValueError):
            pass

    skip = (state or {}).get('skip', 0)
    triggered = dash.callback_context.triggered
    source = triggered[0]['prop_id'] if triggered else ''
    if 'session-explorer-next' in source:
        skip += filters['limit']
    elif 'session-explorer-prev' in source:
        skip = max(0, skip - filters['limit'])
    elif not source.startswith('session-explorer-state'):
        # A filter change starts again from the first page.
        skip = 0
    filters['skip'] = skip

    sessions = getattr(TMonWidgets, 'accepted_sessions', []) or []
    page, total = apply_session_filters(sessions, filters)
    if total and skip >= total:
        skip = max(0, ((total - 1) // filters['limit']) * filters['limit'])
        filters['skip'] = skip
        page, total = apply_session_filters(sessions, filters)

    first = skip + 1 if total else 0
    last = min(skip + filters['limit'], total)
    info = f"{first}-{last} of {total}"
    # Writing the store re-runs this callback once; leave it untouched then so
    # the chain stops instead of resetting the page.
    state_out = no_update if skip == (state or {}).get('skip', 0) else {'skip': skip}
    return {'display': 'block'}, render_session_cards(page), info, state_out
