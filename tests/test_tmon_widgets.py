import pandas as pd
from dash import dcc, html, no_update

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
    elif children is not None:
        yield from _walk(children)


def test_header_matches_the_simva_style():
    header = TMonWidget.build_header()
    assert header.className == "header"
    assert header.style["position"] == "sticky"
    assert header.style["top"] == 0
    assert header.style["backgroundColor"] == TMonWidget.BRAND_ORANGE
    assert "boxShadow" in header.style
    sources = [child.src for child in _walk(header) if isinstance(child, html.Img)]
    assert sources[0].startswith("data:image/png;base64,")
    # The Contact us icon is an .ico, like in SIMVA's header.
    assert any(src.startswith("data:image/x-icon;base64,") for src in sources)
    texts = list(_texts(header))
    assert "Txmon - The xAPI Trace Monitor" in texts
    assert "Contact us" in texts


def test_header_brand_shows_full_name_and_links_home():
    for header in (TMonWidget.build_header(), TMonWidget.build_header(with_login=True)):
        links = [component for component in _walk(header) if isinstance(component, html.A)]
        home = [link for link in links if link.href == "https://tmon.external.test/"]
        assert len(home) == 1
        assert "Txmon - The xAPI Trace Monitor" in list(_texts(home[0]))


def test_header_account_controls_only_when_requested():
    plain_ids = [getattr(child, "id", None)
                 for child in _walk(TMonWidget.build_header())]
    assert "main-login" not in plain_ids
    assert "account-button" not in plain_ids
    assert "connection-status" not in plain_ids

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


def test_return_target_points_one_level_up():
    assert TMonWidget.return_target('/') is None
    assert TMonWidget.return_target(None) is None
    assert TMonWidget.return_target('/simlet/1') == '/'
    assert TMonWidget.return_target(
        '/simlet/1/session/11/dashboard/default') == '/simlet/1'
    assert TMonWidget.return_target('/dashboard/upload') == '/'
    assert TMonWidget.return_target('/1/11/Analysis/dashboard/tab=home_tab') == '/simlet/1'


def test_header_has_a_hidden_return_link():
    link = next(child for child in _walk(TMonWidget.TMonSimvaHeader)
                if getattr(child, 'id', None) == 'return-button')
    assert link.style['display'] == 'none'
    assert link.href == ''


def test_dashboard_tabs_are_vertical_with_svg_icons():
    tabs = next(component for component in _walk(TMonWidget.TMonBody)
                if getattr(component, 'id', None) == 't-mon-tabs')
    assert isinstance(tabs, dcc.Tabs)
    assert tabs.vertical is True
    assert tabs.value is None
    assert [tab.id for tab in tabs.children] == [
        f'dashboard-tab-{value}' for value, _, _ in TMonWidget.DASHBOARD_TABS]
    assert 'dashboard-tab-home_tab' in [tab.id for tab in tabs.children]
    for tab in tabs.children:
        icon, name = tab.label.children
        assert isinstance(icon, html.Img)
        assert icon.src.startswith('data:image/svg+xml;base64,')
        assert name.className == 'tab-name'


def test_graph_layout_controls_are_in_the_dashboard():
    ids = [getattr(child, 'id', None) for child in _walk(TMonWidget.TMonBody)]
    for expected in ('graph-layout', 'graph-rows', 'graph-columns', 'graph-page'):
        assert expected in ids


def _graph_content(count):
    return html.Div(html.Div(
        [html.H3('Visualisations')]
        + [dcc.Graph(id=f'graph-{i}') for i in range(count)]
    ))


def test_graph_layout_limits_twelve_graphs_per_page():
    content = _graph_content(20)
    grid = TMonWidget.arrange_graphs(content, 'grid', 2, 3, 1)
    assert grid.style['gridTemplateColumns'] == 'repeat(3, minmax(0, 1fr))'
    assert len([c for c in grid.children if isinstance(c, dcc.Graph)]) == 6
    second = TMonWidget.arrange_graphs(_graph_content(20), 'grid', 2, 3, 2)
    assert len([c for c in second.children if isinstance(c, dcc.Graph)]) == 6
    third = TMonWidget.arrange_graphs(_graph_content(20), 'grid', 2, 3, 3)
    assert len([c for c in third.children if isinstance(c, dcc.Graph)]) == 6
    fourth = TMonWidget.arrange_graphs(_graph_content(20), 'grid', 2, 3, 4)
    assert len([c for c in fourth.children if isinstance(c, dcc.Graph)]) == 2


