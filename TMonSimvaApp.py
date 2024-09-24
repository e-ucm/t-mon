from dash import Dash, html
from TMonWidgets import SimvaBrowserWidget, TMonWidget

# Initialize Dash app with Flask server
app = Dash(__name__, server=SimvaBrowserWidget.flask.flaskServer)

# If you set host or port differently
print(app.server.config)
httpSecure= "https" if app.server.config.get('SECURE', False) == "True" else "http"
debug=app.server.config.get('DEBUG', "False")
host = app.server.config.get('HOST', '0.0.0.0')
port = app.server.config.get('PORT', 8050)

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
    url = f'{httpSecure}://{host}:{port}'
    print(f'The app is running at {url} (http://0.0.0.0:8050/) - {debug}')
    app.run(debug=True, host="0.0.0.0", port="8050")