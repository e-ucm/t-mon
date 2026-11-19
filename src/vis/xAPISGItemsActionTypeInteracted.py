"""Counts of item interactions grouped by the recorded action type."""
import pandas as pd
import plotly.express as px

from vis import xAPISGnoDataToFillVisualization
from vis.xAPISGVisualizationData import (
    action_type_rows, players_info, short_label,
)

from TMonWidgets.I18n import t


def build(df, game="", target="", mode=""):
    rows = list(action_type_rows(players_info(df), target))
    if not rows:
        return xAPISGnoDataToFillVisualization.noDataToFillVis(10)
    frame = pd.DataFrame(rows)
    counts = frame.groupby(["action_type", "player"]).size().reset_index(name="count")
    figure = px.bar(
        counts, x="action_type", y="count", color="player", barmode="group",
        labels={"action_type": t("figure.axis.action-type"),
                "count": t("figure.axis.count"),
                "player": t("figure.axis.player")},
    )
    title = t("figure.title.item-action-type-count")
    figure.update_layout(title=f"{title} — {short_label(target)}" if target else title)
    return figure
