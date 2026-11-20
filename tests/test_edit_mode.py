"""Tests for ADR 0018: edit mode for tabs and visualisations."""
import pandas as pd
import pytest
from dash import dcc, html

from TMonWidgets import I18n, TMonWidget
from TMonWidgets.ChartBuilder import (
    COUNT_LABEL, build_chart, decode_specs, describe, encode_spec, normalise_spec,
)
from TMonWidgets.PageConfig import build_document, parse_document, serialize


def _walk(component):
    yield component
    children = getattr(component, 'children', None)
    if isinstance(children, (list, tuple)):
        for child in children:
            yield from _walk(child)
    elif children is not None:
        yield from _walk(children)
    label = getattr(component, 'label', None)
    if label is not None and label is not children:
        yield from _walk(label)


def _spec(**labels):
    data = {'type': 'bar', 'x': 'actor.name', 'y': COUNT_LABEL,
            'aggregation': 'count'}
    data.update(labels)
    return normalise_spec(data)


def _ctx(monkeypatch, prop_id):
    import dash

    class Ctx:
        triggered = [{'prop_id': prop_id}]

    monkeypatch.setattr(dash, 'callback_context', Ctx())


# --- graph labels as data --------------------------------------------------


def test_labels_are_kept_only_when_written():
    assert _spec() == {'type': 'bar', 'x': 'actor.name', 'y': COUNT_LABEL,
                       'aggregation': 'count'}
    spec = _spec(title='Players', x_label='Player', y_label='Count')
    assert spec['title'] == 'Players'
    assert spec['x_label'] == 'Player'
    assert spec['y_label'] == 'Count'


def test_describe_prefers_the_users_title():
    spec = _spec(title='My own title')
    assert describe(spec) == 'My own title'
    assert describe(_spec()) == 'name - number of statements'


def test_build_chart_applies_the_labels():
    df = pd.DataFrame({'actor.name': ['a', 'b'], 'score': [1, 2]})
    spec = normalise_spec({
        'type': 'bar', 'x': 'actor.name', 'y': 'score', 'aggregation': 'sum',
        'title': 'Score by player', 'x_label': 'Player', 'y_label': 'Points',
    })
    figure = build_chart(df, spec)
    assert figure.layout.title.text == 'Score by player'
    assert figure.layout.xaxis.title.text == 'Player'
    assert figure.layout.yaxis.title.text == 'Points'


def test_labels_travel_in_a_link_without_breaking_it():
    spec = _spec(title='A | B, C & D', x_label='X, axis', y_label='Y|axis')
    encoded = encode_spec(spec)
    assert decode_specs(encoded) == [spec]
    # Links and configs without labels keep the old four-field shape.
    assert encode_spec(_spec()) == f'bar|actor.name|-|count'
    assert decode_specs('bar|actor.name|-|count') == [_spec()]


def test_config_documents_keep_labels():
    spec = _spec(title='Labelled')
    document = build_document(charts=[spec])
    assert parse_document(serialize(document))['create_tab']['charts'] == [spec]


# --- layout exposes edit-mode controls ------------------------------------


def test_layout_exposes_edit_mode_controls():
    ids = [getattr(child, 'id', None) for child in _walk(TMonWidget.TMonBody)]
    for expected in (
        'edit-mode', 'edit-toggle', 'dashboard-page-controls',
        'item-edit-index', 'tab-remove-pending',
        'new-tab-add', 'item-title', 'item-xlabel', 'item-ylabel', 'item-y',
        'item-aggregation', 'item-labels-div', 'tab-remove-confirm-modal',
        'tab-remove-confirm', 'tab-remove-cancel',
    ):
        assert expected in ids, expected


def test_new_tab_is_shown_in_edit_mode_and_custom_tabs_get_remove():
    pages = [{'id': 'p1', 'name': 'My page', 'charts': [], 'filters': []}]
    view = TMonWidget.dashboard_tab_children(pages)
    edit = TMonWidget.dashboard_tab_children(pages, edit_mode=True)
    ids_view = [getattr(node, 'id', None) for tab in view for node in _walk(tab)]
    ids_edit = [getattr(node, 'id', None) for tab in edit for node in _walk(tab)]
    assert not any(isinstance(i, dict) and i.get('type') == 'tab-remove' for i in ids_view)
    assert any(isinstance(i, dict) and i.get('type') == 'tab-remove'
               and i.get('index') == 'p1' for i in ids_edit)
    # Built-in tabs are never removable, in either mode.
    builtin = [tab for tab in edit if getattr(tab, 'value', '') != 'page:p1']
    builtin_ids = [getattr(node, 'id', None) for tab in builtin for node in _walk(tab)]
    assert not any(isinstance(i, dict) and i.get('type') == 'tab-remove'
                   for i in builtin_ids)


def test_rendered_items_have_edit_controls_only_in_edit_mode():
    df = pd.DataFrame({'actor.name': ['a', 'b']})
    view = TMonWidget.render_page_items(df, [_spec()], [], 'create_tab', False)
    edit = TMonWidget.render_page_items(df, [_spec()], [], 'create_tab', True)

    def styles(items):
        return [(getattr(node, 'id', None), getattr(node, 'style', None))
                for item in items for node in _walk(item)]

    view_ids = [identifier for identifier, _ in styles(view)]
    edit_ids = [identifier for identifier, _ in styles(edit)]
    assert any(isinstance(i, dict) and i.get('type') == 'item-edit' for i in view_ids)
    assert any(isinstance(i, dict) and i.get('type') == 'item-edit' for i in edit_ids)
    view_slot = [style for identifier, style in styles(view)
                 if isinstance(identifier, dict)
                 and identifier.get('type') == 'item-add-slot'][0]
    edit_slot = [style for identifier, style in styles(edit)
                 if isinstance(identifier, dict)
                 and identifier.get('type') == 'item-add-slot'][0]
    assert view_slot['display'] == 'none'
    assert edit_slot['display'] == 'block'


