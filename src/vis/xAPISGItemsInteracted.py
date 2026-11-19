"""Three views of item interaction: time, player/item heatmap and counts."""
import pandas as pd
import plotly.express as px

from vis import xAPISGnoDataToFillVisualization
from vis.xAPISGVisualizationData import interaction_rows, players_info, short_label

from TMonWidgets.I18n import t


def _rows(df, target):
    rows = list(interaction_rows(players_info(df), target))
    return pd.DataFrame(rows) if rows else None


def _title(key, target):
    title = t(key)
    return f"{title} — {short_label(target)}" if target else title


def interaction_time(df, game="", target="", mode=""):
    frame = _rows(df, target)
    if frame is None:
        return xAPISGnoDataToFillVisualization.noDataToFillVis(10)
    figure = px.scatter(
        frame, x="time", y="item", color="player", hover_data=["object_type"],
        labels={"time": t("figure.axis.time"), "item": t("figure.axis.item"),
                "player": t("figure.axis.player")},
    )
    figure.update_layout(title=_title("figure.title.item-interaction-time", target))
    return figure


def interaction_heatmap(df, game="", target="", mode=""):
    frame = _rows(df, target)
    if frame is None:
        return xAPISGnoDataToFillVisualization.noDataToFillVis(10)
    matrix = frame.pivot_table(
        index="player", columns="item", values="time",
        aggfunc="count", fill_value=0)
    figure = px.imshow(
        matrix, aspect="auto",
        labels=dict(x=t("figure.axis.item"), y=t("figure.axis.player"),
                    color=t("figure.axis.count")),
    )
    figure.update_layout(title=_title("figure.title.item-interaction-heatmap", target))
    return figure


def interaction_count(df, game="", target="", mode=""):
    frame = _rows(df, target)
    if frame is None:
        return xAPISGnoDataToFillVisualization.noDataToFillVis(10)
    counts = frame.groupby(["item", "player"]).size().reset_index(name="count")
    figure = px.bar(
        counts, x="item", y="count", color="player", barmode="group",
        labels={"item": t("figure.axis.item"), "count": t("figure.axis.count"),
                "player": t("figure.axis.player")},
    )
    figure.update_layout(title=_title("figure.title.item-interaction-count", target))
    return figure
