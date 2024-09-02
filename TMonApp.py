from dash import Dash, html
from TMonWidgets import UploadWidget, TMonWidget

# Initialize the app
TMonApp = Dash(__name__)
# App layout
TMonApp.layout = html.Div([
        TMonWidget.TMonHeader,
        UploadWidget.TMonUpload,
        TMonWidget.TMonBody,
        TMonWidget.TMonFooter
    ]
)

if __name__ == '__main__':
    TMonApp.run(debug=True, port="5001")