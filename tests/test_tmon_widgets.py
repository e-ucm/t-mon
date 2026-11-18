import pandas as pd
from dash import html

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


def _walk(component):
    """Yield a Dash component and everything nested in its children."""
    yield component
    children = getattr(component, "children", None)
    if isinstance(children, (list, tuple)):
        for child in children:
            yield from _walk(child)
    elif children is not None and hasattr(children, "children"):
        yield from _walk(children)


def test_header_is_sticky_and_shows_both_logos():
    header = TMonWidget.build_header()
    assert header.style["position"] == "sticky"
    assert header.style["top"] == 0
    assert header.style["backgroundColor"] == TMonWidget.BRAND_ORANGE
    sources = [child.src for child in _walk(header) if isinstance(child, html.Img)]
    assert len(sources) == 2
    assert all(src.startswith("data:image/png;base64,") for src in sources)
    assert sources[0] != sources[1]


def test_header_login_controls_only_when_requested():
    plain_ids = [getattr(child, "id", None)
                 for child in _walk(TMonWidget.build_header())]
    assert "main-login" not in plain_ids
    assert "login-logout-button" not in plain_ids

    simva_ids = [getattr(child, "id", None)
                 for child in _walk(TMonWidget.build_header(with_login=True))]
    for expected in ("main-login", "login-logout-button", "account-button",
                     "login-logout", "account", "connection-status"):
        assert expected in simva_ids


def test_footer_stays_at_the_bottom():
    footer = TMonWidget.TMonFooter
    assert footer.style["position"] == "sticky"
    assert footer.style["bottom"] == 0
    # Pushes the footer down when the page content is shorter than the viewport.
    assert footer.style["marginTop"] == "auto"
