from flask import session
import dash
from dash import html, dcc, callback, no_update
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import json
import TMonWidgets
from TMonWidgets.TMonWidget import (
    HEADER_NAV_BUTTON_STYLE, TEXT_SECONDARY, render_simlet_tiles,
)
from TMonWidgets.SimletExplorer import parse_simlet_query, render_simlet_controls
from TMonWidgets.SessionExplorer import (
    is_simlet_path, render_session_explorer_panel,
)
from TMonWidgets import I18n
#Import LoadProcessStatements.py
from LoadProcessStatements import load_from_string, load_players_info_from_uploaded_content
# Import SimvaBrowser class from SimvaBrowser.py
from SimvaBrowser.SimvaBrowser import SimvaBrowser, merge_statements
# Import KeycloakClient class containing a Flask OIDC server from KeycloakClient.py
from SimvaBrowser.KeycloakClient import KeycloakClient
from datetime import datetime
flask=KeycloakClient(homepage=False)

# Base style of the local-file drop zone. Visibility is decided by the active
# tab and by whether the user is logged in.
UPLOAD_STYLE = {
    'width': '100%',
    'height': '60px',
    'lineHeight': '60px',
    'borderWidth': '1px',
    'borderStyle': 'dashed',
    'borderRadius': '5px',
    'textAlign': 'center',
    'margin': '10px',
}


def upload_allowed(active_tab):
    """Whether local files may be uploaded in the current state."""
    return active_tab == 'upload' and bool(flask.oidc.user_loggedin)


# Dash callback to handle login button click
@callback(
    [Output('login-logout-button', 'children'),
     Output('upload-data','style'),
     Output('upload-login-notice','children')],
    [Input('main-login', 'children'),
     Input('app-tabs', 'value')]
)
def login_logout_button_displayed(main, active_tab):
    # The drop zone lives in the Upload tab, and uploading needs a SIMVA login.
    # The tab stays visible when logged out so the notice explains why it is empty.
    style = dict(UPLOAD_STYLE)
    style['display'] = 'block' if upload_allowed(active_tab) else 'none'
    notice = '' if flask.oidc.user_loggedin else I18n.t('upload.login_notice')
    label = I18n.t('header.logout.title') if flask.oidc.user_loggedin else I18n.t('header.login.title')
    return label, style, notice
@callback(
    Output('upload-no-tab-message', 'style'),
    Input('upload-data', 'contents')
)
def show_upload_message_after_upload(contents):
    """Only prompt for a tab once there is uploaded data to visualise."""
    if contents:
        return {'display': 'block', 'color': '#3c6d7a'}
    return {'display': 'none'}


@callback(
    Output('login-logout', 'children'),
    [Input('login-logout-button', 'n_clicks')]
)
def login_logout_button_click(n_clicks):
    if n_clicks > 0:
        if flask.oidc.user_loggedin:
            global browser
            browser=None
            return dcc.Location(pathname='/logoutkeycloak', id='login-logout-link')
        else:
            return dcc.Location(pathname='/login', id='login-logout-link')

# Dash callback to handle account button style
@callback(
    [Output('account-button', 'children'),
     Output('account-button', 'style'),
     Output('header-account-item', 'style')],
    [Input('main-login', 'children')]
)
def account_button(main):
    # The account item carries only the username; it is hidden entirely while
    # logged out, along with the "Logged in as" label that used to sit beside it.
    if flask.oidc.user_loggedin:
        username = (session.get('oidc_auth_profile', {}).get('preferred_username')
                    or I18n.t('header.account'))
        return username, dict(HEADER_NAV_BUTTON_STYLE, fontSize=12, display='block'), {'display': 'flex'}
    return None, dict(HEADER_NAV_BUTTON_STYLE, display='none'), {'display': 'none'}

@callback(
    Output('account', 'children'),
    [Input('account-button', 'n_clicks')]
)
def account_button_click(n_clicks):
    if n_clicks > 0:
        if flask.oidc.user_loggedin:
            return dcc.Location(href=f'{flask.accountpage}', id='account-link')

# Dash callback to update connection status
@callback(
    Output('connection-status', 'children'),
    [Input('main-login', 'children')]
)
def update_connection_status(input_value):
    # The label is hidden; the visible username is written into the account
    # item by account_button(), so keep this value minimal.
    if flask.oidc.user_loggedin:
        return session.get('oidc_auth_profile', {}).get('preferred_username') or ''
    return ''
    
