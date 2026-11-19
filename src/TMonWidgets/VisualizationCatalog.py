"""
Catalogue of the named visualisations T-Mon can build.

The visualisations under ``vis/`` answer specific questions about xAPI-SG
statements. This module gives each of them an id, a translated label and a
builder, so the dashboard can offer them in the creation popup and draw them
from a chart description exactly as it draws a generic ``ChartBuilder`` chart.
The builders are DataFrame-driven and independent of call order.
"""
import pandas as pd

from vis import (
    xAPISGPlayersProgress,
    xAPISGVideosSeenSkipped,
    xAPISGnoDataToFillVisualization,
    xAPISGGamesStartedCompleted,
    xAPISGCompletablesProgress,
    xAPISGCompletablesScores,
    xAPISGCompletablesTimes,
    xAPISGCompletableProgressIncreaseDecrease,
    xAPISGCorrectIncorrectPerPlayer,
    xAPISGCorrectIncorrectPerQuestion,
    xAPISGAlternativesSelectedQuestion,
    xAPISGItemsInteracted,
    xAPISGItemsActionTypeInteracted,
    xAPISGAccessedAccessible,
    xAPISGMenusSelected,
)
from vis.xAPISGVisualizationData import short_label, target_ids

from TMonWidgets import I18n


def _placeholder():
    """The same empty figure the other visualisations use when data is absent."""
    return xAPISGnoDataToFillVisualization.noDataToFillVis(10)


def game_ids(df):
    """Serious-game object ids present in the statements, in first-seen order."""
    if df is None or df.empty:
        return []
    columns = df.columns
    if "object.id" not in columns or "object.definition.type" not in columns:
        return []
    # A normalized statement may carry the full xAPI-SG type or just its last
    # path segment; both name the same serious game.
    is_game = df["object.definition.type"].fillna("").map(
        lambda value: short_label(value).lower() == "serious-game")
    games = df.loc[is_game, "object.id"].dropna()
    return list(dict.fromkeys(str(game) for game in games))


def _prepare_progress(df):
    """Resolve the progress column from the data itself, for the legacy builders."""
    if df is None or df.empty:
        return None
    columns = [column for column in df.columns
               if "result" in column and "progress" in column]
    if not columns:
        return None
    xAPISGPlayersProgress.result_progress_column = columns[0]
    return columns[0]


def _progress_data(df, game):
    column = _prepare_progress(df)
    if column is None or not game:
        return None
    data = xAPISGPlayersProgress.ProgressPlayerLineChart(df, game)
    return data if isinstance(data, pd.DataFrame) and not data.empty else None


def _build_progress_line(df, game, target="", mode=""):
    data = _progress_data(df, game)
    if data is None:
        return _placeholder()
    return xAPISGPlayersProgress.displayPlayerProgressFig(data, game)


def _build_progress_origin(df, game, target="", mode=""):
    data = _progress_data(df, game)
    if data is None:
        return _placeholder()
    return xAPISGPlayersProgress.displayPlayerProgressInitFig(data, game)


def _build_progress_pie(df, game, target="", mode=""):
    """The GamesStartedCompleted notebook's figure, via its ported builder."""
    return xAPISGGamesStartedCompleted.build(df, game, target, mode)


def _build_video_seen_skipped(df, game="", target="", mode=""):
    if df is None or df.empty or "object.definition.type" not in df.columns:
        return _placeholder()
    return xAPISGVideosSeenSkipped.VideoSeenSkippedBarChart(df)


def _build_completable_progress(df, game, target, mode):
    return xAPISGCompletablesProgress.build(df, game, target, mode)


def _build_completable_scores(df, game, target, mode):
    return xAPISGCompletablesScores.build(df, game, target, mode)


def _build_completable_times(df, game, target, mode):
    return xAPISGCompletablesTimes.build(df, game, target, mode)


def _build_completable_progress_change(df, game, target, mode):
    return xAPISGCompletableProgressIncreaseDecrease.build(df, game, target, mode)


def _build_correct_incorrect_player(df, game, target, mode):
    return xAPISGCorrectIncorrectPerPlayer.build(df, game, target, mode)


def _build_correct_incorrect_question(df, game, target, mode):
    return xAPISGCorrectIncorrectPerQuestion.build(df, game, target, mode)


def _build_alternatives_selected(df, game, target, mode):
    return xAPISGAlternativesSelectedQuestion.build(df, game, target, mode)


def _build_item_interaction_time(df, game, target, mode):
    return xAPISGItemsInteracted.interaction_time(df, game, target, mode)


def _build_item_interaction_heatmap(df, game, target, mode):
    return xAPISGItemsInteracted.interaction_heatmap(df, game, target, mode)


def _build_item_interaction_count(df, game, target, mode):
    return xAPISGItemsInteracted.interaction_count(df, game, target, mode)


def _build_item_action_type_count(df, game, target, mode):
    return xAPISGItemsActionTypeInteracted.build(df, game, target, mode)


def _build_accessible_time(df, game, target, mode):
    return xAPISGAccessedAccessible.accessible_time(df, game, target, mode)


def _build_accessible_heatmap(df, game, target, mode):
    return xAPISGAccessedAccessible.accessible_heatmap(df, game, target, mode)


def _build_accessible_count(df, game, target, mode):
    return xAPISGAccessedAccessible.accessible_count(df, game, target, mode)


def _build_menu_selection_count(df, game, target, mode):
    return xAPISGMenusSelected.build(df, game, target, mode)


class VisualEntry:
    """One creatable visualisation."""

    def __init__(self, identifier, label_key, needs_game, builder,
                 target_kind=None, modes=()):
        self.identifier = identifier
        self.label_key = label_key
        self.needs_game = needs_game
        self.target_kind = target_kind
        self.modes = tuple(modes)
        self.builder = builder

    @property
    def label(self):
        return I18n.t(self.label_key)


