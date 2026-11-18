from flask import session
import dash
from dash import html, dcc, callback
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import json
import TMonWidgets
from TMonWidgets.TMonWidget import HEADER_BUTTON_STYLE, render_simlet_tiles
from TMonWidgets.SimletExplorer import parse_simlet_query, render_simlet_controls
from TMonWidgets.SessionExplorer import (
    is_simlet_path, render_session_explorer_panel,
)
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
    notice = '' if flask.oidc.user_loggedin else 'Please log in to upload files.'
    return ("Logout" if flask.oidc.user_loggedin else "Login"), style, notice
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
    Output('account-button', 'style')],
    [Input('main-login', 'children')]
)
def account_button(main):
    # The callback owns this component's style, so it has to keep the header's
    # button appearance as well as changing its visibility.
    if flask.oidc.user_loggedin:
        return "Account", dict(HEADER_BUTTON_STYLE, display='block')
    else:
        return None, dict(HEADER_BUTTON_STYLE, display='none')

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
    if flask.oidc.user_loggedin:
        user_info = session.get('oidc_auth_profile', {})
        preferred_username = user_info.get('preferred_username')
        return f'Logged in as {preferred_username}'
    else:
        return 'Not logged in'
    
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
    actual_simlet=browser._get_id_from_object(browser.actual_simlet, 'simlet', 'name') if browser.actual_simlet is not None else "Select a simlet"
    actual_test=browser._get_id_from_object(browser.actual_test, 'session', 'name') if browser.actual_test is not None else "Select an test"
    actual_activity=browser._get_id_from_object(browser.actual_activity, 'activity', 'name') if browser.actual_activity is not None else "Select an activity"
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
        # Tile links are `/simlet/<id>` with no trailing slash, so the id is the
        # remainder after the prefix rather than a segment of a dashboard path.
        tail = pathname[len('/simlet/'):]
    elif '/dashboard' in pathname:
        tail = pathname.split('/dashboard', 1)[1].lstrip('/')
    else:
        return base_path
    parts = [part for part in tail.split('/')
             if part and '=' not in part]  # drop `tab=home_tab` and query values
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
    return html.H3('Simlets', style={'margin': '0 0 4px 20px', 'fontFamily': 'Inter'})


def render_simlet_explorer_panel(studies=None, search=''):
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
    ], id='simlet-explorer-panel', style={'display': 'none'})


@callback(
    Output('simlet-explorer-panel', 'style'),
    [Input('current-path', 'children'), Input('main-login', 'children')]
)
def toggle_simlet_explorer(path, main):
    """Show the simlet controls only on the logged-in studies list."""
    visible = bool(flask.oidc.user_loggedin) and is_root_path(path)
    return {'display': 'block'} if visible else {'display': 'none'}


@callback(
    [Output('current-simlet', 'style'),
     Output('current-test', 'style'),
     Output('current-activity', 'style'),
     Output('parent-directory', 'style')],
    Input('current-path', 'children'),
)
def toggle_browser_chrome(path):
    """Hide the selection headings and parent button on the studies list.

    At the root there is nothing selected and nowhere to go back to: the SIMVA
    tab shows only the Simlets grid. Deeper in the tree the browser navigation
    is shown as before. A logged-out visitor never sees it, including the `..`
    button, whatever path the URL happens to carry.
    """
    visible = bool(flask.oidc.user_loggedin) and not is_root_path(path)
    style = {'display': 'block'} if visible else {'display': 'none'}
    return style, style, style, style