def test_graph_layout_modes():
    one = TMonWidget.arrange_graphs(_graph_content(5), 'one', 3, 2, 1)
    assert len([c for c in one.children if isinstance(c, dcc.Graph)]) == 1
    vertical = TMonWidget.arrange_graphs(_graph_content(5), 'vertical', 3, 2, 1)
    assert len([c for c in vertical.children if isinstance(c, dcc.Graph)]) == 3
    assert vertical.style['gridTemplateColumns'] == 'repeat(1, minmax(0, 1fr))'
    horizontal = TMonWidget.arrange_graphs(_graph_content(5), 'horizontal', 3, 2, 1)
    assert len([c for c in horizontal.children if isinstance(c, dcc.Graph)]) == 2
    assert horizontal.style['gridTemplateColumns'] == 'repeat(2, minmax(0, 1fr))'


def test_live_updates_live_in_the_footer_and_only_for_simva():
    footer_ids = [getattr(child, 'id', None)
                  for child in _walk(TMonWidget.TMonFooter)]
    for expected in ('live-updates-footer', 'lrs-poll-enabled', 'lrs-poll-rate',
                     'lrs-poll-count', 'lrs-poll-status'):
        assert expected in footer_ids
    content_ids = [getattr(child, 'id', None)
                   for child in _walk(TMonWidget.TMonBody)]
    # The controls are not beside the charts any more.
    assert 'lrs-poll-enabled' not in content_ids
    panel = next(child for child in _walk(TMonWidget.TMonFooter)
                 if getattr(child, 'id', None) == 'live-updates-footer')
    assert panel.style['display'] == 'none'
    assert TMonWidget.live_updates_style('/dashboard/upload') == {'display': 'none'}
    assert TMonWidget.live_updates_style('/') == {'display': 'none'}
    assert TMonWidget.live_updates_style('/simlet/1') == {'display': 'none'}
    assert TMonWidget.live_updates_style(
        '/simlet/1/session/11/dashboard/default')['display'] == 'flex'


def test_interpretation_log_is_visible_only_on_arrival():
    assert TMonWidget.show_interpretation_log_on_arrival(None) == {'display': 'block'}
    assert TMonWidget.show_interpretation_log_on_arrival('') == {'display': 'block'}
    assert TMonWidget.show_interpretation_log_on_arrival('progress_tab') == {
        'display': 'none'}


def test_dashboard_tabs_toggle_collapses_to_icons_only():
    assert TMonWidget.toggle_dashboard_tabs(0) == ('dashboard-tabs-full', '◀')
    assert TMonWidget.toggle_dashboard_tabs(1) == ('dashboard-tabs-compact', '▶')
    assert TMonWidget.toggle_dashboard_tabs(2) == ('dashboard-tabs-full', '◀')


def test_home_tab_is_hidden_only_in_a_session_dashboard():
    assert TMonWidget.hide_home_tab('/simlet/1/session/11/dashboard/default') == {
        'display': 'none'}
    assert TMonWidget.hide_home_tab('/simlet/1') == {'display': 'block'}
    assert TMonWidget.hide_home_tab('/dashboard/upload') == {'display': 'none'}
    assert TMonWidget.hide_home_tab(None) == {'display': 'block'}


def test_session_dashboard_has_no_default_tab(monkeypatch):
    import dash
    monkeypatch.setattr(
        dash, 'callback_context',
        type('Ctx', (), {'triggered': [{'prop_id': 'output-t-mon.style'}]})())
    # The URL has no `tab=` parameter, but the session dashboard still must not
    # fall back to HomePage.
    value, users, objects = TMonWidget.update_tab(
        {'display': 'block'}, '/simlet/1/session/11/dashboard/default',
        '/simlet/1/session/11/dashboard/default')
    assert value is None
    assert users == [] and objects == []


