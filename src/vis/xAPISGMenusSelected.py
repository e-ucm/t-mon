"""Counts of the options selected in one menu, grouped by player."""
import pandas as pd
import plotly.express as px

from vis import xAPISGnoDataToFillVisualization
from vis.xAPISGVisualizationData import (
    ids_from_info, menu_rows, players_info, short_label,
)

from TMonWidgets.I18n import t


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
    figure = px.bar(
        counts, x="selection", y="count", color="player", barmode="group",
        labels={"selection": t("figure.axis.response"),
                "count": t("figure.axis.count"),
                "player": t("figure.axis.player")},
    )
    title = t("figure.title.menu-selection-count")
    figure.update_layout(title=f"{title} — {short_label(target)}" if target else title)
    return figure