def publish_session_activities():
    """
    Tell the dashboard which activities the current selection is made of.

    Only a whole session is a choice between activities: its statements cover all of
    them, and the dashboard turns that into one button per activity. A single activity,
    or a legacy server that keeps its statements in the trace store, leaves the list
    empty and the dashboard falls back to labelling by activity id.

    Returns:
        list: The activities of the selection as [{"id": ..., "name": ...}].
    """
    if browser is None or browser.analysis_is_activity is not False:
        TMonWidgets.sessionActivities=[]
        return TMonWidgets.sessionActivities
    activities=[]
    for activity in browser.accepted_activities or []:
        activity_id=browser._get_id_from_object(activity, 'activity', 'id')
        if activity_id is None:
            continue
        activities.append({
            "id": str(activity_id),
            "name": browser._get_id_from_object(activity, 'activity', 'name') or str(activity_id)
        })
    TMonWidgets.sessionActivities=activities
    return activities


def get_analysis_outputs(pathname, dashboardpath):
    """
    Run the analysis over the current browser selection and build the callback outputs.

    Loads the statements resolved by SimvaBrowser.get_analysis_content (LRS statements
    for the selected session/activity, or the presigned trace file), then appends the
    dashboard route to the URL so the T-Mon tabs open with the data already loaded.
    """
    run_analyse_style={'display': 'none'}
    global poll_failures
    # A fresh analysis starts a fresh polling run, so drop the previous failure count.
    poll_failures = 0
    TMonWidgets.xapiData=[]
    # The activity buttons belong to the selection, so they are restated with it rather
    # than left over from the previous one.
    publish_session_activities()
    out=[]
    err=[]
    current_file_path, content_string = browser.get_analysis_content()
    if content_string is None:
        # Report why the LRS gave nothing: a failed request and a genuinely empty
        # result need different fixes, and the old wording hid which one had happened.
        detail = browser.lrs_error or "the LRS returned no statements for this selection"
        source = "the LRS" if browser.health_ok else "the LRS and the trace store"
        err.append(f"No xAPI statements available for {browser.current_path}: {detail}.")
        err.append(
            "Statements are read from the LRS only; the trace store is used as a "
            f"fallback on legacy servers. Checked: {source}."
        )
    else:
        load_from_string(
            content_string, TMonWidgets.xapiData, out, err
        )
        if len(TMonWidgets.xapiData) == 0:
            # An empty result is a valid answer, not a failure: say so instead of
            # opening the dashboard on a blank set of charts.
            err.append(
                f"The LRS holds no statements yet for {browser.current_path}. "
                "Statements appear here once the activity produces them; "
                "turn on Live updates to keep this view current."
            )
    div_list=[html.Div([
            html.Div(out),
            html.Div(err),
            html.Hr(),
        ])]
    print(f"Pathname : {pathname} - dashboardpath : {dashboardpath}")
    actual_simlet=browser._get_id_from_object(browser.actual_simlet, 'simlet', 'name') if browser.actual_simlet is not None else I18n.t('browser.select_simlet')
    actual_test=browser._get_id_from_object(browser.actual_test, 'session', 'name') if browser.actual_test is not None else I18n.t('browser.select_test')
    actual_activity=browser._get_id_from_object(browser.actual_activity, 'activity', 'name') if browser.actual_activity is not None else I18n.t('browser.select_activity')
    tmon_style = {'display': 'none'} if len(err) > 0 else {'display': 'block'}
    return browser.current_path, actual_simlet, actual_test, actual_activity, [], [], run_analyse_style, html.Div(div_list), tmon_style, f"{pathname}{dashboardpath}"


def reload_xapi_data_from_selection():
    """
    Rebuild the shared xAPI statement list from the browser's current selection.

    Reused by the initial analysis and by the poller so both normalize the statements
    the same way. Returns the number of statements now loaded.
    """
    TMonWidgets.xapiData=[]
    content = browser.get_lrs_content()
    if content is None:
        return 0
    load_from_string(content, TMonWidgets.xapiData, [], [])
    return len(TMonWidgets.xapiData)


# Consecutive failed polls, shown in the status line so a retry is visible rather than
# silent. Reset whenever a read succeeds or a new analysis is started.
poll_failures = 0


# Dash callback to let the user choose how often the LRS is polled
@callback(
    [Output('lrs-poll-interval', 'interval'),
     Output('lrs-poll-interval', 'disabled')],
    [Input('lrs-poll-rate', 'value'),
     Input('lrs-poll-enabled', 'value')]
)
def set_poll_rate(rate, enabled):
    """
    Apply the chosen polling period to the timer.

    Polling only makes sense once a session or activity is loaded, so the timer stays
    disabled until the user turns it on, keeping the server idle otherwise. The
    control's own state is the feedback here; `lrs-poll-status` is left to the poller
    so no two callbacks write the same property.
    """
    if not rate:
        raise PreventUpdate
    seconds=int(rate)
    is_enabled=bool(enabled) and flask.oidc.user_loggedin
    return seconds*1000, not is_enabled

