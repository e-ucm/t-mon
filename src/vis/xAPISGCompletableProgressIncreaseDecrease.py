"""Line chart of completable progress over time, including increases/decreases."""
import pandas as pd
import plotly.express as px

from vis import xAPISGnoDataToFillVisualization
from vis.xAPISGVisualizationData import (
    completable_progress_rows, ids_from_info, players_info, short_label,
)

from TMonWidgets.I18n import t


def build(df, game="", target="", mode=""):
    info = players_info(df)
    if not target:
        choices = ids_from_info(info, "completable-change")
        target = choices[0] if choices else ""
    rows = list(completable_progress_rows(info, target, only_changes=True))
    if not rows:
        return xAPISGnoDataToFillVisualization.noDataToFillVis(10)
    frame = pd.DataFrame(rows).sort_values("time")

    if mode == "relative":
        frame["time"] = (frame["time"]
                         - frame.groupby(["player", "completable"])["time"].transform("min"))
        frame["time"] = frame["time"].dt.total_seconds() / 60.0
        time_label = t("figure.axis.elapsed")
    else:
        time_label = t("figure.axis.time")

    labels = {"player": t("figure.axis.player"),
              "completable": t("figure.axis.completable"),
              "progress": t("figure.axis.progress"),
              "time": time_label}
    if frame["completable"].nunique() > 1:
        figure = px.line(
            frame, x="time", y="progress", color="player",
            facet_col="completable", markers=True, labels=labels,
        )
    else:
        figure = px.line(
            frame, x="time", y="progress", color="player",
            markers=True, labels=labels,
        )
    title = t("figure.title.completable-progress-change")
    figure.update_layout(title=f"{title} — {short_label(target)}" if target else title)
    return figure
