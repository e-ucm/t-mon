import os
from dash import Dash, html, Input, Output, State
from TMonWidgets import UploadWidget, TMonWidget

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

if __name__ == '__main__':
    TMonApp.run(debug=True, port="5001")