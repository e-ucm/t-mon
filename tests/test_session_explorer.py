"""Tests for the simlet's Sessions list UI."""

from dash import html
from dash.exceptions import PreventUpdate

import dash
import TMonWidgets
from TMonWidgets import SessionExplorer as Explorer


SESSIONS = [
    {
        'session_id': 11, 'session_name': 'First session',
        'session_description': 'the intro', 'session_status': 'active',
        'createdAt': '2026-11-18T10:24:54.201Z',
        'activities': [1, 2],
        'tags': [{'tag_id': 1, 'tag_name': 'maths', 'tag_color': '#3b82f6'}],
    },
    {
        'session_id': 12, 'session_name': 'Second session',
        'session_description': 'the follow-up', 'session_status': 'inactive',
        'createdAt': '2026-11-01T10:24:54.201Z',
        'activities': [3], 'tags': [],
    },
    {
        'session_id': 13, 'session_name': 'Third session',
        'session_description': 'the wrap-up', 'session_status': 'terminated',
        'createdAt': '2026-10-01T10:24:54.201Z',
        'activities': [], 'tags': [],
    },
]


def _texts(component):
    if isinstance(component, str):
        yield component
        return
    children = getattr(component, 'children', None)
    if isinstance(children, (list, tuple)):
        for child in children:
            yield from _texts(child)
    elif children is not None:
        yield from _texts(children)


def _walk(component):
    yield component
    children = getattr(component, 'children', None)
    if isinstance(children, (list, tuple)):
        for child in children:
            yield from _walk(child)
    elif children is not None and hasattr(children, 'children'):
        yield from _walk(children)


def test_simlet_path_detection():
    assert Explorer.is_simlet_path('output/1/') is True
    assert Explorer.is_simlet_path('output/1/', 'output/') is True
    assert Explorer.is_simlet_path('output/') is False
    assert Explorer.is_simlet_path('output/1/11/') is False
    assert Explorer.is_simlet_path(None) is False


def test_default_query_uses_four_per_page_and_the_default_sort():
    assert Explorer.build_session_query(Explorer.parse_session_query('')) == (
        'status=&skip=0&limit=4&orderBy=id&order=asc')
    # A list link carrying the simlets' desc order is normalised to a choice
    # that the Sessions sort dropdown can actually display.
    assert Explorer.parse_session_query('?orderBy=id&order=desc')['order'] == 'asc'


def test_session_filters_status_search_tags_sort_and_page():
    def ids(search=''):
        page, total = Explorer.apply_session_filters(
            SESSIONS, Explorer.parse_session_query(search))
        return [session['session_id'] for session in page], total

    assert ids() == ([11, 12, 13], 3)  # "Default" is id ascending
    assert ids('?status=active')[0] == [11]
    assert ids('?status=inactive')[0] == [12]
    assert ids('?status=terminated')[0] == [13]
    assert ids('?searchString=FOLLOW')[0] == [12]
    assert ids('?searchTags=1')[0] == [11]
    assert ids('?orderBy=name&order=asc')[0] == [11, 12, 13]
    assert ids('?limit=2')[0] == [11, 12]
    assert ids('?skip=2&limit=2')[0] == [13]


def test_session_cards_look_like_the_simva_sessions_tab():
    page, _ = Explorer.apply_session_filters(SESSIONS, Explorer.parse_session_query(''))
    cards = Explorer.render_session_cards(page)
    texts = list(_texts(cards))
    for expected in ('First session', 'the intro', 'Active', 'Created at: 2026/11/18',
                     'Activities: 2', 'Participants: 0', 'maths'):
        assert expected in texts

    # The session card is no longer clickable; only the dashboard tiles are.
    # Activities stay collapsed: only the count is on the card.
    assert not any(isinstance(child, html.Table) for child in _walk(cards))


def test_each_session_card_has_dashboard_tiles_and_a_create_button():
    page, _ = Explorer.apply_session_filters(SESSIONS, Explorer.parse_session_query(''))
    cards = Explorer.render_session_cards(page)
    creates = [child for child in _walk(cards)
               if isinstance(child, html.Button)
               and (getattr(child, 'id', None) or {}).get('type')
               == 'dashboard-add']
    assert len(creates) >= 1
    assert '+' in [text for text in _texts(cards)]


def test_status_badges_use_the_simva_colours():
    page, _ = Explorer.apply_session_filters(SESSIONS, Explorer.parse_session_query(''))
    spans = [child for child in _walk(Explorer.render_session_cards(page))
             if isinstance(child, html.Div) and 'backgroundColor' in (getattr(child, 'style', None) or {})]
    colors = [span.style['backgroundColor'] for span in spans
              if span.style['backgroundColor'] in ('#8ec26d', '#fbfd68', '#f07667')]
    assert colors == ['#8ec26d', '#fbfd68', '#f07667']


def test_sort_dropdown_has_a_matching_initial_value():
    controls = Explorer.render_session_controls(
        Explorer.parse_session_query(''), SESSIONS)
    sort = next(child for child in _walk(controls)
                if getattr(child, 'id', None) == 'session-explorer-sort')
    assert sort.value == 'id:asc'
    assert sort.value in [option['value'] for option in sort.options]
    assert any(option['label'] == 'Default' for option in sort.options)


class _Context:
    def __init__(self, source):
        self.triggered = [{'prop_id': source}]


def test_session_callback_renders_only_on_a_simlet(monkeypatch):
    monkeypatch.setattr(TMonWidgets, 'accepted_sessions', SESSIONS, raising=False)
    monkeypatch.setattr(dash, 'callback_context', _Context('session-explorer-search.value'))

    style, cards, info, state = Explorer.update_session_explorer(
        'output/1/', None, '', '', 'id:asc', [], 4, 0, 0, {'skip': 0})
    assert style == {'display': 'block'}
    assert 'First session' in list(_texts(cards))
    assert info == '1-3 of 3'

    # Outside a simlet the callback leaves the panel alone.
    monkeypatch.setattr(dash, 'callback_context', _Context('current-path.children'))
    try:
        Explorer.update_session_explorer(
            'output/', None, '', '', 'id:asc', [], 4, 0, 0, {'skip': 0})
    except PreventUpdate:
        pass
    else:
        raise AssertionError('the sessions list should not render outside a simlet')