# Dash callback to fetch new statements as they arrive
@callback(
    [Output('lrs-data-version', 'data'),
     Output('lrs-poll-status', 'children'),
     Output('lrs-poll-count', 'children')],
    [Input('lrs-poll-interval', 'n_intervals')]
)
def poll_lrs_data(n_intervals):
    """
    Pull statements that arrived since the last poll and refresh the dashboard.

    Bumps `lrs-data-version` only when new statements were actually found, so the
    charts and the data table redraw on real changes instead of on every tick.

    Data that lands after a poll is not lost: the query window trails the current time
    by a lag and overlaps the previous window, so a late statement is re-read on a
    later tick, and the LRS watermark only moves forward on a fully successful read.
    Statements already held are dropped by identity, so the overlap and any repeated
    delivery add nothing to the dashboard. A failed read leaves the version untouched
    and is reported, and the next tick simply tries the same window again.
    """
    global poll_failures
    try:
        current_browser=browser
        if current_browser is None:
            raise NameError("Browser is null.")
    except NameError:
        raise PreventUpdate
    if not current_browser.analysis_ready or current_browser.analysis_object_id is None:
        raise PreventUpdate
    if current_browser.lrs_data is None:
        # The initial load fell back to trace files, so there is no LRS window to poll.
        raise PreventUpdate

    payload=current_browser._get_lrs_statements(
        objectId=current_browser.analysis_object_id,
        is_activity=current_browser.analysis_is_activity
    )
    stamp=datetime.now().strftime("%H:%M:%S")
    if payload is None:
        # Nothing moved forward, so the next tick re-reads the very same window.
        poll_failures += 1
        return (
            None,
            f"LRS unreachable at {stamp} - retrying next tick (attempt {poll_failures})",
            str(len(current_browser.lrs_data))
        )

    merged, added=merge_statements(current_browser.lrs_data, payload)
    if added == 0:
        poll_failures = 0
        return (
            None,
            f"No new statements at {stamp} - {len(merged)} total",
            str(len(merged))
        )

    current_browser.lrs_data=merged
    total=reload_xapi_data_from_selection()
    poll_failures = 0
    print(f"POLL: {added} new statement(s) for {current_browser.current_path}, {total} total")
    return (
        (n_intervals, added, total),
        f"+{added} new statement(s) at {stamp} - {total} total",
        str(total)
    )

def browser_path_from_dashboard_url(pathname, base_path):
    """
    Translate a simlet URL into the browser's directory-style path.

    A simlet tile links to ``/simlet/<id>``; an analysed selection can also carry
    a ``/dashboard/tab=...`` suffix. The browser navigates a flat ``output/<id>/``
    tree, so the simlet id has to be lifted out of either form rather than copied
    verbatim.

    Args:
        pathname (str): The URL the app was opened at.
        base_path (str): The browser's root directory.

    Returns:
        str: The browser path for that URL, or the root when it names no simlet.
    """
    if not pathname or pathname == '/':
        return base_path
    if pathname.startswith('/simlet/'):
        # Tile links are `/simlet/<id>`; a session dashboard is
        # `/simlet/<id>/session/<id>/dashboard`. Both name a simlet id first.
        tail = pathname[len('/simlet/'):]
    elif '/dashboard' in pathname:
        tail = pathname.split('/dashboard', 1)[1].lstrip('/')
    else:
        return base_path
    parts = [part for part in tail.split('/')
             if part and '=' not in part]  # drop `tab=home_tab` and query values
    if len(parts) >= 3 and parts[1] == 'session':
        # The dashboard shortcut opens the same whole-session analysis entry as
        # the "Complete session" folder button.
        return base_path + f"{parts[0]}/{parts[2]}/Analysis/"
    parts = [part for part in parts if part != 'dashboard']
    if not parts:
        return base_path
    return base_path + '/'.join(parts) + '/'


def is_root_path(path):
    """Whether a browser path is the studies-list root of the current account."""
    if not isinstance(path, str):
        # A cleared path (e.g. the empty Div a logged-out callback writes back)
        # is not a navigable browser path, so treat it as the root.
        return True
    global browser
    try:
        base = browser.base_path
    except (NameError, AttributeError):
        base = 'output/'
    current = path.rstrip('/')
    return current in ('', str(base or '').rstrip('/'))


def render_simlet_section(studies, id_getter, search=''):
    """
    Build the heading above the simlet explorer on the studies list.

    The controls and grid live in a persistent panel (see
    :func:`render_simlet_explorer_panel`) so their ids exist in every layout
    state. Keeping them out of the callback-rebuilt folder list is what stops
    Dash from reporting callback inputs that point at missing components.

    Args:
        studies: Raw simlet objects from the SimVA API (unused here).
        id_getter: Callable ``(simlet, type, name) -> value`` of the browser.
        search: The URL query string holding the explorer state (unused here).

    Returns:
        html.H3: The "Simlets" heading.
    """
    return html.H3(I18n.t('simlets.title'), style={'margin': '0 0 4px 20px', 'fontFamily': 'Inter'})