@callback(
    Output('browser_div', 'children'),
    Input('main-login', 'children'),
    [State('url', 'pathname'), State('url', 'search')]
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
        
        actual_simlet=browser._get_id_from_object(browser.actual_simlet, 'simlet', 'name') if browser.actual_simlet is not None else "Select a simlet"
        actual_test=browser._get_id_from_object(browser.actual_test, 'session', 'name') if browser.actual_test is not None else "Select an test"
        actual_activity=browser._get_id_from_object(browser.actual_activity, 'activity', 'name') if browser.actual_activity is not None else "Select an activity"
        chrome_style = ({'display': 'none'} if browser.current_path == browser.base_path
                        else {'display': 'block'})
        appLayout = html.Div([
            html.H3(id='current-path', children=browser.current_path, style={'display': 'none'}),
            html.H4(id='current-simlet', children=actual_simlet, style=chrome_style),
            html.H4(id='current-test', children=actual_test, style=chrome_style),
            html.H4(id='current-activity', children=actual_activity, style=chrome_style),
            html.Button('..', id='parent-directory', n_clicks=0, style=chrome_style),
            html.Div(id='folders-div', children=folder_buttons),
            html.Div(id='files-div', children=file_buttons),
            html.Button('Run Analyse', id='run-analyse', n_clicks=0, style=run_analyse_style),
            # One persistent explorer panel in every state; its style decides
            # whether it is shown, so its ids never disappear from the layout.
            render_simlet_explorer_panel(TMonWidgets.accepted_studies, search),
            render_session_explorer_panel(TMonWidgets.accepted_sessions, search),
        ])
        return appLayout
    else:
        return html.Div([
                html.H4("Connect to your SIMVA account to access to your data."),
                html.H3(id='current-path', style={'display': 'none'}),
                html.H4(id='current-simlet', style={'display': 'none'}),
                html.H4(id='current-test', style={'display': 'none'}),
                html.H4(id='current-activity', style={'display': 'none'}),
                html.Button('..', id='parent-directory', n_clicks=0, style={'display': 'none'}),
                html.Div(id='folders-div', children=[], style={'display': 'none'}),
                html.Div(id='files-div', children=[], style={'display': 'none'}),
                html.Button('Run Analyse', id='run-analyse', n_clicks=0, style={'display': 'none'}),
                render_simlet_explorer_panel(),
                render_session_explorer_panel(),
            ])

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
        div_list.append(html.H5(n))
        div_list.append(html.H6(datetime.fromtimestamp(d)))
        load_players_info_from_uploaded_content(c, n, TMonWidgets.xapiData, out, err)
        div_list.append(html.Div(out))
        div_list.append(html.Div(err))
        if len(err) > 0:
            nbError += 1
        div_list.append(html.Hr())
    if nbError == len(list_of_names or []):
        style = {'display': 'none'}
    return div_list, style


def uploaded_outputs(div_list, style):
    """The ten callback outputs for a local upload: clear the browser, show the log."""
    empty = html.Div()
    return (empty, empty, empty, empty, empty, empty,
            {'display': 'none'}, div_list, style, "/dashboard/tab=home_tab")


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
     Input('upload-data', 'contents')],
    [State('current-path', 'children'),
     State('url', 'pathname'),
     State('url', 'search'),
     State('upload-data', 'filename'),
     State('upload-data', 'last_modified'),
     State('app-tabs', 'value')]
)
def update_browser(n_clicks_parent, folder_n_clicks, file_n_clicks, n_clicks_run_analyse,
                   list_of_contents, current_path, statepathname, state_search,
                   list_of_names, list_of_dates, active_tab):
    # In the Upload tab a dropped file is local even if a SIMVA session is open
    # in the other tab, so it must not be read as a SimVA selection.
    if upload_allowed(active_tab) and list_of_names:
        div_list, style = load_uploaded_files(list_of_contents, list_of_names, list_of_dates)
        return uploaded_outputs(div_list, style)
    try: 
        browser
        if browser == None:
            raise NameError("Browser is null.")
    except NameError:
        print("Well, it WASN'T defined after all!")
        if list_of_names and flask.oidc.user_loggedin:
            print(f"List_of_names : {list_of_names} - list_of_dates : {list_of_dates}")
            div_list, style = load_uploaded_files(list_of_contents, list_of_names, list_of_dates)
            return uploaded_outputs(div_list, style)
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
        actual_simlet=browser._get_id_from_object(browser.actual_simlet, 'simlet', 'name') if browser.actual_simlet is not None else "Select a simlet"
        actual_test=browser._get_id_from_object(browser.actual_test, 'session', 'name') if browser.actual_test is not None else "Select an test"
        actual_activity=browser._get_id_from_object(browser.actual_activity, 'activity', 'name') if browser.actual_activity is not None else "Select an activity"
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
                html.Button('Run Analyse', id='run-analyse', n_clicks=0, style={'display': 'none'}),
                # The panels stay in the layout in every browser state; only
                # their visibility changes, so the callback ids always resolve.
                render_simlet_explorer_panel(),
                render_session_explorer_panel(),
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

