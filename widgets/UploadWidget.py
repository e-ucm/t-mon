from dash import html, dcc, callback, Output, Input, State
from fileBrowserAndUploadButtonToLoadProcessStatements import load_players_info_from_uploaded_content
import datetime
from dash.exceptions import PreventUpdate
import widgets

TMonUpload=html.Div([
    dcc.Upload(
        id='upload-data',
        children=html.Div([
            'Drag and Drop or ',
            html.A('Select Files')
        ]),
        style={
            'width': '100%',
            'height': '60px',
            'lineHeight': '60px',
            'borderWidth': '1px',
            'borderStyle': 'dashed',
            'borderRadius': '5px',
            'textAlign': 'center',
            'margin': '10px'
        },
        # Allow multiple files to be uploaded
        multiple=True
    ),
    html.Div(id='output-treatment'),
])

@callback(
    [Output('output-treatment', 'children'), 
     Output('output-t-mon', 'style'),
     Output('t-mon-tabs', 'value')],
    Input('upload-data', 'contents'),
    State('upload-data', 'filename'),
    State('upload-data', 'last_modified')
)
def update_output(list_of_contents, list_of_names, list_of_dates):
    if list_of_contents is None:
        raise PreventUpdate
    else:
        div_list = []
        widgets.xapiData = []
        nbError=0
        style={'display': 'block'}
        for c, n, d in zip(list_of_contents, list_of_names, list_of_dates):
            out, err = [], []
            div_list.append(html.H5(n))
            div_list.append(html.H6(datetime.datetime.fromtimestamp(d)))
            load_players_info_from_uploaded_content(c, n, widgets.xapiData, out, err)
            div_list.append(html.Div(out))
            div_list.append(html.Div(err))
            if len(err) > 0 : 
                nbError+=1
            div_list.append(html.Hr())
        if nbError == len(list_of_names):
            style={'display': 'none'}
        return div_list, style, "home"
