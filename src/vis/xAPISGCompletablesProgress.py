"""Bar chart of the final progress reached by each player in each completable."""
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
        choices = ids_from_info(info, "completable")
        target = choices[0] if choices else ""
    rows = list(completable_progress_rows(info, target))
    if not rows:
        return xAPISGnoDataToFillVisualization.noDataToFillVis(10)
    frame = pd.DataFrame(rows)
    # Keep the last sample per player/completable: the notebook's bar showed the
    # level each player ended on, not every intermediate progress event.
    frame = frame.sort_values("time").groupby(
        ["player", "completable"], as_index=False).tail(1)
    figure = px.bar(
        frame, x="completable", y="progress", color="player", barmode="group",
        labels={"player": t("figure.axis.player"),
                "completable": t("figure.axis.completable"),
                "progress": t("figure.axis.progress")},
    )
    title = t("figure.title.completable-progress")
    figure.update_layout(title=f"{title} — {short_label(target)}" if target else title)
    return figure
