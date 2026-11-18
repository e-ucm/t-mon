import os
from dash import Dash, dcc, html, Input, Output, State, no_update
from dash.exceptions import PreventUpdate
from TMonWidgets.SimvaBrowserWidget import (
    flask, simvaBrowserBody, TMonUploadPanel, TMonContent,
)
from TMonWidgets import TMonWidget, I18n

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
        TMonContent,
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
     Input('url', 'pathname')],
)
def switch_mode(tab, pathname):
    """Show only the panel belonging to the selected mode.

    Once a simlet is selected the mode tabs are in the way: the page is about
    that one simlet, so the SIMVA browser stays and both tabs disappear. Going
    back up to the studies list (``/``) brings them back.
    """
    # The Tabs component draws its tab bar as a flex row. Setting `display:
    # block` here would override that and stack "SIMVA" over "Upload file", so
    # the visible state has to keep it a flex row.
    visible_tabs = {'display': 'flex', 'flexDirection': 'row'}
    if simlet_selected(pathname):
        return {'display': 'none'}, {'display': 'block'}, {'display': 'none'}
    if tab == 'upload':
        return (visible_tabs, {'display': 'none'},
                {'display': 'block', 'padding': '20px'})
    return visible_tabs, {'display': 'block'}, {'display': 'none'}


@app.callback(
    [Output('i18n-location', 'href'),
     Output('header-language', 'value'),
     Output('header-contact-label', 'children'),
     Output('app-tab-simva', 'label'),
     Output('app-tab-upload', 'label')],
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
    labels = (I18n.translate('header.contact', language),
              I18n.translate('app.tab.simva', language),
              I18n.translate('app.tab.upload', language))
    if current != language:
        return f'?lng={language}', language, *labels
    return no_update, language, *labels


if __name__ == '__main__':
    # Construct the URL
    print(f'The app is running at http://0.0.0.0:8050/')
    app.run(debug=True, host="0.0.0.0", port="8050")
