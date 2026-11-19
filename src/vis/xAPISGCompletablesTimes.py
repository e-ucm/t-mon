"""Completion time per completable: per player for one target, min/max for all."""
import pandas as pd
import plotly.express as px

from vis import xAPISGnoDataToFillVisualization
from vis.xAPISGVisualizationData import (
    completable_time_rows, ids_from_info, players_info, short_label,
)

from TMonWidgets.I18n import t


def build(df, game="", target="", mode=""):
    info = players_info(df)
    if not target:
        choices = ids_from_info(info, "completable")
        target = choices[0] if choices else ""
    rows = list(completable_time_rows(info, target))
    if not rows:
        return xAPISGnoDataToFillVisualization.noDataToFillVis(10)
    frame = pd.DataFrame(rows)

    if target:
        figure = px.bar(
            frame, x="player", y="minutes", color="completable", barmode="group",
            labels={"player": t("figure.axis.player"),
                    "minutes": t("figure.axis.duration"),
                    "completable": t("figure.axis.completable")},
        )
    else:
        summary = frame.groupby("completable", as_index=False).agg(
            minimum=("minutes", "min"), maximum=("minutes", "max"))
        figure = px.bar(
            summary, x="completable", y=["maximum", "minimum"], barmode="group",
            labels={"completable": t("figure.axis.completable"),
                    "value": t("figure.axis.duration"),
                    "variable": t("figure.axis.duration"),
                    "maximum": t("figure.axis.maximum"),
                    "minimum": t("figure.axis.minimum")},
        )
    title = t("figure.title.completable-times")
    figure.update_layout(title=f"{title} — {short_label(target)}" if target else title)
    return figure
