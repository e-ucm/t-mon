from flask import session
import dash
from dash import html, dcc, callback
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import json
import TMonWidgets
#Import LoadProcessStatements.py
from LoadProcessStatements import load_from_string, load_players_info_from_uploaded_content
# Import SimvaBrowser class from SimvaBrowser.py
from SimvaBrowser.SimvaBrowser import SimvaBrowser, merge_statements
# Import KeycloakClient class containing a Flask OIDC server from KeycloakClient.py
from SimvaBrowser.KeycloakClient import KeycloakClient
from datetime import datetime
flask=KeycloakClient(homepage=False)

# Dash callback to handle login button click
@callback(
    [Output('login-logout-button', 'children'),
     Output('upload-data','style')],
    [Input('main-login', 'children')]
)
def login_logout_button_displayed(main):
    if flask.oidc.user_loggedin:
        return "Logout", {'display': 'None'}
    else:
        return "Login", {'display': 'block',
                         'width': '100%',
                'height': '60px',
                'lineHeight': '60px',
                'borderWidth': '1px',
                'borderStyle': 'dashed',
                'borderRadius': '5px',
                'textAlign': 'center',
                'margin': '10px'}  

# Dash callback to handle login button click
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
    if flask.oidc.user_loggedin:
        return "Account", {'display': 'block'}
    else:
        return None, {'display': 'none'}

