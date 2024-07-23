from dash import Dash, html
from widgets import SIMVAWidget, TMonWidget

# Initialize Dash app with Flask server
global app
app = Dash(__name__, server=SIMVAWidget.flask.flaskServer)
global xapiData
xapiData = []

# If you set host or port differently
global port, host, debug, httpSecure
httpSecure= "https://" if app.server.config.get('SECURE', False) else "http://"
debug=app.server.config.get('DEBUG', False),
host = app.server.config.get('HOST', '127.0.0.1')
port = app.server.config.get('PORT', 5000)

# Layout of the dashboard
app.layout=html.Div(
    [
        TMonWidget.TMonHeader,
        SIMVAWidget.simvaBrowserBody,
        TMonWidget.TMonBody,
        TMonWidget.TMonFooter,
    ]
)

if __name__ == '__main__':
    app.run(debug=debug, port=port)
    # Construct the URL
    url = f'{httpSecure}{host}:{port}'
    print(f'The app is running at {url}')