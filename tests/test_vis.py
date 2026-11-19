import pandas as pd
import plotly.graph_objects as go
import pytest

from vis import (
    xAPISGPlayersProgress,
    xAPISGVideosSeenSkipped,
    xAPISGnoDataToFillVisualization,
    xAPISGVisualizationData,
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

SERIOUS = "https://w3id.org/xapi/seriousgames/activity-types/serious-game"
GAME = "https://example.com/xapi/activity/game-1"
LEVEL = "https://example.com/xapi/activity/level-1"
QUESTION = "https://example.com/xapi/activity/question-1"
ITEM = "https://example.com/xapi/activity/item-1"
ACCESSIBLE = "https://example.com/xapi/activity/accessible-1"
MENU = "https://example.com/xapi/activity/menu-1"
CUTSCENE = "https://example.com/xapi/activity/cutscene-1"


def cutscene_df():
    return pd.DataFrame(
        {
            "verb.id": [
                "http://adlnet.gov/expapi/verbs/accessed",
                "http://adlnet.gov/expapi/verbs/skipped",
            ],
            "object.id": [CUTSCENE, CUTSCENE],
            "actor.name": ["player-1", "player-1"],
            "object.definition.type": [
                "https://xapi.org/activity-types/cutscene",
                "https://xapi.org/activity-types/cutscene",
            ],
        }
    )


def notebook_df():
    """Statements covering every target kind the notebook builders use."""
    rows = []

    def add(actor, verb, object_id, object_type, timestamp, **result):
        row = {
            "actor.name": actor,
            "verb.id": f"http://adlnet.gov/expapi/verbs/{verb}",
            "object.id": object_id,
            "object.definition.type": f"https://example.com/xapi/types/{object_type}",
            "timestamp": timestamp,
        }
        row.update(result)
        rows.append(row)

    # The game and the completable share a timestamp range, as a real session does.
    add("p1", "initialized", GAME, "serious-game", "2026-01-01T00:00:00Z")
    add("p1", "progressed", GAME, "serious-game", "2026-01-01T00:05:00Z",
        **{"result.progress": 0.5})
    add("p1", "completed", GAME, "serious-game", "2026-01-01T00:10:00Z",
        **{"result.progress": 1, "result.score.raw": 8})
    add("p2", "initialized", GAME, "serious-game", "2026-01-01T00:01:00Z")
    add("p2", "completed", GAME, "serious-game", "2026-01-01T00:11:00Z",
        **{"result.progress": 1, "result.score.raw": 9})
    add("p1", "progressed", LEVEL, "level", "2026-01-01T00:02:00Z",
        **{"result.progress": -1})
    add("p1", "progressed", LEVEL, "level", "2026-01-01T00:03:00Z",
        **{"result.progress": 0.4})
    add("p2", "initialized", LEVEL, "level", "2026-01-01T00:02:30Z")
    add("p2", "completed", LEVEL, "level", "2026-01-01T00:04:00Z",
        **{"result.score.raw": 6})
    add("p1", "completed", LEVEL, "level", "2026-01-01T00:06:00Z",
        **{"result.score.raw": 7})

    for actor, response, success, timestamp in (
        ("p1", "a", True, "2026-01-01T00:12:00Z"),
        ("p1", "b", False, "2026-01-01T00:13:00Z"),
        ("p2", "a", True, "2026-01-01T00:14:00Z"),
    ):
        add(actor, "selected", QUESTION, "alternative", timestamp,
            **{"result.response": response, "result.success": success})

    for actor, timestamp in (
        ("p1", "2026-01-01T00:15:00Z"),
        ("p1", "2026-01-01T00:16:00Z"),
        ("p2", "2026-01-01T00:17:00Z"),
    ):
        add(actor, "interacted", ITEM, "item", timestamp)
    add("p1", "interacted", ITEM, "item", "2026-01-01T00:18:00Z",
        **{"result.action_type": "grab"})

    add("p1", "accessed", ACCESSIBLE, "accessible", "2026-01-01T00:19:00Z")
    add("p2", "accessed", ACCESSIBLE, "accessible", "2026-01-01T00:20:00Z")
    add("p1", "selected", MENU, "menu", "2026-01-01T00:21:00Z",
        **{"result.response": "start"})
    add("p2", "selected", MENU, "menu", "2026-01-01T00:22:00Z",
        **{"result.response": "quit"})
    add("p1", "accessed", CUTSCENE, "cutscene", "2026-01-01T00:23:00Z")
    return pd.DataFrame(rows)


def test_no_data_to_fill_visualization_returns_figure():
    fig = xAPISGnoDataToFillVisualization.noDataToFillVis(10)
    assert isinstance(fig, go.Figure)


def test_video_seen_skipped_bar_chart_with_data():
    fig = xAPISGVideosSeenSkipped.VideoSeenSkippedBarChart(cutscene_df())
    assert isinstance(fig, go.Figure)


def test_video_seen_skipped_bar_chart_empty():
    df = pd.DataFrame(columns=["object.definition.type", "verb.id", "object.id", "actor.name"])
    fig = xAPISGVideosSeenSkipped.VideoSeenSkippedBarChart(df)
    assert isinstance(fig, go.Figure)


def test_update_progress():
    xAPISGPlayersProgress.result_progress_column = "result.progress"
    assert (
        xAPISGPlayersProgress.update_progress(
            {"verb.id": "http://adlnet.gov/expapi/verbs/initialized"}
        )
        == 0
    )
    assert (
        xAPISGPlayersProgress.update_progress(
            {"verb.id": "http://adlnet.gov/expapi/verbs/completed"}
        )
        == 1
    )
    assert (
        xAPISGPlayersProgress.update_progress(
            {"verb.id": "http://adlnet.gov/expapi/verbs/progressed", "result.progress": 0.5}
        )
        == 0.5
    )


# --- DataFrame-driven notebook adapters ------------------------------------


def test_adapter_derives_every_target_kind():
    df = notebook_df()
    info = xAPISGVisualizationData.players_info(df)
    assert set(info) == {"p1", "p2"}
    assert info["p1"]["game_started"] and info["p1"]["game_completed"]
    assert set(xAPISGVisualizationData.target_ids(df, "game")) == {GAME}
    for kind, expected in (
        ("completable", LEVEL),
        ("completable-change", LEVEL),
        ("alternative", QUESTION),
        ("item", ITEM),
        ("action-type", "grab"),
        ("accessible", ACCESSIBLE),
        ("menu", MENU),
    ):
        assert expected in xAPISGVisualizationData.target_ids(df, kind)


def test_adapter_is_order_independent():
    df = notebook_df()
    kinds = ("game", "completable", "completable-change", "alternative",
             "item", "action-type", "accessible", "menu")
    expected = {kind: xAPISGVisualizationData.target_ids(df, kind) for kind in kinds}
    reversed_df = df.iloc[::-1].reset_index(drop=True)
    for kind in kinds:
        assert xAPISGVisualizationData.target_ids(reversed_df, kind) == expected[kind]


def test_adapter_accepts_xapi_extension_fields_and_short_ids():
    df = pd.DataFrame([
        {
            "actor.name": "p1",
            "verb.id": "http://adlnet.gov/expapi/verbs/completed",
            "object.id": LEVEL,
            "object.definition.type": "https://example.com/xapi/types/level",
            "result.extensions.score": 7,
            "result.extensions.progress": 1,
        },
    ])
    info = xAPISGVisualizationData.players_info(df)
    assert info["p1"]["completables_scores"][LEVEL] == 7
    assert xAPISGVisualizationData.canonical_target(info, "completable", "level-1") == LEVEL
    assert xAPISGVisualizationData.short_label(LEVEL) == "level-1"


NEW_BUILDERS = [
    (xAPISGCompletablesProgress.build, LEVEL, ""),
    (xAPISGCompletablesScores.build, LEVEL, ""),
    (xAPISGCompletablesTimes.build, LEVEL, ""),
    (xAPISGCompletableProgressIncreaseDecrease.build, LEVEL, "absolute"),
    (xAPISGCompletableProgressIncreaseDecrease.build, LEVEL, "relative"),
    (xAPISGCorrectIncorrectPerPlayer.build, QUESTION, ""),
    (xAPISGCorrectIncorrectPerQuestion.build, QUESTION, ""),
    (xAPISGAlternativesSelectedQuestion.build, QUESTION, ""),
    (xAPISGItemsInteracted.interaction_time, ITEM, ""),
    (xAPISGItemsInteracted.interaction_heatmap, ITEM, ""),
    (xAPISGItemsInteracted.interaction_count, ITEM, ""),
    (xAPISGItemsActionTypeInteracted.build, "grab", ""),
    (xAPISGAccessedAccessible.accessible_time, ACCESSIBLE, ""),
    (xAPISGAccessedAccessible.accessible_heatmap, ACCESSIBLE, ""),
    (xAPISGAccessedAccessible.accessible_count, ACCESSIBLE, ""),
    (xAPISGMenusSelected.build, MENU, ""),
]


@pytest.mark.parametrize("builder,target,mode", NEW_BUILDERS)
def test_notebook_builder_returns_a_plotly_figure(builder, target, mode):
    figure = builder(notebook_df(), "", target, mode)
    assert isinstance(figure, go.Figure)
    assert figure.data
    assert figure.layout.title.text


@pytest.mark.parametrize("builder,_target,_mode", NEW_BUILDERS)
def test_notebook_builder_shows_placeholder_for_an_empty_target(builder, _target, _mode):
    figure = builder(notebook_df(), "", "https://example.com/xapi/activity/missing", "")
    assert isinstance(figure, go.Figure)
    assert not figure.data


def test_games_started_completed_uses_the_existing_progress_data():
    df = notebook_df()
    figure = xAPISGGamesStartedCompleted.build(df, GAME)
    assert isinstance(figure, go.Figure)
    assert figure.data
    assert "Games started and completed" in figure.layout.title.text
