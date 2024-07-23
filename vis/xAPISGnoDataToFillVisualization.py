# ***noDataToFillVis* function** display a text saying "There is no data to fill the visualization." when no data are given to a certain visualisation
# Input :
# * max : the max y value
# * showYLabel : False if the y value labels are not display, otherwise the y value labels are display

import plotly.graph_objs as go
import numpy as np
def noDataToFillVis(max_val, showYLabel=False):
    fig = go.Figure()

    fig.add_annotation(
        x=0.5,
        y=max_val / 2,
        text="There is no data to fill the visualization.",
        showarrow=False,
        font=dict(size=10),
        xref='paper',
        yref='y'
    )

    fig.update_xaxes(showticklabels=False)
    
    if not showYLabel:
        fig.update_yaxes(showticklabels=False)
        
    fig.update_yaxes(range=[0, max_val])
    fig.update_yaxes(tickvals=list(np.arange(0, max_val, max_val / 10)))

    return fig