def render_simlet_explorer_panel(studies=None, search='', style=None):
    """
    Build the persistent panel holding the simlet controls and their grid.

    The panel is present whatever the login/navigation state; a separate
    callback only changes its visibility. Its ids can therefore always be
    bound to the explorer callback.

    Args:
        studies: Loaded simlets, used to populate the tag selector.
        search: The URL query string holding the explorer state.

    Returns:
        html.Div: The controls and the grid slot, hidden by default.
    """
    return html.Div([
        render_simlet_controls(parse_simlet_query(search), studies or []),
        html.Div(id='simlet-browser-grid'),
    ], id='simlet-explorer-panel',
        style=style if style is not None else {'display': 'none'})


@callback(
    Output('simlet-explorer-panel', 'style'),
    [Input('current-path', 'children'), Input('main-login', 'children')]
)
def toggle_simlet_explorer(path, main):
    """Show the simlet controls only on the logged-in studies list."""
    visible = bool(flask.oidc.user_loggedin) and is_root_path(path)
    return {'display': 'block'} if visible else {'display': 'none'}


def simlet_level(path):
    """Whether the browser is at a simlet, with no session opened yet."""
    global browser
    try:
        base = browser.base_path
    except (NameError, AttributeError):
        base = 'output/'
    return is_simlet_path(path, base)


def render_simlet_view_panel(sessions=None, search='', style=None, session_style=None):
    """
    The two-tab view shown once a simlet is open.

    The simlet name stays above the tabs; the session and activity headings and
    the ``..`` button are replaced by the tabs at this level.
    """
    return html.Div([
        dcc.Tabs(id='simlet-view-tabs', value='sessions', children=[
            dcc.Tab(label=I18n.t('sessions.general_tab'), value='general', children=[
                html.Div(
                    I18n.t('sessions.placeholder'),
                    style={'padding': '20px', 'fontFamily': 'Inter',
                           'color': TEXT_SECONDARY}),
            ]),
            dcc.Tab(label=I18n.t('sessions.sessions_tab'), value='sessions', children=[
                render_session_explorer_panel(sessions, search, style=session_style),
            ]),
        ]),
    ], id='simlet-view-panel',
        style=style if style is not None else {'display': 'none'})


def simlet_chrome_styles(path):
    """
    Styles for the simlet name, the old navigation headings and the tab panel.

    Shared by ``init_storage`` (which rebuilds the whole browser layout) and
    the style callback, so the first render and later navigation agree.
    """
    hidden = {'display': 'none'}
    if not flask.oidc.user_loggedin or is_root_path(path):
        return hidden, hidden, hidden

    global browser
    try:
        has_test = browser.actual_test is not None
        has_activity = browser.actual_activity is not None
    except (NameError, AttributeError):
        has_test = has_activity = False
    at_simlet = simlet_level(path) or not (has_test or has_activity)

    name_style = {'display': 'block', 'fontSize': '18px',
                  'margin': '4px 0 10px 20px'}
    chrome = {'display': 'block'} if (has_test or has_activity) else hidden
    panel = {'display': 'block'} if at_simlet else hidden
    return name_style, chrome, panel


@callback(
    [Output('current-simlet', 'style'),
     Output('current-test', 'style'),
     Output('current-activity', 'style'),
     Output('parent-directory', 'style'),
     Output('simlet-view-panel', 'style')],
    Input('current-path', 'children'),
)
def toggle_browser_chrome(path):
    """Choose the chrome for the studies list, a simlet, or a deeper selection.

    The studies list shows only the Simlets grid. At the simlet level only the
    simlet name and its two tabs are shown; the session/activity headings and
    the ``..`` button appear again once a session is opened.
    """
    name_style, chrome, panel = simlet_chrome_styles(path)
    return name_style, chrome, chrome, chrome, panel