# Dash callback to handle login button click
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
    actual_study=browser._get_id_from_object(browser.actual_study, 'simlet', 'name') if browser.actual_study is not None else "Select a study"
    actual_test=browser._get_id_from_object(browser.actual_test, 'session', 'name') if browser.actual_test is not None else "Select an test"
    actual_activity=browser._get_id_from_object(browser.actual_activity, 'activity', 'name') if browser.actual_activity is not None else "Select an activity"
    tmon_style = {'display': 'none'} if len(err) > 0 else {'display': 'block'}
    return browser.current_path, actual_study, actual_test, actual_activity, [], [], run_analyse_style, html.Div(div_list), tmon_style, f"{pathname}{dashboardpath}"


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

    payload=current_browser._get_lrs_data_from_simva_api(
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

# Dash callback to handle login button click
@callback(
    Output('browser_div', 'children'),
    Input('main-login', 'children'), 
    State('url', 'pathname')
)
def init_storage(main, pathname):
    if flask.oidc.user_loggedin:
        # Initialize SimvaBrowser
        global browser
        browser = SimvaBrowser(session)
        if pathname is None or pathname == '/':
            browser.current_path= browser.base_path
        else:
            # Find the position of "/dashboard/"
            index = pathname.find("/dashboard")
            # Slice the string up to the index if "/dashboard/" is found
            if index != -1:
                newpathname = pathname[:index]
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
        print(f'Study : {browser.actual_study} -Activity : {browser.actual_activity} - File : {browser.actual_selected_file}')
        actual_study=browser._get_id_from_object(browser.actual_study, 'simlet', 'name') if browser.actual_study is not None else "Select a study"
        actual_test=browser._get_id_from_object(browser.actual_test, 'session', 'name') if browser.actual_test is not None else "Select an test"
        actual_activity=browser._get_id_from_object(browser.actual_activity, 'activity', 'name') if browser.actual_activity is not None else "Select an activity"
        appLayout = html.Div([
            html.H3(id='current-path', children=browser.current_path, style={'display': 'none'}),
            html.H4(id='current-study', children=actual_study),
            html.H4(id='current-test', children=actual_test),
            html.H4(id='current-activity', children=actual_activity),
            html.Button('..', id='parent-directory', n_clicks=0, style={'display': 'block'}),
            html.Div(id='folders-div', children=folder_buttons),
            html.Div(id='files-div', children=file_buttons),
            html.Button('Run Analyse', id='run-analyse', n_clicks=0, style=run_analyse_style),
        ])
        return appLayout
    else:
        return html.Div([
                html.H4("Connect to your SIMVA account to access to your data or Drag and Drop / Select file to visualize your data."),
                html.H3(id='current-path', style={'display': 'none'}),
                html.H4(id='current-study', style={'display': 'none'}),
                html.H4(id='current-test', style={'display': 'none'}),
                html.H4(id='current-activity', style={'display': 'none'}),
                html.Button('..', id='parent-directory', n_clicks=0, style={'display': 'none'}),
                html.Div(id='folders-div', children=[], style={'display': 'none'}),
                html.Div(id='files-div', children=[], style={'display': 'none'}),
                html.Button('Run Analyse', id='run-analyse', n_clicks=0, style={'display': 'none'}),
            ])

@callback(
    [Output('current-path', 'children'),
     Output('current-study', 'children'),
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
     State('upload-data', 'filename'),
    State('upload-data', 'last_modified')]
)
def update_browser(n_clicks_parent, folder_n_clicks, file_n_clicks, n_clicks_run_analyse, list_of_contents, current_path, statepathname, list_of_names, list_of_dates):
    try: 
        browser
        if browser == None:
            raise NameError("Browser is null.")
    except NameError:
        print("Well, it WASN'T defined after all!")
        if list_of_names:
            print(f"List_of_names : {list_of_names} - list_of_dates : {list_of_dates}")
            div_list = []
            TMonWidgets.xapiData = []
            nbError=0
            style={'display': 'block'}
            for c, n, d in zip(list_of_contents, list_of_names, list_of_dates):
                out, err = [], []
                div_list.append(html.H5(n))
                div_list.append(html.H6(datetime.fromtimestamp(d)))
                load_players_info_from_uploaded_content(c, n, TMonWidgets.xapiData, out, err)
                div_list.append(html.Div(out))
                div_list.append(html.Div(err))
                if len(err) > 0 : 
                    nbError+=1
                div_list.append(html.Hr())
            if nbError == len(list_of_names):
                style={'display': 'none'}
            return html.Div(),html.Div(),html.Div(),html.Div(),html.Div(),html.Div(),{'display': 'none'}, div_list, style, f"/dashboard/tab=home_tab"
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
            if button_id['type'] == 'folder-button':
                browser.current_path = browser.current_path + button_id['index']
            elif button_id['type'] == 'file-button':
                browser.current_path = browser.current_path + button_id["index"]
            pathname=browser.current_path.replace(browser.base_path, "/")
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
        folder_buttons = [html.Button(f"{f.get('name')} ({f.get('id')})", id={'type': 'folder-button', 'index': f.get("id")}, n_clicks=0) for f in browser.dirs]
        file_buttons = [html.Button(f, id={'type': 'file-button', 'index': f}, n_clicks=0, style={'backgroundColor': 'green'}) for f in browser.files if f.endswith(browser.accept)]
        run_analyse_style = {'display': 'none'} if browser._isdir(browser.current_path) else {'display': 'block'}
        print("Pathname:", pathname)
        actual_study=browser._get_id_from_object(browser.actual_study, 'simlet', 'name') if browser.actual_study is not None else "Select a study"
        actual_test=browser._get_id_from_object(browser.actual_test, 'session', 'name') if browser.actual_test is not None else "Select an test"
        actual_activity=browser._get_id_from_object(browser.actual_activity, 'activity', 'name') if browser.actual_activity is not None else "Select an activity"
        return browser.current_path, actual_study,actual_test, actual_activity, folder_buttons, file_buttons, run_analyse_style, html.H1(""), {'display': 'none'}, pathname

simvaBrowserBody = html.Div(
    [
        dcc.Location(id='url', refresh=False), # Location component for URL handling
        html.Div(id='browser_div', children=[
                html.H3(id='current-path', style={'display': 'none'}),
                html.H4(id='current-study'),
                html.H4(id='current-test'),
                html.H4(id='current-activity'),
                html.Button('..', id='parent-directory', n_clicks=0, style={'display': 'none'}),
                html.Div(id='folders-div', children=[]),
                html.Div(id='files-div', children=[]),
                html.Button('Run Analyse', id='run-analyse', n_clicks=0, style={'display': 'none'}),
            ]
        ),
        dcc.Upload(
            id='upload-data',
            children=html.Div([
                'Drag and Drop or ',
                html.A('Select Files')
            ]),
            style={
                'width': '100%',
                'height': '60px',
                'lineHeight': '60px',
                'borderWidth': '1px',
                'borderStyle': 'dashed',
                'borderRadius': '5px',
                'textAlign': 'center',
                'margin': '10px'
            },
            # Allow multiple files to be uploaded
            multiple=True
        ),
        html.Div(id='debug-browser', children=[]),
        html.Div(id='content',children=[]),
        # Live update plumbing: the timer is disabled until a session/activity is
        # analysed and the user enables it, and the store only changes when the
        # poller actually found new statements, which is what redraws the dashboard.
        dcc.Interval(id='lrs-poll-interval', interval=10000, disabled=True, n_intervals=0),
        dcc.Store(id='lrs-data-version', data=0),
    ]
)

LoginLogoutBody = html.Div(id="main-login", children=[
    html.Button(id='login-logout-button', n_clicks=0),
    html.Button(id='account-button', n_clicks=0),
    html.Div(id='login-logout'),
    html.Div(id='account',children=[]),
    html.Div(id='connection-status',children=[])
])