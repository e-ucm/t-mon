import os
from flask import jsonify, request
from dash import Dash, dcc, html, Input, Output, State, no_update
from dash.exceptions import PreventUpdate
from TMonWidgets.SimvaBrowserWidget import (
    flask, simvaBrowserBody, TMonUploadPanel,
)
from TMonWidgets import TMonWidget, I18n
from TMonWidgets.PageConfig import (
    delete_named, list_saved, load_named, save_named,
)

# Initialize Dash app with Flask server. The explicit assets folder keeps the
# logo images resolvable no matter which directory the app is launched from.
app = Dash(
    __name__,
    server=flask.flaskServer,
    serve_locally=True,
    assets_folder=os.path.join(os.path.dirname(__file__), 'assets'),
    # The simlet explorer's controls and grid are created by the callback that
    # rebuilds the studies-list root, so they are not in the initial layout.
    # Dash has to accept those ids as callback inputs/outputs.
    #suppress_callback_exceptions=True,
)

# Layout of the dashboard. The top tabs choose between analysing local files and
# browsing SIMVA; the dashboard below them is shared by both modes.
app.layout=html.Div(
    [
        TMonWidget.TMonSimvaHeader,
        dcc.Tabs(
            id='app-tabs',
            value='simva',
            children=[
                dcc.Tab(label=I18n.t('app.tab.simva'), value='simva',
                        id='app-tab-simva'),
                dcc.Tab(label=I18n.t('app.tab.upload'), value='upload',
                        id='app-tab-upload'),
            ],
            colors={
                'border': '#ddd',
                'primary': TMonWidget.BRAND_ORANGE,
                'background': '#fff',
            },
        ),
        html.Div(id='simva-panel', children=[simvaBrowserBody]),
        TMonUploadPanel,
        TMonWidget.TMonBody,
        TMonWidget.TMonFooter,
    ],
    style={
        'minHeight': '100vh',
        'display': 'flex',
        'flexDirection': 'column',
    },
)


def simlet_selected(pathname):
    """
    Whether the URL points at a simlet rather than at the studies list.

    A tile opens ``/simlet/<id>`` and browsing deeper keeps the id in the path.
    The ``/dashboard/...`` suffix and the upload flow's URL carry no simlet of
    their own, so neither counts as a selection.

    Args:
        pathname (str): The current browser path.

    Returns:
        bool: True when a simlet is selected.
    """
    if not pathname or pathname == '/':
        return False
    path = str(pathname).split('/dashboard', 1)[0].rstrip('/')
    return bool(path) and path not in ('/simlet', '/')


@app.callback(
    [Output('app-tabs', 'style'),
     Output('simva-panel', 'style'),
     Output('upload-panel', 'style')],
    [Input('app-tabs', 'value'),
     Input('url', 'pathname'),
     Input('output-t-mon', 'style')],
)
def switch_mode(tab, pathname, dashboard_style):
    """Show only the panel belonging to the selected mode.

    Once a simlet is selected the mode tabs are in the way: the page is about
    that one simlet, so the SIMVA browser stays and both tabs disappear. Going
    back up to the studies list (``/``) brings them back.
    """
    # The Tabs component draws its tab bar as a flex row. Setting `display:
    # block` here would override that and stack "SIMVA" over "Upload file", so
    # the visible state has to keep it a flex row.
    visible_tabs = {'display': 'flex', 'flexDirection': 'row'}
    hidden = {'display': 'none'}
    if isinstance(dashboard_style, dict) and dashboard_style.get('display') == 'block':
        # The dashboard has its own header, sidebar and content; the SIMVA
        # browser and the mode tabs are no longer part of the page.
        return hidden, hidden, hidden
    if simlet_selected(pathname):
        return {'display': 'none'}, {'display': 'block'}, {'display': 'none'}
    if tab == 'upload':
        return (visible_tabs, {'display': 'none'},
                {'display': 'block', 'padding': '20px'})
    return visible_tabs, {'display': 'block'}, {'display': 'none'}


@app.callback(
    Output('live-updates-footer', 'style'),
    Input('url', 'pathname')
)
def toggle_live_updates(pathname):
    return TMonWidget.live_updates_style(pathname)


@app.callback(
    [Output('return-button', 'style'), Output('return-button', 'href')],
    Input('url', 'pathname')
)
def update_return_button(pathname):
    """Link back to the parent page everywhere except the studies list."""
    target = TMonWidget.return_target(pathname)
    if not target:
        return {'display': 'none'}, no_update
    return {'display': 'inline-block'}, target


@app.callback(
    [Output('i18n-location', 'href'),
     Output('header-language', 'value'),
     Output('header-contact-label', 'children'),
     Output('app-tab-simva', 'label'),
     Output('app-tab-upload', 'label'),
     Output('upload-no-tab-message', 'children'),
     Output('return-button', 'children')],
    Input('header-language', 'value'),
    State('url', 'search')
)
def change_language(language, search):
    """Remember the chosen language and keep the selector showing it.

    On a fresh load the dropdown has no value yet, so the remembered language
    (session, or ``lng`` in the URL) is selected instead of the English default.
    Only a real change from the user triggers a reload.
    """
    current = I18n.language_from_search(search) or I18n.current_language()
    if not language:
        language = current
    if language not in I18n.SUPPORTED_LANGUAGES:
        raise PreventUpdate
    I18n.set_language(language)
    labels = (I18n.translate('header.contact.title', language),
              I18n.translate('app.tab.simva', language),
              I18n.translate('app.tab.upload', language),
              I18n.translate('dashboard.no_tab_selected', language),
              I18n.translate('navigation.return', language))
    if current != language:
        return f'?lng={language}', language, *labels
    return no_update, language, *labels


# Named configuration storage for external clients. The Dash toolbar reaches the
# same per-user directory through TMonWidgets.PageConfig; these endpoints expose
# the list/save/load/delete operations over the existing authenticated server.
CONFIG_ROUTE = '/api/tmon/configs'


@flask.flaskServer.route(CONFIG_ROUTE, methods=['GET'])
def tmon_config_list():
    """Names saved for the current user."""
    return jsonify({'names': list_saved()})


@flask.flaskServer.route(CONFIG_ROUTE + '/<name>', methods=['GET'])
def tmon_config_get(name):
    """Read one saved configuration, validated before it is returned."""
    try:
        return jsonify(load_named(name))
    except ValueError as error:
        return jsonify({'error': str(error)}), 404


@flask.flaskServer.route(CONFIG_ROUTE + '/<name>', methods=['POST'])
def tmon_config_put(name):
    """Save a configuration document under ``name`` for the current user."""
    try:
        saved = save_named(name, request.get_json(silent=True) or {})
    except ValueError as error:
        return jsonify({'error': str(error)}), 400
    return jsonify({'name': saved})


@flask.flaskServer.route(CONFIG_ROUTE + '/<name>', methods=['DELETE'])
def tmon_config_delete(name):
    """Delete one saved configuration."""
    try:
        removed = delete_named(name)
    except ValueError as error:
        return jsonify({'error': str(error)}), 400
    return jsonify({'deleted': removed})



app.clientside_callback(
    "function(n){ if(n){ window.open(window.location.href, '_blank'); } return n || 0; }",
    Output('new-tab-opened', 'data'),
    Input('open-dashboard-new-tab', 'n_clicks'),
    prevent_initial_call=True,
)

if __name__ == '__main__':
    # Construct the URL
    print(f'The app is running at http://0.0.0.0:8050/')
    app.run(debug=True, host="0.0.0.0", port="8050")
