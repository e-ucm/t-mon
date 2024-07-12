from dash import Dash, html
from TMonWidgets import SimvaBrowserWidget, TMonWidget

# Initialize Dash app with Flask server
app = Dash(__name__, server=SimvaBrowserWidget.flask.flaskServer)

# Layout of the dashboard
app.layout=html.Div(
    [
        SimvaBrowserWidget.LoginLogoutBody,
        TMonWidget.TMonHeader,
        SimvaBrowserWidget.simvaBrowserBody,
        TMonWidget.TMonBody,
        TMonWidget.TMonFooter,
    ]
)

if __name__ == '__main__':
    # Construct the URL
    print(f'The app is running at http://0.0.0.0:8050/')
    app.run(debug=True, host="0.0.0.0", port="8050")