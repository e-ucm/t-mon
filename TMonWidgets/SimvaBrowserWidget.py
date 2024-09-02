from flask import session
import dash
from dash import html, dcc, callback
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import json
import TMonWidgets
#Import LoadProcessStatements.py
from LoadProcessStatements import load_players_info_from_content
# Import SimvaBrowser class from SimvaBrowser.py
from SimvaBrowser.SimvaBrowser import SimvaBrowser
# Import KeycloakClient class containing a Flask OIDC server from KeycloakClient.py
from SimvaBrowser.KeycloakClient import KeycloakClient
flask=KeycloakClient(homepage=False)

# Dash callback to handle login button click
@callback(
    Output('login-logout-button', 'children'),
    [Input('main-login', 'children')]
)
def login_logout_button_displayed(main):
    if flask.oidc.user_loggedin:
        return "Logout"
    else:
        return "Login"    

# Dash callback to handle login button click
@callback(
    Output('login-logout', 'children'),
    [Input('login-logout-button', 'n_clicks')]
)
def login_logout_button_click(n_clicks):
    if n_clicks > 0:
        if flask.oidc.user_loggedin:
            return dcc.Location(pathname='/logoutkeycloak', id='login-logout-link')
        else:
            return dcc.Location(pathname='/login', id='login-logout-link')

# Dash callback to handle account button style
@callback(
    [Output('account-button', 'children'),
    Output('account-button', 'style')],
    [Input('main-login', 'children')]
)
def login_logout_button(main):
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
        folder_buttons = [html.Button(f, id={'type': 'folder-button', 'index': f}, n_clicks=0) for f in browser.dirs]
        file_buttons = [html.Button(f, id={'type': 'file-button', 'index': f}, n_clicks=0, style={'backgroundColor': 'green'}) for f in browser.files if f.endswith(browser.accept)]
        run_analyse_style = {'display': 'none'}
        if not browser._isdir(browser.current_path):
            run_analyse_style = {'display': 'block'}
        appLayout = html.Div([
            html.H3(id='current-path', children=browser.current_path),
            html.Button('..', id='parent-directory', n_clicks=0, style={'display': 'block'}),
            html.Div(id='folders-div', children=folder_buttons),
            html.Div(id='files-div', children=file_buttons),
            html.Button('Run Analyse', id='run-analyse', n_clicks=0, style=run_analyse_style),
        ])
        return appLayout
    else:
        return html.H4("Connect to your SIMVA account to access to your data.")

@callback(
    [Output('current-path', 'children'),
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
     Input('run-analyse', 'n_clicks')],
    [State('current-path', 'children'),
     State('url', 'pathname')]
)
def update_browser(n_clicks_parent, folder_n_clicks, file_n_clicks, n_clicks_run_analyse, current_path, statepathname):
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
        run_analyse_style={'display': 'none'}
        folder_buttons=[]
        file_buttons=[]
        TMonWidgets.xapiData=[]
        div_list= []
        out=[]
        err=[]
        fileExists, errorFileExist=browser.file_exists(current_path)
        if fileExists:
            content_string = browser.get_file_content(current_path)
            load_players_info_from_content(
                content_string, current_path, TMonWidgets.xapiData, out, err
            )
        else:
            if errorFileExist['Code']=="NoSuchKey":
                err.append(f"Specified file at {current_path} don't exist.")
            elif errorFileExist['Code']=='AccessDenied':
                 err.append(f"Access denied to Specified file {current_path}. Check your IAM policies and bucket policies.")
            else:
                err.append(errorFileExist['Code'])
                err.append(errorFileExist['Message'])
                err.append(errorFileExist['Key'])
        div_list.append(html.Div([
                html.Div(out),
                html.Div(err),
                html.Hr(),
            ]))
        pathname=newstatepathname
        if run_dashboard:
            dashboardpath=f"{dashboard_url}"
        else:
            dashboardpath=f"/dashboard/tab=home_tab"
        print(f"Pathname : {pathname} - State : {newstatepathname} - dashboardurl : {dashboard_url}")
        if(len(err) > 0):
            return browser.current_path, folder_buttons, file_buttons, run_analyse_style, html.Div(div_list), {'display': 'none'}, f"{pathname}{dashboardpath}" 
        else:
            return browser.current_path, folder_buttons, file_buttons, run_analyse_style, html.Div(div_list), {'display': 'block'}, f"{pathname}{dashboardpath}"
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
    folder_buttons = [html.Button(f, id={'type': 'folder-button', 'index': f}, n_clicks=0) for f in browser.dirs]
    file_buttons = [html.Button(f, id={'type': 'file-button', 'index': f}, n_clicks=0, style={'backgroundColor': 'green'}) for f in browser.files if f.endswith(browser.accept)]
    run_analyse_style = {'display': 'none'} if browser._isdir(browser.current_path) else {'display': 'block'}
    print("Pathname:", pathname)
    return browser.current_path, folder_buttons, file_buttons, run_analyse_style, html.H1(""), {'display': 'none'}, pathname

simvaBrowserBody = html.Div(
    [
        dcc.Location(id='url', refresh=False), # Location component for URL handling
        html.Div(id='browser_div', children=[
                html.H3(id='current-path'),
                html.Button('..', id='parent-directory', n_clicks=0, style={'display': 'none'}),
                html.Div(id='folders-div', children=[]),
                html.Div(id='files-div', children=[]),
                html.Button('Run Analyse', id='run-analyse', n_clicks=0, style={'display': 'none'}),
            ]
        ), 
        html.Div(id='debug-browser', children=[]),
        html.Div(id='content',children=[])
    ]
)

LoginLogoutBody = html.Div(id="main-login", children=[
    html.Button(id='login-logout-button', n_clicks=0),
    html.Button(id='account-button', n_clicks=0),
    html.Div(id='login-logout'),
    html.Div(id='account',children=[]),
    html.Div(id='connection-status',children=[])
])