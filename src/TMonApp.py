import os
from dash import Dash, html, Input, Output, State, no_update
from dash.exceptions import PreventUpdate
from TMonWidgets import UploadWidget, TMonWidget, I18n

# Initialize the app. The explicit assets folder keeps the logo images resolvable
# no matter which directory the app is launched from.
TMonApp = Dash(
    __name__,
    serve_locally=True,
    assets_folder=os.path.join(os.path.dirname(__file__), 'assets'),
)
# App layout
TMonApp.layout = html.Div([
        TMonWidget.TMonHeader,
        html.H2('Select JSON xAPI-SG file to process and see visualizations', style={
            'margin': '20px 20px 0',
            'color': '#1e1e1e',
            'fontFamily': 'Inter',
        }),
        html.Div([
            TMonWidget.TMonSidebar,
            TMonWidget.TMonBody,
        ], style={'display': 'flex'}),
        TMonWidget.TMonFooter
    ],
    style={
        'minHeight': '100vh',
        'display': 'flex',
        'flexDirection': 'column',
    }
)

# Sidebar toggle callback
@TMonApp.callback(
    Output('sidebar', 'style'),
    Input('sidebar-toggle', 'n_clicks'),
    State('sidebar', 'style'),
)
def toggle_sidebar(n_clicks, style):
    if n_clicks > 0:
        # Toggle between hidden and visible
        if style.get('display') == 'none':
            return {'display': 'block'}
        else:
            return {'display': 'none'}
    return {'display': 'block'}  # Default: visible on mobile

@TMonApp.callback(
    [Output('return-button', 'style'), Output('return-button', 'href')],
    Input('url-t-mon', 'pathname')
)
def update_return_button(pathname):
    target = TMonWidget.return_target(pathname)
    if not target:
        return {'display': 'none'}, no_update
    return {'display': 'inline-block'}, target


@TMonApp.callback(
    [Output('i18n-location', 'href'),
     Output('header-language', 'value'),
     Output('header-contact-label', 'children'),
     Output('return-button', 'children')],
    Input('header-language', 'value'),
    State('url-t-mon', 'search')
)
def change_language(language, search):
    """Remember the chosen language; restore it on the next page load."""
    current = I18n.language_from_search(search) or I18n.current_language()
    if not language:
        language = current
    if language not in I18n.SUPPORTED_LANGUAGES:
        raise PreventUpdate
    I18n.set_language(language)
    label = I18n.translate('header.contact.title', language)
    return_label = I18n.translate('navigation.return', language)
    if current != language:
        return f'?lng={language}', language, label, return_label
    return no_update, language, label, return_label


if __name__ == '__main__':
    TMonApp.run(debug=True, port="5001")