def test_upload_dashboard_never_shows_simlet_tiles(monkeypatch):
    import dash
    from dash import dcc
    monkeypatch.setattr(
        dash, 'callback_context',
        type('Ctx', (), {'triggered': [{'prop_id': 't-mon-tabs.value'}]})())
    statement = {
        'actor': {'name': 'Player'},
        'object': {'id': 'activity-1'},
        'verb': {'id': 'http://example.com/verb'},
    }
    monkeypatch.setattr(TMonWidgets, 'xapiData', [statement])
    monkeypatch.setattr(TMonWidgets, 'accepted_studies', [
        {'id': '1', 'name': 'a simlet'},
    ])
    result = TMonWidget.update_output(
        'home_tab', None, [], None, [],
        panel_style={'display': 'block'}, app_path='/dashboard/upload')
    links = [child for child in _walk(result[3]) if isinstance(child, dcc.Link)]
    anchors = [child for child in _walk(result[3]) if isinstance(child, html.A)]
    assert not links
    assert all(not str(getattr(link, 'href', '')).startswith('/simlet/')
               for link in anchors)


def test_upload_dashboard_tab_shows_its_content(monkeypatch):
    import dash
    monkeypatch.setattr(
        dash, 'callback_context',
        type('Ctx', (), {'triggered': [{'prop_id': 't-mon-tabs.value'}]})())
    statement = {
        'actor': {'name': 'Player'},
        'object': {'id': 'activity-1',
                   'definition': {'type': 'https://w3id.org/xapi/seriousgames/'
                                          'activity-types/Screen'}},
        'verb': {'id': 'http://example.com/verb'},
    }
    monkeypatch.setattr(TMonWidgets, 'xapiData', [statement])
    result = TMonWidget.update_output(
        'progress_tab', None, [], None, [],
        panel_style={'display': 'block'}, app_path='/dashboard/upload')
    assert result[0] is no_update  # local upload must not rewrite the URL
    texts = [child for child in _walk(result[3]) if isinstance(child, str)]
    assert any('Player Progress' in text for text in texts)
    assert not any('no tab selected' in text for text in texts)


def test_no_tab_state_shows_the_selection_and_a_hint(monkeypatch):
    import dash
    monkeypatch.setattr(
        dash, 'callback_context',
        type('Ctx', (), {'triggered': [{'prop_id': 't-mon-tabs.value'}]})())
    result = TMonWidget.update_output(
        None, None, [], None, [], panel_style={'display': 'block'},
        simlet_name='test', session_name='survey')
    content = result[3]
    texts = [child for child in _walk(content) if isinstance(child, str)]
    assert 'T-Mon Home Page.' in texts
    assert 'no tab selected, select one tab.' in texts


def test_default_page_shows_the_no_tab_message():
    content = TMonWidget.render_homepage_content()
    texts = [child for child in _walk(html.Div(content)) if isinstance(child, str)]
    assert 'no tab selected, select one tab.' in texts


def test_dashboard_header_names_the_selection():
    assert TMonWidget.update_dashboard_title(
        {'display': 'block'}, 'test', 'survey') == 'test / survey'
    assert TMonWidget.update_dashboard_title(
        {'display': 'block'}, html.Div(), html.Div()) == ''
    assert TMonWidget.update_dashboard_title(
        {'display': 'none'}, 'test', 'survey') == ''


def test_dashboard_layout_puts_content_to_the_right_of_the_tabs():
    def find(component, id):
        return next(c for c in _walk(component) if getattr(c, 'id', None) == id)

    body = TMonWidget.TMonBody
    header = find(body, 'dashboard-header')
    assert find(header, 'dashboard-title') is not None
    assert find(header, 'users-multi-dynamic-dropdown') is not None
    assert find(header, 'object-multi-dynamic-dropdown') is not None
    assert find(header, 'activity-filter-div') is not None
    tabs = find(body, 'dashboard-tabs-wrapper')
    content = find(body, 'dashboard-content')
    assert find(content, 'tabs-content') is not None
    assert find(content, 'content') is not None
    assert find(content, 'chart-creator-controls') is not None
    # The sidebar and the content are siblings under one flex row.
    row = next(c for c in _walk(body)
               if isinstance(c, html.Div)
               and (getattr(c, 'style', None) or {}).get('display') == 'flex'
               and tabs in (c.children or []) and content in (c.children or []))
    assert row.style['display'] == 'flex'