@callback(
    [Output('browser_div', 'children'),
     Output('output-t-mon', 'style', allow_duplicate=True),
     Output('url', 'pathname', allow_duplicate=True)],
    Input('main-login', 'children'),
    [State('url', 'pathname'), State('url', 'search')],
    prevent_initial_call='initial_duplicate',
)
def init_storage(main, pathname, search=''):
    if flask.oidc.user_loggedin:
        # Initialize SimvaBrowser
        global browser
        browser = SimvaBrowser(session)
        if pathname is None or pathname == '/':
            browser.current_path = browser.base_path
        elif pathname.startswith('/simlet/') or '/dashboard' in pathname:
            # Tile links keep the URL at /simlet/<id>, and analysed selections
            # add a /dashboard/tab=... suffix. Restore the matching browser
            # selection instead of falling back to the studies-list root.
            browser.current_path = browser_path_from_dashboard_url(
                pathname, browser.base_path)
        else:
            newpathname = pathname
            if newpathname.endswith(".json/"):
                newpathname=newpathname[:((len(newpathname)-1))]
            browser.current_path=browser.base_path + newpathname[1:]
        print(f"Pathname set to {pathname} - {browser.current_path} - {browser.base_path}")
        browser._update_files()
        folder_buttons = [html.Button(f"{f.get('name')} ({f.get('id')})", id={'type': 'folder-button', 'index': f.get('id')}, n_clicks=0) for f in browser.dirs]
        file_buttons = [html.Button(f, id={'type': 'file-button', 'index': f}, n_clicks=0, style={'backgroundColor': 'green'}) for f in browser.files if f.endswith(browser.accept)]
        run_analyse_style = {'display': 'none'}
        if not browser._isdir(browser.current_path):
            run_analyse_style = {'display': 'block'}
        print(f'simlet : {browser.actual_simlet} -Activity : {browser.actual_activity} - File : {browser.actual_selected_file}')
        # Store studies in TMonWidgets for access by the dashboard
        TMonWidgets.accepted_studies = browser.accepted_studies
        
        # Sessions are drawn as cards by their own panel, so at the simlet
        # level the plain folder buttons would duplicate them - and naming the
        # activities here would show them before a session is opened.
        at_root = browser.current_path == browser.base_path
        at_simlet = is_simlet_path(browser.current_path, browser.base_path)
        if at_root:
            folder_buttons = [render_simlet_section(
                TMonWidgets.accepted_studies, browser._get_id_from_object, search)]
        elif at_simlet:
            folder_buttons = []
        else:
            folder_buttons = [html.Button(f"{f.get('name')} ({f.get('id')})", id={'type': 'folder-button', 'index': f.get('id')}, n_clicks=0) for f in browser.dirs]
        TMonWidgets.accepted_sessions = browser.accepted_tests if at_simlet else []
        
        actual_simlet=browser._get_id_from_object(browser.actual_simlet, 'simlet', 'name') if browser.actual_simlet is not None else I18n.t('browser.select_simlet')
        actual_test=browser._get_id_from_object(browser.actual_test, 'session', 'name') if browser.actual_test is not None else I18n.t('browser.select_test')
        actual_activity=browser._get_id_from_object(browser.actual_activity, 'activity', 'name') if browser.actual_activity is not None else I18n.t('browser.select_activity')
        # Set the styles here, not only in the style callback: init_storage
        # replaces the whole layout, so styles written to the old components
        # on the same page load would be lost.
        name_style, chrome_style, panel_style = simlet_chrome_styles(browser.current_path)
        appLayout = html.Div([
            html.H3(id='current-path', children=browser.current_path, style={'display': 'none'}),
            html.H4(id='current-simlet', children=actual_simlet, style=name_style),
            html.H4(id='current-test', children=actual_test, style=chrome_style),
            html.H4(id='current-activity', children=actual_activity, style=chrome_style),
            html.Button('..', id='parent-directory', n_clicks=0, style=chrome_style),
            html.Div(id='folders-div', children=folder_buttons),
            html.Div(id='files-div', children=file_buttons),
            html.Button(I18n.t('browser.run_analyse'), id='run-analyse', n_clicks=0, style=run_analyse_style),
            # One persistent explorer panel in every state; its style decides
            # whether it is shown, so its ids never disappear from the layout.
            render_simlet_explorer_panel(
                TMonWidgets.accepted_studies, search,
                style={'display': 'block'} if at_root else {'display': 'none'}),
            render_simlet_view_panel(
                TMonWidgets.accepted_sessions, search, style=panel_style,
                session_style=panel_style),
        ])
        # A URL that points at an analysable selection (for example
        # /simlet/1/session/1/dashboard/default) should load the dashboard on
        # arrival, not wait for a button click.
        if getattr(browser, 'analysis_ready', False):
            dashboardpath = '/dashboard/tab=home_tab'
            if pathname and '/dashboard' in pathname:
                segment = pathname.split('/dashboard', 1)[1]
                if segment.strip('/'):
                    dashboardpath = '/dashboard/' + segment.lstrip('/')
            analysis_path = pathname.split('/dashboard', 1)[0].rstrip('/') if pathname else ''
            if not analysis_path:
                analysis_path = browser.current_path.replace(browser.base_path, '/').rstrip('/')
            try:
                outputs = get_analysis_outputs(analysis_path, dashboardpath)
                tmon_style = outputs[8]
                url = outputs[9]
                return appLayout, tmon_style, url
            except Exception as exc:  # noqa: BLE001 - never break the page load
                print(f'Auto-analysis on load failed: {exc}')
        return appLayout, {'display': 'none'}, no_update
    else:
        return (html.Div([
                html.H4(I18n.t('browser.connect')),
                html.H3(id='current-path', style={'display': 'none'}),
                html.H4(id='current-simlet', style={'display': 'none'}),
                html.H4(id='current-test', style={'display': 'none'}),
                html.H4(id='current-activity', style={'display': 'none'}),
                html.Button('..', id='parent-directory', n_clicks=0, style={'display': 'none'}),
                html.Div(id='folders-div', children=[], style={'display': 'none'}),
                html.Div(id='files-div', children=[], style={'display': 'none'}),
                html.Button(I18n.t('browser.run_analyse'), id='run-analyse', n_clicks=0, style={'display': 'none'}),
                render_simlet_explorer_panel(),
                render_simlet_view_panel(),
            ]), {'display': 'none'}, no_update)

