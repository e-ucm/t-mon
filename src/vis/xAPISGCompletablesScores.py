"""Grouped bar chart of final scores per player and completable."""
import pandas as pd
import plotly.express as px

from vis import xAPISGnoDataToFillVisualization
from vis.xAPISGVisualizationData import (
    completable_score_rows, ids_from_info, players_info, short_label,
)

from TMonWidgets.I18n import t


def build(df, game="", target="", mode=""):
    info = players_info(df)
    if not target:
        choices = ids_from_info(info, "completable")
        target = choices[0] if choices else ""
    rows = list(completable_score_rows(info, target))
    if not rows:
        return xAPISGnoDataToFillVisualization.noDataToFillVis(10)
    frame = pd.DataFrame(rows)
    figure = px.bar(
        frame, x="completable", y="score", color="player", barmode="group",
        labels={"completable": t("figure.axis.completable"),
                "score": t("figure.axis.score"),
                "player": t("figure.axis.player")},
    )
    title = t("figure.title.completable-scores")
    figure.update_layout(title=f"{title} — {short_label(target)}" if target else title)
    return figure
