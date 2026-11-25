"""The shared empty figure shown when there is nothing to plot.

This used to live in ``vis/xAPISGnoDataToFillVisualization.py``. The default
dashboard no longer has a ``vis`` package: its graphs are defined in
``config/default-dashboard.json`` and drawn by :mod:`GraphTypes`.
"""
import numpy as np
import plotly.graph_objs as go


def no_data_figure(max_value=10, show_y_label=False):
    """Return the standard 'no data' figure, scaled to ``max_value``."""
    figure = go.Figure()
    figure.add_annotation(
        x=0.5,
        y=max_value / 2,
        text="There is no data to fill the visualization.",
        showarrow=False,
        font=dict(size=10),
        xref='paper',
        yref='y',
    )
    figure.update_xaxes(showticklabels=False)
    if not show_y_label:
        figure.update_yaxes(showticklabels=False)
    figure.update_yaxes(
        range=[0, max_value],
        tickvals=list(np.arange(0, max_value, max_value / 10)),
    )
    return figure
