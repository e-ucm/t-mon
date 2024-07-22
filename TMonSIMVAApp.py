from flask import redirect, url_for, session
import dash
from dash import html, dcc, dash_table
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import json
import plotly.express as px

#Import fileBrowserAndUploadButtonToLoadProcessStatements.py
from fileBrowserAndUploadButtonToLoadProcessStatements import load_players_info_from_content
# Import SimvaBrowser from simvaWidget.py
from simvaWidget import SimvaBrowser
# Import Flask server from keycloakAuth.py
from keycloakAuth import KeycloakClient
flask=KeycloakClient(homepage=False)
# Initialize Dash app with Flask server
app = dash.Dash(__name__, server=flask.flaskServer)
# If you set host or port differently
http= "https://" if app.server.config.get('SECURE', False) else "http://"
debug=app.server.config.get('DEBUG', False),
host = app.server.config.get('HOST', '127.0.0.1')
port = app.server.config.get('PORT', 5000)

# Dash callback to handle login button click
@app.callback(
    Output('login-logout-button', 'children'),
    [Input('main', 'children')]
)
def login_logout_button(main):
    if flask.oidc.user_loggedin:
        return "Logout"
    else:
        return "Login"    

# Dash callback to handle login button click
@app.callback(
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
@app.callback(
    [Output('account-button', 'children'),
    Output('account-button', 'style')],
    [Input('main', 'children')]
)
def login_logout_button(main):
    if flask.oidc.user_loggedin:
        return "Account", {'display': 'block'}
    else:
        return None, {'display': 'none'}

# Dash callback to handle login button click
@app.callback(
    Output('account', 'children'),
    [Input('account-button', 'n_clicks')]
)
def account_button_click(n_clicks):
    if n_clicks > 0:
        if flask.oidc.user_loggedin:
            return dcc.Location(href=f'{flask.accountpage}{http}{host}:{port}', id='account-link')

# Dash callback to update connection status
@app.callback(
    Output('connection-status', 'children'),
    [Input('main', 'children')]
)
def update_connection_status(input_value):
    if flask.oidc.user_loggedin:
        user_info = session.get('oidc_auth_profile', {})
        preferred_username = user_info.get('preferred_username')
        return f'Logged in as {preferred_username} - {session}'
    else:
        return 'Not logged in'
    
# Dash callback to handle login button click
@app.callback(
    [Output('browser_div', 'children')],
    [Input('main', 'children')]
)
def init_storage(main):
    if flask.oidc.user_loggedin:
        # Initialize SimvaBrowser
        global browser
        browser = SimvaBrowser(session)
        folder_buttons = [html.Button(f, id={'type': 'folder-button', 'index': f}, n_clicks=0) for f in browser.dirs]
        file_buttons = [html.Button(f, id={'type': 'file-button', 'index': f}, n_clicks=0, style={'background-color': 'green'}) for f in browser.files if f.endswith(browser.accept)]
        run_analyse_style = {'display': 'none'}
        if not browser._isdir(browser.current_path):
            run_analyse_style = {'display': 'block'}
        appLayout = [html.Div([
            html.H3(id='current-path', children=browser.current_path),
            html.Button('..', id='parent-directory', n_clicks=0, style={'display': 'block'}),
            html.Div(id='folders-div', children=folder_buttons),
            html.Div(id='files-div', children=file_buttons),
            html.Button('Run Analyse', id='run-analyse', n_clicks=0, style=run_analyse_style)
        ])]
        return appLayout

@app.callback(
    [Output('current-path', 'children'),
     Output('folders-div', 'children'),
     Output('files-div', 'children'),
     Output('run-analyse', 'style'),
     Output('debug-browser', 'children')],
    [Input('parent-directory', 'n_clicks'),
     Input({'type': 'folder-button', 'index': dash.dependencies.ALL}, 'n_clicks'),
     Input({'type': 'file-button', 'index': dash.dependencies.ALL}, 'n_clicks')],
    [State('current-path', 'children')]
)
def update_browser(n_clicks_parent, folder_n_clicks, file_n_clicks, current_path):
    ctx = dash.callback_context
    res=f"{current_path} - triggered : {ctx.triggered} - Files : {file_n_clicks} - Folders : {folder_n_clicks} - n_clicks_parent : {n_clicks_parent}"
    print(res)
    if not ctx.triggered:
        raise PreventUpdate
    triggered_prop_id = ctx.triggered[0]['prop_id']
    # Remove the .n_clicks suffix
    cleaned_prop_id = triggered_prop_id.rsplit('.', 1)[0]
    if 'parent-directory' in cleaned_prop_id:
        if len(browser.current_path) > len(browser.base_path):
            if browser._isdir(browser.current_path):
                browser.current_path = browser.current_path.rpartition(browser.delimiter)[0]
            browser.current_path = browser.current_path.rpartition(browser.delimiter)[0] + browser.delimiter
        else:
            browser.current_path = browser.base_path
    else:
        button_id = json.loads(cleaned_prop_id)
        if button_id['type'] == 'folder-button':
            browser.current_path = browser.current_path + button_id['index']
        elif button_id['type'] == 'file-button':
            browser.current_path = browser.current_path + button_id["index"]
    
    browser._update_files()
    
    folder_buttons = [html.Button(f, id={'type': 'folder-button', 'index': f}, n_clicks=0) for f in browser.dirs]
    file_buttons = [html.Button(f, id={'type': 'file-button', 'index': f}, n_clicks=0, style={'background-color': 'green'}) for f in browser.files if f.endswith(browser.accept)]
    run_analyse_style = {'display': 'none'} if browser._isdir(browser.current_path) else {'display': 'block'}
    
    return browser.current_path, folder_buttons, file_buttons, run_analyse_style, [html.H1(f'Res : {res}')]


@app.callback(
    Output('content', 'children'),
    [Input('run-analyse', 'n_clicks')],
    [State('current-path', 'children')]
)
def run_analyse(n_clicks, current_path):
    if n_clicks > 0:
        global xapiData, timeformats
        #players_info={}
        xapiData=[]
        div_list= []
        out=[]
        err=[]
        timeformats=['%Y-%m-%dT%H:%M:%SZ','%Y-%m-%dT%H:%M:%S.%fZ']
        content_string = browser.get_file_content(current_path)
        try:
            load_players_info_from_content(
                content_string, current_path, xapiData, out, err
            )
            # Normalize the JSON data to a pandas DataFrame
            import pandas as pd
            df = pd.json_normalize(xapiData)
            # Convert the DataFrame to a dictionary suitable for DataTable
            data = df.to_dict('records')
            div_list.append(html.Div([
                    html.Div(out),
                    html.Div(err),
                    html.Hr(),
                    html.Div([
                        html.H3("Length table : " + str(len(xapiData))),
                        dash_table.DataTable(
                            columns=[{"name": i, "id": i} for i in df.columns],
                            data=data
                    )])
                ]))
        except Exception as e:
            print(e)
            div_list.append(html.Div(
                html.Div([
                    'There was an error processing this file.'
                ]),
                html.Div(out),
                html.Div(err)
            ))
        
        return html.Div(div_list)
    else:
        raise PreventUpdate

# Layout of the dashboard
app.layout = html.Div(id="main", children=[
    html.H1('Secure Dashboard'),
    html.Button(id='login-logout-button', n_clicks=0),
    html.Button(id='account-button', n_clicks=0),
    html.Div(id='login-logout'),
    html.Div(id='account',children=["Account"]),
    html.Div(id='connection-status',children=[]),
    html.Div(id='browser_div', children=[
        html.H3(id='current-path'),
        html.Button('..', id='parent-directory', n_clicks=0, style={'display': 'none'}),
        html.Div(id='folders-div', children=[]),
        html.Div(id='files-div', children=[]),
        html.Button('Run Analyse', id='run-analyse', n_clicks=0, style={'display': 'none'})
    ]),
    html.Div(id='debug-browser', children=[]),
    html.Div(id='content',children=[])
])

if __name__ == '__main__':
    app.run(debug=debug, port=port)
    # Construct the URL
    url = f'{http}{host}:{port}'
    print(f'The app is running at {url}')