def load_uploaded_files(list_of_contents, list_of_names, list_of_dates):
    """
    Load local xAPI-SG files into the shared statement list.

    Used by the Upload tab and by the legacy path where no SIMVA browser is
    open, so a dropped file is handled the same way in both modes.
    """
    div_list = []
    TMonWidgets.xapiData = []
    # An uploaded file belongs to no SimVA session, so the activity buttons of
    # a previous selection do not apply to it.
    TMonWidgets.sessionActivities = []
    nbError = 0
    style = {'display': 'block'}
    for c, n, d in zip(list_of_contents or [], list_of_names or [], list_of_dates or []):
        out, err = [], []
        when = datetime.fromtimestamp(d).isoformat()
        source = f"{n} {when}"
        div_list.append(html.H5(n))
        div_list.append(html.H6(when))
        load_players_info_from_uploaded_content(
            c, n, TMonWidgets.xapiData, out, err, source=source)
        div_list.append(html.Div(out))
        div_list.append(html.Div(err))
        if len(err) > 0:
            nbError += 1
        div_list.append(html.Hr())
    if nbError == len(list_of_names or []):
        style = {'display': 'none'}
    return div_list, style


def uploaded_outputs(div_list, style, filename=None, when=None):
    """The ten callback outputs for a local upload: clear the browser, show the log.

    The file name and date are part of the log shown in the dashboard content,
    not the header; the URL carries no tab so HomePage is not opened.
    """
    # Empty children must be strings, not Div components: the dashboard header
    # reads the simlet/session slots as text.
    return ('', '', '', '', '', '',
            {'display': 'none'}, div_list, style, "/dashboard/upload")


