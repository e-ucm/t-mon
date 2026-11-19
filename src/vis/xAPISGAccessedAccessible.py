"""Three views of accessible-zone access: time, heatmap and counts."""
import pandas as pd
import plotly.express as px

from vis import xAPISGnoDataToFillVisualization
from vis.xAPISGVisualizationData import accessible_rows, players_info


def _rows(df, target):
    rows = list(accessible_rows(players_info(df), target))
    return pd.DataFrame(rows) if rows else None


def accessible_time(df, game="", target="", mode=""):
    frame = _rows(df, target)
    if frame is None:
        return xAPISGnoDataToFillVisualization.noDataToFillVis(10)
    return px.scatter(frame, x="time", y="accessible", color="player")


def accessible_heatmap(df, game="", target="", mode=""):
    frame = _rows(df, target)
    if frame is None:
        return xAPISGnoDataToFillVisualization.noDataToFillVis(10)
    matrix = frame.pivot_table(
        index="player", columns="accessible", values="time",
        aggfunc="count", fill_value=0)
    return px.imshow(matrix, aspect="auto")


def accessible_count(df, game="", target="", mode=""):
    frame = _rows(df, target)
    if frame is None:
        return xAPISGnoDataToFillVisualization.noDataToFillVis(10)
    counts = frame.groupby(["accessible", "player"]).size().reset_index(name="count")
    return px.bar(counts, x="accessible", y="count", color="player", barmode="group")
