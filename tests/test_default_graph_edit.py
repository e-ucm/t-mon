"""ADR 0018: administrators edit default-dashboard graphs without touching JSON."""
import json

import pandas as pd

from TMonWidgets import TMonWidget, UserRoles
from TMonWidgets.ChartBuilder import COUNT_LABEL, normalise_spec
from TMonWidgets.PageConfig import build_document, parse_document, serialize

GRAPH = {
    'id': 'statements-by-player',
    'type': 'bar',
    'title': 'Statements by player',
    'x': {'data': 'actor.name', 'label': 'Player'},
    'y': {'data': 'count', 'label': 'Statements'},
    'aggregation': 'count',
}
PAGE = {'id': 'progress', 'graphs': [GRAPH]}
TAB = {'id': 'progress_tab', 'title': 'Progress', 'pages': [PAGE]}
KEY = 'progress_tab:progress:statements-by-player'


def _walk(component):
    yield component
    children = getattr(component, 'children', None)
    if isinstance(children, (list, tuple)):
        for child in children:
            yield from _walk(child)
    elif children is not None:
        yield from _walk(children)


def _ctx(monkeypatch, prop_id):
    import dash

    monkeypatch.setattr(
        dash, 'callback_context',
        type('Ctx', (), {'triggered': [{'prop_id': prop_id, 'value': 1}]})())


def _chart_df():
    return pd.DataFrame({'actor.name': ['a', 'b', 'a']})


# --- roles ---------------------------------------------------------------


def test_roles_are_read_from_every_claim_shape():
    assert UserRoles.roles_from_claims(
        {'realm_access': {'roles': ['administrator', 'student']}}
    ) == {'administrator', 'student'}
    assert UserRoles.roles_from_claims(
        {'resource_access': {'tmon': {'roles': ['teacher']}}}
    ) == {'teacher'}
    assert UserRoles.roles_from_claims({'roles': ['researcher']}) == {'researcher'}
    assert UserRoles.roles_from_claims({'groups': ['default-role']}) == {'default-role'}
    assert UserRoles.roles_from_claims(None) == set()


def test_only_administrator_is_admin():
    assert UserRoles.ROLE_ADMINISTRATOR == 'administrator'
    assert 'administrator' in UserRoles.KNOWN_ROLES
    assert 'researcher' in UserRoles.KNOWN_ROLES


# --- definition graph to chart spec --------------------------------------


def test_default_graph_spec_reads_the_definition():
    spec = TMonWidget.default_graph_spec(GRAPH)
    assert spec == {
        'type': 'bar', 'x': 'actor.name', 'y': COUNT_LABEL,
        'aggregation': 'count', 'title': 'Statements by player',
        'x_label': 'Player', 'y_label': 'Statements',
    }


def test_types_the_builder_cannot_draw_are_not_editable():
    assert TMonWidget.default_graph_spec({'id': 'h', 'type': 'heatmap',
                                          'x': {'data': 'a'},
                                          'y': {'data': 'b'}}) is None
    assert TMonWidget.default_graph_spec({'id': 't', 'type': 'table'}) is None


def test_find_default_graph_uses_the_key():
    dashboard = {'tabs': [TAB]}
    assert TMonWidget.find_default_graph(KEY, dashboard) is GRAPH
    assert TMonWidget.find_default_graph('nope:nope:nope', dashboard) is None


# --- rendering -----------------------------------------------------------


def test_admin_in_edit_mode_gets_an_edit_control_on_default_graphs():
    page = TMonWidget.render_default_page(
        TAB, PAGE, _chart_df(), _chart_df(), {}, edit_mode=True, admin=True)
    ids = [getattr(node, 'id', None) for node in _walk(page)]
    assert {'type': 'default-graph-edit', 'index': KEY} in ids


def test_non_admin_or_view_mode_gets_no_default_edit_control():
    for kwargs in ({'edit_mode': True, 'admin': False},
                   {'edit_mode': False, 'admin': True}):
        page = TMonWidget.render_default_page(
            TAB, PAGE, _chart_df(), _chart_df(), {}, **kwargs)
        ids = [getattr(node, 'id', None) for node in _walk(page)]
        assert not any(isinstance(item, dict)
                       and item.get('type') == 'default-graph-edit'
                       for item in ids)


def test_heatmaps_never_get_an_edit_control():
    heatmap = {'id': 'heat', 'type': 'heatmap',
               'x': {'data': 'object.id'}, 'y': {'data': 'actor.name'}}
    page = TMonWidget.render_default_page(
        TAB, {'id': 'progress', 'graphs': [heatmap]}, _chart_df(), _chart_df(),
        {}, edit_mode=True, admin=True)
    ids = [getattr(node, 'id', None) for node in _walk(page)]
    assert not any(isinstance(item, dict)
                   and item.get('type') == 'default-graph-edit'
                   for item in ids)


