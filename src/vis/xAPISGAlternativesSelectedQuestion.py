"""Frequency of each response selected for one alternative (question)."""
import pandas as pd
import plotly.express as px

from vis import xAPISGnoDataToFillVisualization
from vis.xAPISGVisualizationData import (
    alternative_answer_rows, ids_from_info, players_info, short_label,
)

from TMonWidgets.I18n import t


def build(df, game="", target="", mode=""):
    info = players_info(df)
    if not target:
        choices = ids_from_info(info, "alternative")
        target = choices[0] if choices else ""
    rows = list(alternative_answer_rows(info, target))
    if not rows:
        return xAPISGnoDataToFillVisualization.noDataToFillVis(10)
    frame = pd.DataFrame(rows)
    frame["result"] = frame["success"].map({
        True: t("figure.legend.correct"), False: t("figure.legend.incorrect"),
    })
    counts = frame.groupby(
        ["response", "result"], dropna=False).size().reset_index(name="count")
    figure = px.bar(
        counts, x="response", y="count", color="result", barmode="stack",
        labels={"response": t("figure.axis.response"),
                "count": t("figure.axis.count"),
                "result": t("figure.axis.result")},
    )
    title = t("figure.title.alternatives-selected")
    figure.update_layout(title=f"{title} — {short_label(target)}" if target else title)
    return figure
