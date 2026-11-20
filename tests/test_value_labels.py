"""URL values are shown by their last segment on a chart axis."""
import pandas as pd
import plotly.graph_objects as go

from TMonWidgets.ChartBuilder import COUNT_LABEL, build_chart
from TMonWidgets.GraphTypes import render_graph
from TMonWidgets.ValueLabels import shorten_url_value


def test_shortens_a_url_to_its_last_segment():
    assert shorten_url_value("https://yyyuyugjh.com/xxx") == "xxx"
    assert shorten_url_value("https://yyyuyugjh.com/xxx/") == "xxx"
    assert shorten_url_value("https://yyyuyugjh.com/a/b/xxx") == "xxx"
    assert shorten_url_value("http://yyyuyugjh.com/xxx?team=1#top") == "xxx"
    assert shorten_url_value("https://yyyuyugjh.com") == "yyyuyugjh.com"


def test_leaves_other_values_untouched():
    assert shorten_url_value("plain text") == "plain text"
    assert shorten_url_value("a/b/xxx") == "a/b/xxx"
    assert shorten_url_value("urn:uuid:123") == "urn:uuid:123"
    assert shorten_url_value(7) == 7
    assert shorten_url_value(None) is None
    assert shorten_url_value("https://yyyuyugjh.com/a%20b") == "a b"


def test_custom_chart_groups_by_the_readable_part_of_a_url():
    df = pd.DataFrame({
        "object.id": [
            "https://yyyuyugjh.com/intro",
            "https://yyyuyugjh.com/intro",
            "https://yyyuyugjh.com/quiz",
        ],
    })
    figure = build_chart(df, {
        "type": "bar", "x": "object.id", "y": COUNT_LABEL,
        "aggregation": "count",
    })
    assert isinstance(figure, go.Figure)
    assert list(figure.data[0].x) == ["intro", "quiz"]
    assert list(figure.data[0].y) == [2, 1]


def test_custom_chart_shortens_both_axes_when_they_hold_urls():
    df = pd.DataFrame({
        "actor.id": ["https://host/players/a", "https://host/players/b"],
        "object.id": ["https://host/activities/one", "https://host/activities/two"],
        "score": [1.0, 2.0],
    })
    figure = build_chart(df, {
        "type": "scatter", "x": "actor.id", "y": "object.id",
        "aggregation": "sum",
    })
    assert list(figure.data[0].x) == ["a", "b"]


def test_default_dashboard_graph_shortens_urls_too():
    df = pd.DataFrame({
        "object.id": ["https://host/intro", "https://host/intro", "https://host/quiz"],
    })
    graph = {
        "type": "bar", "id": "activities",
        "x": {"data": "object.id", "label": "Activity"},
        "y": {"data": "count"},
        "aggregation": "count",
    }
    figure = render_graph(df, graph)
    assert list(figure.data[0].x) == ["intro", "quiz"]
    assert list(figure.data[0].y) == [2, 1]


def test_default_dashboard_heatmap_shortens_both_axes():
    df = pd.DataFrame({
        "actor.id": ["https://host/a", "https://host/a", "https://host/b"],
        "object.id": ["https://host/one", "https://host/two", "https://host/two"],
    })
    graph = {
        "type": "heatmap", "id": "matrix",
        "x": {"data": "actor.id"}, "y": {"data": "object.id"},
    }
    figure = render_graph(df, graph)
    assert list(figure.data[0].x) == ["a", "b"]
    assert list(figure.data[0].y) == ["one", "two"]