def test_an_override_replaces_the_figure_but_not_the_definition():
    override = normalise_spec({**TMonWidget.default_graph_spec(GRAPH),
                               'title': 'Edited title'})
    page = TMonWidget.render_default_page(
        TAB, PAGE, _chart_df(), _chart_df(), {}, edit_mode=True, admin=True,
        overrides={KEY: override})
    figures = [node.figure for node in _walk(page)
               if getattr(node, 'id', '') == 'default-progress_tab-progress-statements-by-player']
    assert figures[0].layout.title.text == 'Edited title'
    # The definition itself is untouched.
    assert GRAPH['title'] == 'Statements by player'


# --- popup ---------------------------------------------------------------


def test_edit_button_opens_the_floater_for_a_default_graph(monkeypatch):
    _ctx(monkeypatch,
         json.dumps({'index': KEY, 'type': 'default-graph-edit'}) + '.n_clicks')
    result = TMonWidget.toggle_edit_floater(
        0, 0, 0, 0, 0, [], [], 0, 0, [], [1], 0, 'progress_tab', True)
    assert result[3]['display'] == 'flex'
    assert result[4] == 'create'
    assert result[6] == {'index': f'default:{KEY}'}


def test_prefill_reads_the_definition_and_any_override():
    result = TMonWidget.prefill_item_modal(
        {'index': f'default:{KEY}'}, None, None, [], [], [], {})
    assert result[0] == 'bar'
    assert result[1] == 'actor.name'
    assert result[3:6] == ('Statements by player', 'Player', 'Statements')
    assert result[6] == COUNT_LABEL
    assert result[7] == 'count'

    override = normalise_spec({**TMonWidget.default_graph_spec(GRAPH),
                               'title': 'Saved edit', 'x': 'actor.name'})
    result = TMonWidget.prefill_item_modal(
        {'index': f'default:{KEY}'}, None, None, [], [], [], {KEY: override})
    assert result[3] == 'Saved edit'


def test_saving_the_popup_stores_an_override(monkeypatch):
    _ctx(monkeypatch, 'item-add.n_clicks')
    monkeypatch.setattr(TMonWidget, 'is_admin', lambda: True)
    result = TMonWidget.update_default_graph_overrides(
        1, None, {'index': f'default:{KEY}'}, {},
        'bar', 'actor.name', COUNT_LABEL, 'count',
        'Edited', 'Player', 'Statements')
    assert result[KEY]['title'] == 'Edited'
    assert result[KEY]['x_label'] == 'Player'


def test_saving_a_created_chart_does_not_write_an_override(monkeypatch):
    import pytest
    from dash.exceptions import PreventUpdate

    _ctx(monkeypatch, 'item-add.n_clicks')
    monkeypatch.setattr(TMonWidget, 'is_admin', lambda: True)
    with pytest.raises(PreventUpdate):
        TMonWidget.update_default_graph_overrides(
            1, None, {'index': 'chart:0'}, {},
            'bar', 'actor.name', COUNT_LABEL, 'count', '', '', '')


def test_a_non_admin_cannot_write_an_override(monkeypatch):
    import pytest
    from dash.exceptions import PreventUpdate

    _ctx(monkeypatch, 'item-add.n_clicks')
    monkeypatch.setattr(TMonWidget, 'is_admin', lambda: False)
    with pytest.raises(PreventUpdate):
        TMonWidget.update_default_graph_overrides(
            1, None, {'index': f'default:{KEY}'}, {},
            'bar', 'actor.name', COUNT_LABEL, 'count',
            'Edited', 'Player', 'Statements')


def test_editing_a_default_graph_does_not_add_a_page_chart(monkeypatch):
    _ctx(monkeypatch, 'item-add.n_clicks')
    _, charts, _, _ = TMonWidget.update_page_state(
        None, None, None, 1, None, None,
        {'display': 'block'}, None, None, None, None,
        'progress_tab', None, None,
        'bar', None, 'actor.name', None, None, None,
        [], [], [], None,
        item_edit_index={'index': f'default:{KEY}'})
    assert charts == []


# --- configuration -------------------------------------------------------


def test_configuration_carries_default_graph_overrides():
    override = normalise_spec({**TMonWidget.default_graph_spec(GRAPH),
                               'title': 'Edited'})
    document = build_document(default_graph_overrides={KEY: override})
    parsed = parse_document(serialize(document))
    assert parsed['default_graph_overrides'] == {KEY: override}


def test_configuration_drops_overrides_that_are_not_charts():
    document = parse_document(serialize({
        'version': 1,
        'default_graph_overrides': {KEY: {'type': 'bar'}, 'bad': 'nope'},
    }))
    assert document['default_graph_overrides'] == {}