VISUALS = {
    "progress-line": VisualEntry(
        "progress-line", "visual.progress-line", True, _build_progress_line,
        target_kind="game"),
    "progress-origin": VisualEntry(
        "progress-origin", "visual.progress-origin", True, _build_progress_origin,
        target_kind="game"),
    "progress-pie": VisualEntry(
        "progress-pie", "visual.progress-pie", True, _build_progress_pie,
        target_kind="game"),
    "video-seen-skipped": VisualEntry(
        "video-seen-skipped", "visual.video-seen-skipped", False,
        _build_video_seen_skipped),
    "completable-progress-change": VisualEntry(
        "completable-progress-change", "visual.completable-progress-change", False,
        _build_completable_progress_change, target_kind="completable-change",
        modes=("absolute", "relative")),
    "completable-progress": VisualEntry(
        "completable-progress", "visual.completable-progress", False,
        _build_completable_progress, target_kind="completable"),
    "completable-scores": VisualEntry(
        "completable-scores", "visual.completable-scores", False,
        _build_completable_scores, target_kind="completable"),
    "completable-times": VisualEntry(
        "completable-times", "visual.completable-times", False,
        _build_completable_times, target_kind="completable"),
    "correct-incorrect-by-player": VisualEntry(
        "correct-incorrect-by-player", "visual.correct-incorrect-by-player", False,
        _build_correct_incorrect_player, target_kind="alternative"),
    "correct-incorrect-by-question": VisualEntry(
        "correct-incorrect-by-question", "visual.correct-incorrect-by-question", False,
        _build_correct_incorrect_question, target_kind="alternative"),
    "alternatives-selected": VisualEntry(
        "alternatives-selected", "visual.alternatives-selected", False,
        _build_alternatives_selected, target_kind="alternative"),
    "item-interaction-time": VisualEntry(
        "item-interaction-time", "visual.item-interaction-time", False,
        _build_item_interaction_time, target_kind="item"),
    "item-interaction-heatmap": VisualEntry(
        "item-interaction-heatmap", "visual.item-interaction-heatmap", False,
        _build_item_interaction_heatmap, target_kind="item"),
    "item-interaction-count": VisualEntry(
        "item-interaction-count", "visual.item-interaction-count", False,
        _build_item_interaction_count, target_kind="item"),
    "item-action-type-count": VisualEntry(
        "item-action-type-count", "visual.item-action-type-count", False,
        _build_item_action_type_count, target_kind="action-type"),
    "accessible-time": VisualEntry(
        "accessible-time", "visual.accessible-time", False,
        _build_accessible_time, target_kind="accessible"),
    "accessible-heatmap": VisualEntry(
        "accessible-heatmap", "visual.accessible-heatmap", False,
        _build_accessible_heatmap, target_kind="accessible"),
    "accessible-count": VisualEntry(
        "accessible-count", "visual.accessible-count", False,
        _build_accessible_count, target_kind="accessible"),
    "menu-selection-count": VisualEntry(
        "menu-selection-count", "visual.menu-selection-count", False,
        _build_menu_selection_count, target_kind="menu"),
}

GROUPED_VISUALS = (
    ("visual.group.progress", ["progress-line", "progress-origin", "progress-pie"]),
    ("visual.group.videos", ["video-seen-skipped"]),
    ("visual.group.completables", [
        "completable-progress-change", "completable-progress",
        "completable-scores", "completable-times",
    ]),
    ("visual.group.alternatives", [
        "correct-incorrect-by-player", "correct-incorrect-by-question",
        "alternatives-selected",
    ]),
    ("visual.group.interactions", [
        "item-interaction-time", "item-interaction-heatmap",
        "item-interaction-count", "item-action-type-count",
    ]),
    ("visual.group.accessibles", [
        "accessible-time", "accessible-heatmap", "accessible-count",
    ]),
    ("visual.group.menus", ["menu-selection-count"]),
)


def _resolve_target(entry, df, target):
    """Choose a valid target, accepting the notebooks' last-segment ids."""
    available = target_ids(df, entry.target_kind)
    if not target:
        return available[0] if available else ""
    if target in available:
        return target
    for identifier in available:
        if short_label(identifier) == str(target):
            return identifier
    return available[0] if available else ""


def build_named_visual(df, spec):
    """Draw a named visualisation described by ``spec``, or a placeholder."""
    if not isinstance(spec, dict):
        return _placeholder()
    entry = VISUALS.get(spec.get("visual"))
    if entry is None:
        return _placeholder()

    game = spec.get("game") or ""
    if entry.needs_game:
        available = game_ids(df)
        if game not in available:
            game = available[0] if available else ""
        if not game:
            return _placeholder()
    else:
        game = ""

    target = spec.get("target") or ""
    if entry.target_kind:
        target = _resolve_target(entry, df, target)
        if not target:
            return _placeholder()

    mode = spec.get("mode") or ""
    if entry.modes:
        mode = mode if mode in entry.modes else entry.modes[0]

    try:
        figure = entry.builder(df, game, target, mode)
    except (KeyError, TypeError, ValueError):
        return _placeholder()
    return figure if figure is not None else _placeholder()


def describe_named(spec):
    """One-line title for a named visualisation."""
    entry = VISUALS.get(spec.get("visual")) if isinstance(spec, dict) else None
    if entry is None:
        return ""
    label = entry.label
    details = []
    if entry.needs_game and spec.get("game"):
        details.append(str(spec["game"]))
    if entry.target_kind and spec.get("target"):
        details.append(short_label(spec["target"]))
    return f"{label} — {' / '.join(details)}" if details else label
