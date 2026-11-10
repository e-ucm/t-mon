import pandas as pd

import TMonWidgets
from TMonWidgets import MultiSelector, TMonWidget


def test_get_value_from_url():
    url = "tab=dashboard&actor.name=John+Doe&object.id=https://simva.example/1"
    assert TMonWidget.get_value_from_url(url, "tab=") == "dashboard"
    assert TMonWidget.get_value_from_url(url, "actor.name=") == "John Doe"
    assert TMonWidget.get_value_from_url(url, "object.id=") == "https://simva.example/1"
    assert TMonWidget.get_value_from_url(url, "missing=") is None


def test_activity_name_of():
    previous = getattr(TMonWidgets, "sessionActivities", [])
    TMonWidgets.sessionActivities = [{"name": "Observation", "id": "123"}]
    try:
        assert TMonWidget.activity_name_of("123") == "Observation"
        assert TMonWidget.activity_name_of("other") == "other"
        TMonWidgets.sessionActivities = []
        assert TMonWidget.activity_name_of("123") == "123"
    finally:
        TMonWidgets.sessionActivities = previous


def test_hidden_activities_from_url():
    assert TMonWidget.hidden_activities_from_url("/dashboard/?hidden-activity=2,3") == ["2", "3"]
    assert TMonWidget.hidden_activities_from_url("/dashboard/?hidden-activity=2&x=1") == ["2"]
    assert TMonWidget.hidden_activities_from_url("/dashboard/") == []
    assert TMonWidget.hidden_activities_from_url(None) == []


def test_search_value_from_multi_selector_filters_options():
    df = pd.DataFrame({"object": ["Activity One", "activity two", "Other"]})
    filtered, options = MultiSelector.searchValueFromMultiSelector(df, "object", "activity", None)
    assert len(filtered) == 3
    assert [o["label"] for o in options] == ["Activity One", "activity two"]


def test_search_value_from_multi_selector_keeps_selected():
    df = pd.DataFrame({"object": ["Alpha", "Beta"]})
    filtered, options = MultiSelector.searchValueFromMultiSelector(df, "object", None, ["Beta"])
    assert filtered["object"].tolist() == ["Beta"]
    assert [o["value"] for o in options] == ["Beta", "Alpha"]


def test_search_value_from_multi_selector_no_search_no_selection():
    df = pd.DataFrame({"object": ["Alpha", "Beta"]})
    filtered, options = MultiSelector.searchValueFromMultiSelector(df, "object", None, None)
    assert len(filtered) == 2
    assert [o["value"] for o in options] == ["Alpha", "Beta"]