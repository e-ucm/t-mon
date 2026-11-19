"""Counts of the options selected in one menu, grouped by player."""
import pandas as pd
import plotly.express as px

from vis import xAPISGnoDataToFillVisualization
from vis.xAPISGVisualizationData import ids_from_info, menu_rows, players_info


def build(df, game="", target="", mode=""):
    info = players_info(df)
    if not target:
        choices = ids_from_info(info, "menu")
        target = choices[0] if choices else ""
    rows = list(menu_rows(info, target))
    if not rows:
        return xAPISGnoDataToFillVisualization.noDataToFillVis(10)
    frame = pd.DataFrame(rows)
    counts = frame.groupby(
        ["selection", "player"], dropna=False).size().reset_index(name="count")
    return px.bar(counts, x="selection", y="count", color="player", barmode="group")
