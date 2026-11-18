import pandas as pd
from dash import html, no_update

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


def test_header_brand_shows_full_name_and_links_home():
    for header in (TMonWidget.build_header(), TMonWidget.build_header(with_login=True)):
        links = [component for component in _walk(header) if isinstance(component, html.A)]
        assert len(links) == 1
        assert links[0].href == "https://tmon.external.test/"
        assert "Txmon - The xAPI Trace Monitor" in list(_texts(header))


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


def test_hidden_dashboard_does_not_rewrite_the_url():
    # A tile navigates to /simlet/<id>. The dashboard is hidden then, so writing
    # its relative `tab=...` query would resolve against that path and replace
    # the id with `tab=home_tab` instead of appending to it.
    assert TMonWidget.url_output({'display': 'none'}, 'tab=home_tab') is no_update
    assert TMonWidget.url_output(None, 'tab=home_tab') is no_update
    # Once the dashboard is open, the URL is its business again.
    assert TMonWidget.url_output({'display': 'block'}, 'tab=home_tab') == 'tab=home_tab'


def _texts(component):
    """Yield every string written anywhere under a Dash component."""
    if isinstance(component, str):
        yield component
        return
    if component is None:
        return
    children = getattr(component, "children", None)
    if isinstance(children, (list, tuple)):
        for child in children:
            yield from _texts(child)
    elif children is not None:
        yield from _texts(children)


# A real response from the SimVA `/simlets` endpoint, kept verbatim so the tile
# stays tied to the field names and shapes the API actually sends.
SIMLET_FROM_API = {
    "simlet_id": 1,
    "simlet_name": "test",
    "simlet_archived": False,
    "simlet_description": "",
    "sessions": [1],
    "groups": [1, 2],
    "tags": [{
        "tag_id": 1, "tag_name": "test", "tag_color": "#3b82f6",
        "tag_right": "READ",
        "createdAt": "2026-11-18T11:30:40.207Z",
        "updatedAt": "2026-11-18T11:30:40.207Z",
    }],
    "createdAt": "2026-11-18T10:24:54.201Z",
    "updatedAt": "2026-11-18T10:24:54.201Z",
    "current_user_id": 3,
    "current_user_username": "teacher",
    "current_user_permission": "FULL",
}


def test_simlet_tile_details_read_the_api_shape():
    assert TMonWidget.simlet_tile_details(SIMLET_FROM_API) == {
        "created": "2026/11/18",
        "updated": "2026/11/18",
        "sessions": 1,
        "groups": 2,
        "participants": 0,
        "tags": [{"name": "test", "color": "#3b82f6"}],
    }
    # The browser annotates each simlet with the count returned by
    # /simlets/<id>/groups/participants/count.
    counted = dict(SIMLET_FROM_API, participants_count=6)
    assert TMonWidget.simlet_tile_details(counted)["participants"] == 6
    # A simlet with no tags says so rather than showing an empty line.
    untagged = dict(SIMLET_FROM_API, tags=[])
    assert TMonWidget.simlet_tile_details(untagged)["tags"] == []


def test_simlet_tile_shows_the_metadata():
    grid = TMonWidget.render_simlet_tiles([SIMLET_FROM_API])
    texts = list(_texts(grid))
    for expected in ("test", "Created at: 2026/11/18", "Updated at: 2026/11/18",
                     "Sessions: 1", "Groups: 2", "Participants: 0", "Tags:"):
        assert expected in texts
    links = [component for component in _walk(grid) if isinstance(component, html.A)]
    assert [link.href for link in links] == ["/simlet/1"]


def test_simlet_tile_uses_legible_text_on_the_light_card():
    grid = TMonWidget.render_simlet_tiles([SIMLET_FROM_API])
    card = next(component for component in _walk(grid)
                if isinstance(component, html.Div)
                and (component.style or {}).get('backgroundColor') == TMonWidget.LIGHT_CARD)
    assert card.children[0].style['color'] == TMonWidget.DARK_BACKGROUND
    assert card.children[1].children[0].style['color'] == TMonWidget.TEXT_SECONDARY


def test_simlet_tile_tags_use_their_own_colours():
    grid = TMonWidget.render_simlet_tiles([SIMLET_FROM_API])
    chips = [component for component in _walk(grid)
             if isinstance(component, html.Span)
             and 'backgroundColor' in (getattr(component, 'style', None) or {})]
    assert [(chip.children, chip.style['backgroundColor']) for chip in chips] == [
        ('test', '#3b82f6')]
    assert chips[0].style['color'] == TMonWidget.TEXT_PRIMARY


def test_tag_text_color_switches_for_light_backgrounds():
    assert TMonWidget.tag_text_color('#3b82f6') == TMonWidget.TEXT_PRIMARY
    assert TMonWidget.tag_text_color('#ffff99') == TMonWidget.DARK_BACKGROUND
    assert TMonWidget.tag_text_color(None) == TMonWidget.TEXT_PRIMARY