@callback(
    [Output('current-path', 'children'),
     Output('current-simlet', 'children'),
     Output('current-test', 'children'),
     Output('current-activity', 'children'),
     Output('folders-div', 'children'),
     Output('files-div', 'children'),
     Output('run-analyse', 'style'),
     Output('content', 'children'),
     Output('output-t-mon', 'style'),
     Output('url', 'pathname')
     ],
    [Input('parent-directory', 'n_clicks'),
     Input({'type': 'folder-button', 'index': dash.dependencies.ALL}, 'n_clicks'),
     Input({'type': 'file-button', 'index': dash.dependencies.ALL}, 'n_clicks'),
     Input('run-analyse', 'n_clicks'),
     Input({'type': 'session-dashboard-button', 'index': dash.dependencies.ALL}, 'n_clicks'),
     Input('upload-data', 'contents')],
    [State('current-path', 'children'),
     State('url', 'pathname'),
     State('url', 'search'),
     State('upload-data', 'filename'),
     State('upload-data', 'last_modified'),
     State('app-tabs', 'value')]
)
def update_browser(n_clicks_parent, folder_n_clicks, file_n_clicks, n_clicks_run_analyse,
                   dashboard_n_clicks, list_of_contents, current_path, statepathname,
                   state_search, list_of_names, list_of_dates, active_tab):
    # In the Upload tab a dropped file is local even if a SIMVA session is open
    # in the other tab, so it must not be read as a SimVA selection.
    if upload_allowed(active_tab) and list_of_names:
        div_list, style = load_uploaded_files(list_of_contents, list_of_names, list_of_dates)
        name = list_of_names[0] if list_of_names else None
        when = (datetime.fromtimestamp(list_of_dates[0]).isoformat()
                if list_of_dates else None)
        return uploaded_outputs(div_list, style, name, when)
    try: 
        browser
        if browser == None:
            raise NameError("Browser is null.")
    except NameError:
        print("Well, it WASN'T defined after all!")
        if list_of_names and flask.oidc.user_loggedin:
            print(f"List_of_names : {list_of_names} - list_of_dates : {list_of_dates}")
            div_list, style = load_uploaded_files(list_of_contents, list_of_names, list_of_dates)
            name = list_of_names[0] if list_of_names else None
            when = (datetime.fromtimestamp(list_of_dates[0]).isoformat()
                    if list_of_dates else None)
            return uploaded_outputs(div_list, style, name, when)
        else:
            return html.Div(),html.Div(),html.Div(),html.Div(),html.Div(),html.Div(),{'display': 'none'}, html.Div(), {'display': 'none'}, "/"
    else:
        print("Sure, it was defined.")
        ctx = dash.callback_context
        res=f"{current_path} - triggered : {ctx.triggered} - Files : {file_n_clicks} - Folders : {folder_n_clicks} - n_clicks_parent : {n_clicks_parent} - n-clicks-run-analyse : {n_clicks_run_analyse}"
        print(res)
        if not ctx.triggered:
            raise PreventUpdate
        triggered_prop_id = ctx.triggered[0]['prop_id']
        print(f'PropId : {triggered_prop_id} - State : {statepathname} - {browser.current_path} - {browser.base_path}')
        # Find the position of "/dashboard/"
        index = statepathname.find("/dashboard")
        # Slice the string up to the index if "/dashboard/" is found
        if index != -1:
            newstatepathname = statepathname[:index]
            dashboard_url = statepathname[index:]
            run_dashboard=True
        else:
            newstatepathname = statepathname
            dashboard_url = ""
            run_dashboard=False
        print(f"run_dashboard : {run_dashboard}")
        # Remove the .n_clicks suffix
        if 'parent-directory' in triggered_prop_id and int(n_clicks_parent)>0:
            print(f"Current Path : {browser.current_path} - State : {newstatepathname} ")
            if len(browser.current_path) > len(browser.base_path):
                if browser._isdir(browser.current_path):
                    browser.current_path = browser.current_path.rpartition(browser.delimiter)[0]
                browser.current_path = browser.current_path.rpartition(browser.delimiter)[0] + browser.delimiter
            else:
                browser.current_path = browser.base_path
            pathname=browser.current_path.replace(browser.base_path, "/")
            print(f"{browser.current_path} - New Path : {pathname}")
        elif ('run-analyse' in triggered_prop_id and int(n_clicks_run_analyse)>0) or run_dashboard:
            pathname=newstatepathname
            if run_dashboard:
                dashboardpath=f"{dashboard_url}"
            else:
                dashboardpath=f"/dashboard/tab=home_tab"
            print(f"State : {newstatepathname} - dashboardurl : {dashboard_url}")
            return get_analysis_outputs(pathname, dashboardpath)
        elif 'session-dashboard-button' in triggered_prop_id:
            # Shortcut from a session card: select the same "Complete session"
            # (Analysis) entry the folder navigation would have opened.
            if not any(int(click or 0) > 0 for click in (dashboard_n_clicks or [])):
                raise PreventUpdate
            button_id = json.loads(triggered_prop_id.rsplit('.n_clicks', 1)[0])
            simlet_id = browser._get_id_from_object(browser.actual_simlet, 'simlet', 'id')
            if simlet_id is None:
                raise PreventUpdate
            browser.current_path = (
                f"{browser.base_path}{simlet_id}/{button_id['index']}/Analysis/")
            browser._update_files()
            analysis_path = f"/simlet/{simlet_id}/session/{button_id['index']}"
            return get_analysis_outputs(analysis_path, "/dashboard/default")
        elif "-button"in triggered_prop_id:
            cleaned_prop_id = triggered_prop_id.replace(".n_clicks", "")
            button_id = json.loads(cleaned_prop_id)
            # Redrawing a list (for example after changing the Sessions filter)
            # re-creates its buttons with n_clicks=0. That is a render, not a
            # click, so it must not navigate into a session or activity.
            clicks = (folder_n_clicks if button_id['type'] == 'folder-button'
                      else file_n_clicks) or []
            if not any(int(click or 0) > 0 for click in clicks):
                raise PreventUpdate
            if button_id['type'] == 'folder-button':
                browser.current_path = browser.current_path + button_id['index']
            elif button_id['type'] == 'file-button':
                browser.current_path = browser.current_path + button_id["index"]
            pathname=browser.current_path.replace(browser.base_path, "/")
            # Entering a simlet from the browser should carry the same dashboard
            # URL a Simlets tile uses, with its home tab selected.
            if (button_id['type'] == 'folder-button' and browser.actual_simlet is not None
                    and browser.actual_test is None):
                simlet_id = browser._get_id_from_object(browser.actual_simlet, 'simlet', 'id')
                if simlet_id is not None:
                    pathname = f"/simlet/{simlet_id}"
        else:
            print("Nothing to do ! Prevent update")
            raise PreventUpdate
        browser._update_files()
        # Entering the session level "Complete session" entry or a single activity
        # means the selection is directly analysable: load its LRS statements and
        # jump straight to the dashboard instead of waiting for a button click.
        if browser.analysis_ready:
            dashboardpath=f"/dashboard/tab=home_tab"
            analysis_path=pathname.rstrip('/')
            print(f"Auto analysis for {analysis_path} (is_activity={browser.analysis_is_activity})")
            return get_analysis_outputs(analysis_path, dashboardpath)
        at_root = browser.current_path == browser.base_path
        at_simlet = is_simlet_path(browser.current_path, browser.base_path)
        if at_root:
            # Coming back up with ".." lands on the studies list again, so show
            # the same Simlets explorer as on a fresh load of "/".
            folder_buttons = [render_simlet_section(
                TMonWidgets.accepted_studies, browser._get_id_from_object, state_search)]
        elif at_simlet:
            # Sessions are drawn by their own panel; no activities here until
            # one of them is opened.
            folder_buttons = []
        else:
            folder_buttons = [html.Button(f"{f.get('name')} ({f.get('id')})", id={'type': 'folder-button', 'index': f.get("id")}, n_clicks=0) for f in browser.dirs]
        TMonWidgets.accepted_sessions = browser.accepted_tests if at_simlet else []
        file_buttons = [html.Button(f, id={'type': 'file-button', 'index': f}, n_clicks=0, style={'backgroundColor': 'green'}) for f in browser.files if f.endswith(browser.accept)]
        run_analyse_style = {'display': 'none'} if browser._isdir(browser.current_path) else {'display': 'block'}
        print("Pathname:", pathname)
        actual_simlet=browser._get_id_from_object(browser.actual_simlet, 'simlet', 'name') if browser.actual_simlet is not None else I18n.t('browser.select_simlet')
        actual_test=browser._get_id_from_object(browser.actual_test, 'session', 'name') if browser.actual_test is not None else I18n.t('browser.select_test')
        actual_activity=browser._get_id_from_object(browser.actual_activity, 'activity', 'name') if browser.actual_activity is not None else I18n.t('browser.select_activity')
        return browser.current_path, actual_simlet,actual_test, actual_activity, folder_buttons, file_buttons, run_analyse_style, html.H1(""), {'display': 'none'}, pathname

