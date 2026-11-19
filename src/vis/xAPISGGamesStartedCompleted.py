"""Started/completed games pie, built from the shared progress implementation."""
from vis import xAPISGPlayersProgress
from vis import xAPISGnoDataToFillVisualization
from vis.xAPISGVisualizationData import short_label

from TMonWidgets.I18n import t


def _is_serious_game(value):
    """Accept both the full xAPI-SG type and its last path segment."""
    return str(value).rstrip("/").split("/")[-1].lower() == "serious-game"


def _game_ids(df):
    if df is None or getattr(df, "empty", True):
        return []
    needed = {"object.id", "object.definition.type"}
    if not needed.issubset(df.columns):
        return []
    types = df["object.definition.type"].fillna("").map(_is_serious_game)
    games = df.loc[types, "object.id"].dropna()
    return list(dict.fromkeys(str(game) for game in games))


def build(df, game="", target="", mode=""):
    """Draw the existing started/completed pie for one serious game."""
    if not game:
        games = _game_ids(df)
        game = games[0] if games else ""
    if not game:
        return xAPISGnoDataToFillVisualization.noDataToFillVis(10)
    data = xAPISGPlayersProgress.ProgressPlayerPie(df, game)
    if data is None or getattr(data, "empty", True):
        return xAPISGnoDataToFillVisualization.noDataToFillVis(10)
    figure = xAPISGPlayersProgress.displayPlayerProgressPieFig(data, game)
    title = t("figure.title.games-started-completed")
    suffix = short_label(target) if target else short_label(game)
    figure.update_layout(title=f"{title} — {suffix}" if suffix else title)
    return figure
