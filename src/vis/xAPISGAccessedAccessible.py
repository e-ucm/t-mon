"""Three views of accessible-zone access: time, heatmap and counts."""
import pandas as pd
import plotly.express as px

from vis import xAPISGnoDataToFillVisualization
from vis.xAPISGVisualizationData import accessible_rows, players_info, short_label

from TMonWidgets.I18n import t


def _rows(df, target):
    rows = list(accessible_rows(players_info(df), target))
    return pd.DataFrame(rows) if rows else None


def _title(key, target):
    title = t(key)
    return f"{title} — {short_label(target)}" if target else title


def accessible_time(df, game="", target="", mode=""):
    frame = _rows(df, target)
    if frame is None:
        return xAPISGnoDataToFillVisualization.noDataToFillVis(10)
    figure = px.scatter(
        frame, x="time", y="accessible", color="player",
        labels={"time": t("figure.axis.time"),
                "accessible": t("figure.axis.accessible"),
                "player": t("figure.axis.player")},
    )
    figure.update_layout(title=_title("figure.title.accessible-time", target))
    return figure


def accessible_heatmap(df, game="", target="", mode=""):
    frame = _rows(df, target)
    if frame is None:
        return xAPISGnoDataToFillVisualization.noDataToFillVis(10)
    matrix = frame.pivot_table(
        index="player", columns="accessible", values="time",
        aggfunc="count", fill_value=0)
    figure = px.imshow(
        matrix, aspect="auto",
        labels=dict(x=t("figure.axis.accessible"), y=t("figure.axis.player"),
                    color=t("figure.axis.count")),
    )
    figure.update_layout(title=_title("figure.title.accessible-heatmap", target))
    return figure


def accessible_count(df, game="", target="", mode=""):
    frame = _rows(df, target)
    if frame is None:
        return xAPISGnoDataToFillVisualization.noDataToFillVis(10)
    counts = frame.groupby(["accessible", "player"]).size().reset_index(name="count")
    figure = px.bar(
        counts, x="accessible", y="count", color="player", barmode="group",
        labels={"accessible": t("figure.axis.accessible"),
                "count": t("figure.axis.count"),
                "player": t("figure.axis.player")},
    )
    figure.update_layout(title=_title("figure.title.accessible-count", target))
    return figure
