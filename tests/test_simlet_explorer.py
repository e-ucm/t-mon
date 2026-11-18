"""Tests for the query-parameter driven simlet explorer."""

import dash
import TMonWidgets
from TMonWidgets import SimletExplorer as Explorer


STUDIES = [
    {
        'simlet_id': 1, 'simlet_name': 'Alpha', 'simlet_archived': False,
        'simlet_description': 'the first study',
        'createdAt': '2026-11-01T10:00:00.000Z',
        'updatedAt': '2026-11-18T10:00:00.000Z',
        'tags': [{'tag_id': 1, 'tag_name': 'maths', 'tag_color': '#3b82f6'}],
    },
    {
        'simlet_id': 2, 'simlet_name': 'Beta', 'simlet_archived': False,
        'simlet_description': 'the second study',
        'createdAt': '2026-11-02T10:00:00.000Z',
        'updatedAt': '2026-11-10T10:00:00.000Z',
        'tags': [{'tag_id': 2, 'tag_name': 'physics', 'tag_color': '#f00'}],
    },
    {
        'simlet_id': 3, 'simlet_name': 'Gamma', 'simlet_archived': True,
        'simlet_description': 'an old study',
        'createdAt': '2026-10-01T10:00:00.000Z',
        'updatedAt': '2026-10-02T10:00:00.000Z',
        'tags': [],
    },
]


def test_default_query_matches_the_simva_front_convention():
    assert Explorer.build_simlet_query(Explorer.parse_simlet_query('')) == (
        'status=active&skip=0&limit=9&orderBy=id&order=asc')


def test_query_round_trip_and_bad_values():
    search = '?status=archived&skip=9&limit=18&orderBy=name&order=desc' \
             '&searchString=alpha&searchTags=1,2'
    filters = Explorer.parse_simlet_query(search)
    assert filters == {
        'status': 'archived', 'searchString': 'alpha', 'skip': 9, 'limit': 18,
        'orderBy': 'name', 'order': 'desc', 'searchTags': ['1', '2'],
    }
    assert Explorer.build_simlet_query(filters) == search.lstrip('?')

    sane = Explorer.parse_simlet_query('?status=bogus&skip=-5&limit=999'
                                       '&orderBy=nope&order=sideways')
    assert sane['status'] == 'active'
    assert sane['skip'] == 0
    assert sane['limit'] == Explorer.MAX_LIMIT
    assert sane['orderBy'] == 'id'
    assert sane['order'] == 'asc'


def test_filters_status_search_and_tags():
    def ids(search=''):
        page, total = Explorer.apply_simlet_filters(STUDIES, Explorer.parse_simlet_query(search))
        assert total == len(page)
        return [study['simlet_id'] for study in page]

    assert ids() == [1, 2]
    assert ids('?status=archived') == [3]
    assert ids('?searchString=FIRST') == [1]
    assert ids('?searchTags=2') == [2]
    assert ids('?searchTags=1,2') == [1, 2]
    assert ids('?searchTags=3') == []


def test_sorting_and_pagination():
    def ids(search=''):
        page, total = Explorer.apply_simlet_filters(STUDIES, Explorer.parse_simlet_query(search))
        return [study['simlet_id'] for study in page], total

    assert ids('?orderBy=name&order=desc')[0] == [2, 1]
    assert ids('?orderBy=createdAt&order=asc')[0] == [1, 2]
    assert ids('?orderBy=updatedAt&order=asc')[0] == [2, 1]

    # Two active simlets, one per page.
    assert ids('?limit=1')[0] == [1]
    assert ids('?skip=1&limit=1')[0] == [2]
    page, total = Explorer.apply_simlet_filters(
        STUDIES, Explorer.parse_simlet_query('?skip=1&limit=1'))
    assert total == 2


def test_tag_options_come_from_the_loaded_simlets():
    options = Explorer.available_tag_options(STUDIES)
    assert options == [
        {'label': 'maths', 'value': '1'},
        {'label': 'physics', 'value': '2'},
    ]


def test_controls_are_initialised_from_the_url():
    controls = Explorer.render_simlet_controls(
        Explorer.parse_simlet_query('?status=archived&searchString=old&limit=7'), STUDIES)
    values = {child.id: getattr(child, 'value', None) for child in controls.children
              if getattr(child, 'id', None)}
    assert values['simlet-explorer-status'] == 'archived'
    assert values['simlet-explorer-search'] == 'old'
    assert values['simlet-explorer-sort'] == 'id:asc'
    assert values['simlet-explorer-limit'] == 7
    assert values['simlet-explorer-tags'] == []

class _Context:
    def __init__(self, source):
        self.triggered = [{'prop_id': source}]


def test_callback_updates_grid_info_and_url(monkeypatch):
    monkeypatch.setattr(TMonWidgets, 'accepted_studies', STUDIES)
    monkeypatch.setattr(dash, 'callback_context', _Context('simlet-explorer-search.value'))

    grid, info, search = Explorer.update_simlet_explorer(
        'active', 'alpha', 'id:asc', [], 9, 0, 0, None, None, '')
    assert 'Alpha' in [child for child in _texts(grid)]
    assert info == '1-1 of 1'
    assert 'searchString=alpha' in search
    assert 'skip=0' in search

    monkeypatch.setattr(dash, 'callback_context', _Context('simlet-explorer-next.n_clicks'))
    _, info, search = Explorer.update_simlet_explorer(
        'active', '', 'id:asc', [], 1, 0, 1, None, None, '?limit=1&skip=0')
    assert info == '2-2 of 2'
    assert 'skip=1' in search


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