# --- callbacks -------------------------------------------------------------


def test_page_state_arguments_follow_dash_input_then_state_order():
    """Dash calls with every Input first; a State must never land in n_clicks."""
    import inspect

    params = list(inspect.signature(TMonWidget.update_page_state).parameters)
    assert params[:13] == [
        'page_add_n', 'page_rename_n', 'page_delete_n', 'item_add_n',
        'item_remove_n', 'filter_values', 'chart_add_n', 'chart_remove_n',
        'panel_style', 'config_command', 'tab_remove_clicks',
        'confirm_remove_n', 'new_tab_n',
    ]
    assert params[13:30] == [
        'tab', 'target', 'page_name', 'item_kind', 'item_chart_type',
        'item_column', 'item_game', 'item_target', 'item_mode',
        'chart_type', 'chart_x', 'chart_y', 'chart_aggregation',
        'pages', 'charts', 'filters', 'pathname',
    ]


def test_edit_toggle_switches_between_view_and_edit(monkeypatch):
    _ctx(monkeypatch, 'edit-toggle.n_clicks')
    enabled, label, style, page_style = TMonWidget.toggle_edit_mode(1, False)
    assert enabled is True
    assert label == I18n.t('edit.mode.disable')
    assert style['display'] == 'block'
    assert page_style['display'] == 'block'
    enabled, label, style, page_style = TMonWidget.toggle_edit_mode(1, True)
    assert enabled is False
    assert style['display'] == 'none'
    assert page_style['display'] == 'none'


def test_tab_remove_asks_before_removing(monkeypatch):
    _ctx(monkeypatch, '{"index":"p1","type":"tab-remove"}.n_clicks')
    pending, style = TMonWidget.handle_tab_remove_request([1], 0, 0, None)
    assert pending == 'p1'
    assert style['display'] == 'block'
    _ctx(monkeypatch, 'tab-remove-confirm.n_clicks')
    assert TMonWidget.handle_tab_remove_request([1], 1, 0, 'p1') == (
        None, {'display': 'none'})


def test_edit_button_opens_the_popup_for_an_existing_item(monkeypatch):
    _ctx(monkeypatch, '{"index":"chart:0","type":"item-edit"}.n_clicks')
    style, target, edit = TMonWidget.toggle_item_modal(
        [], 0, 0, [1], [], 'page:p1')
    assert style['display'] == 'block'
    assert target == 'page:p1'
    assert edit == {'index': 'chart:0'}


def test_popup_is_prefilled_with_the_graph_and_its_labels():
    spec = _spec(title='Title', x_label='X', y_label='Y')
    result = TMonWidget.prefill_item_modal(
        {'index': 'chart:0'}, 'create_tab', [spec], [], [])
    assert result[0] == 'bar'
    assert result[1] == 'actor.name'
    assert result[3:6] == ('Title', 'X', 'Y')


def test_new_tab_button_creates_an_empty_page(monkeypatch):
    _ctx(monkeypatch, 'new-tab-add.n_clicks')
    pages, charts, filters, _, _ = TMonWidget.update_page_state(
        None, None, None, None, None, None, None, None,
        {'display': 'block'}, None, None, None, 1,
        'create_tab', None, 'From the tab',
        None, None, None, None, None, None,
        None, None, None, None, [], [], [], None)
    assert len(pages) == 1
    assert pages[0]['name'] == 'From the tab'
    assert pages[0]['charts'] == []


def test_confirming_a_tab_removal_deletes_that_page(monkeypatch):
    _ctx(monkeypatch, 'tab-remove-confirm.n_clicks')
    pages = [
        {'id': 'p1', 'name': 'First', 'charts': [], 'filters': []},
        {'id': 'p2', 'name': 'Second', 'charts': [], 'filters': []},
    ]
    result = TMonWidget.update_page_state(
        None, None, None, None, None, None, None, None,
        {'display': 'block'}, None, None, 1, None,
        'create_tab', None, None,
        None, None, None, None, None, None,
        None, None, None, None, pages, [], [], None,
        pending_remove='p1')
    assert [page['id'] for page in result[0]] == ['p2']


def test_editing_a_graph_replaces_the_spec_with_its_labels(monkeypatch):
    _ctx(monkeypatch, 'item-add.n_clicks')
    original = _spec()
    _, charts, _, _, _ = TMonWidget.update_page_state(
        None, None, None, 1, None, None, None, None,
        {'display': 'block'}, None, None, None, None,
        'create_tab', None, None,
        'bar', None, 'actor.name', None, None, None,
        None, None, None, None, [], [original], [], None,
        item_edit_index={'index': 'chart:0'},
        item_title='Edited title', item_xlabel='Player', item_ylabel='Count',
        item_y=COUNT_LABEL, item_aggregation='count')
    assert len(charts) == 1
    assert charts[0]['title'] == 'Edited title'
    assert charts[0]['x_label'] == 'Player'
    assert charts[0]['y_label'] == 'Count'


# --- translations ----------------------------------------------------------


def test_edit_mode_labels_exist_in_every_language():
    keys = [
        'edit.mode.enable', 'edit.mode.disable', 'edit.remove', 'edit.item',
        'edit.graph', 'edit.filter', 'edit.new_tab', 'edit.remove_tab',
        'edit.confirm_tab', 'edit.label.title', 'edit.label.x', 'edit.label.y',
        'visual.y',
    ]
    for language in ('en', 'es', 'fr'):
        for key in keys:
            assert I18n.translate(key, language) != key
