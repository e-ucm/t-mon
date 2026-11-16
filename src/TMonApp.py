from dash import Dash, html, Input, Output, State
from TMonWidgets import UploadWidget, TMonWidget

# Initialize the app
TMonApp = Dash(__name__, serve_locally=True)
# App layout
TMonApp.layout = html.Div([
        TMonWidget.TMonHeader,
        html.Div([
            TMonWidget.TMonSidebar,
            TMonWidget.TMonBody,
        ], style={'display': 'flex'}),
        TMonWidget.TMonFooter
    ]
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