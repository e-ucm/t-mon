import pandas as pd
import plotly.graph_objects as go
import pytest

from vis import xAPISGPlayersProgress, xAPISGVideosSeenSkipped, xAPISGnoDataToFillVisualization


def cutscene_df():
    return pd.DataFrame(
        {
            "verb.id": [
                "http://adlnet.gov/expapi/verbs/accessed",
                "http://adlnet.gov/expapi/verbs/skipped",
            ],
            "object.id": ["cutscene-1", "cutscene-1"],
            "actor.name": ["player-1", "player-1"],
            "object.definition.type": ["https://xapi/cutscene", "https://xapi/cutscene"],
        }
    )


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