import os
from dash import Dash, html
from TMonWidgets.SimvaBrowserWidget import flask, simvaBrowserBody
from TMonWidgets import TMonWidget

# Initialize Dash app with Flask server. The explicit assets folder keeps the
# logo images resolvable no matter which directory the app is launched from.
app = Dash(
    __name__,
    server=flask.flaskServer,
    serve_locally=True,
    assets_folder=os.path.join(os.path.dirname(__file__), 'assets'),
)

# Layout of the dashboard
app.layout=html.Div(
    [
        TMonWidget.TMonSimvaHeader,
        simvaBrowserBody,
        TMonWidget.TMonBody,
        TMonWidget.TMonFooter,
    ],
    style={
        'minHeight': '100vh',
        'display': 'flex',
        'flexDirection': 'column',
    },
)

if __name__ == '__main__':
    # Construct the URL
    print(f'The app is running at http://0.0.0.0:8050/')
    app.run(debug=True, host="0.0.0.0", port="8050")