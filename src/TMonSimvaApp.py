import os
from dash import Dash, dcc, html, Input, Output
from TMonWidgets.SimvaBrowserWidget import (
    flask, simvaBrowserBody, TMonUploadPanel, TMonContent,
)
from TMonWidgets import TMonWidget

# Initialize Dash app with Flask server. The explicit assets folder keeps the
# logo images resolvable no matter which directory the app is launched from.
app = Dash(
    __name__,
    server=flask.flaskServer,
    serve_locally=True,
    assets_folder=os.path.join(os.path.dirname(__file__), 'assets'),
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
                dcc.Tab(label='SIMVA', value='simva'),
                dcc.Tab(label='Upload file', value='upload'),
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


@app.callback(
    [Output('simva-panel', 'style'), Output('upload-panel', 'style')],
    Input('app-tabs', 'value'),
)
def switch_mode(tab):
    """Show only the panel belonging to the selected top tab."""
    if tab == 'upload':
        return {'display': 'none'}, {'display': 'block', 'padding': '20px'}
    return {'display': 'block'}, {'display': 'none'}


if __name__ == '__main__':
    # Construct the URL
    print(f'The app is running at http://0.0.0.0:8050/')
    app.run(debug=True, host="0.0.0.0", port="8050")