simvaBrowserBody = html.Div(
    [
        dcc.Location(id='url', refresh=False), # Location component for URL handling
        html.Div(id='browser_div', children=[
                html.H3(id='current-path', style={'display': 'none'}),
                html.H4(id='current-simlet'),
                html.H4(id='current-test'),
                html.H4(id='current-activity'),
                html.Button('..', id='parent-directory', n_clicks=0, style={'display': 'none'}),
                html.Div(id='folders-div', children=[]),
                html.Div(id='files-div', children=[]),
                html.Button(I18n.t('browser.run_analyse'), id='run-analyse', n_clicks=0, style={'display': 'none'}),
                # The panels stay in the layout in every browser state; only
                # their visibility changes, so the callback ids always resolve.
                render_simlet_explorer_panel(),
                render_simlet_view_panel(),
            ]
        ),
        html.Div(id='debug-browser', children=[]),
        # Live update plumbing: the timer is disabled until a session/activity is
        # analysed and the user enables it, and the store only changes when the
        # poller actually found new statements, which is what redraws the dashboard.
        dcc.Interval(id='lrs-poll-interval', interval=10000, disabled=True, n_intervals=0),
        dcc.Store(id='lrs-data-version', data=0),
    ]
)

# Local-file drop zone, revealed by the Upload tab. It is one component shared
# with the browser callbacks, so there is never a second `upload-data` id.
TMonUploadPanel = html.Div(
    id='upload-panel',
    style={'display': 'none', 'padding': '20px'},
    children=[
        html.H3('Upload xAPI-SG files'),
        html.P('Select one or more JSON files to analyse after logging in to SIMVA.'),
        html.P(I18n.t('dashboard.no_tab_selected'), id='upload-no-tab-message',
               style={'display': 'none', 'color': '#3c6d7a'}),
        html.Div(id='upload-login-notice', children='',
                 style={'color': '#b34700', 'margin': '10px 0'}),
        dcc.Upload(
            id='upload-data',
            children=html.Div(['Drag and Drop or ', html.A('Select Files')]),
            style=dict(UPLOAD_STYLE, display='none'),
            multiple=True,
        ),
    ],
)

# Both a local upload and a SIMVA analysis log their result here, so the log is
# outside the two tab panels and stays visible whichever mode is active.
TMonContent = html.Div(id='content', children=[])

