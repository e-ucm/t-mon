"""Tests for ADR 0017: data-driven default dashboards."""
import copy
import inspect
import json

import dash
import pandas as pd
import pytest
from dash import dcc, dash_table

from TMonWidgets import DefaultDashboard, GraphTypes, I18n, TMonWidget
from TMonWidgets.DefaultDashboard import DashboardDefinitionError

TITLE = "Progress over time"


def _walk(component):
    yield component
    children = getattr(component, "children", None)
    if isinstance(children, (list, tuple)):
        for child in children:
            yield from _walk(child)
    elif children is not None:
        yield from _walk(children)


def _definition(**changes):
    """A small but complete definition, easy to corrupt for validation tests."""
    document = {
        "version": DefaultDashboard.FORMAT_VERSION,
        "name": "Test dashboard",
        "layout": {"type": "grid", "columns": 3, "rows": 2},
        "general_filters": [],
        "tabs": [
            {
                "id": "overview",
                "title": "Overview",
                "markdown": "# Overview",
                "general_filters": [],
                "pages": [
                    {
                        "id": "main",
                        "title": "Main",
                        "markdown": "Some **markdown**.",
                        "graphs": [
                            {
                                "id": "progress",
                                "title": TITLE,
                                "type": "line",
                                "x": {"label": "Time", "data": "timestamp",
                                      "date": True},
                                "y": {"label": "Progress", "data": "result.progress"},
                            }
                        ],
                    }
                ],
            }
        ],
    }
    document.update(changes)
    return document


def _data():
    return pd.DataFrame({
        "actor.name": ["a", "b", "a", "a"],
        "verb.id": ["progressed", "progressed", "initialized", "progressed"],
        "object.id": ["game", "game", "game", "other"],
        "timestamp": ["2026-01-01T00:00:00Z", "2026-01-01T00:01:00Z",
                      "2026-01-01T00:02:00Z", "2026-01-01T00:03:00Z"],
        "result.progress": [0.1, 0.2, 0.3, 0.4],
    })


# --- definition file -------------------------------------------------------


def test_shipped_definition_is_valid_and_has_the_reserved_tab():
    definition = DefaultDashboard.load()
    assert definition["version"] == 1
    assert definition["name"]
    assert definition["tabs"][-1]["id"] == DefaultDashboard.XAPI_TAB_ID
    assert definition["tabs"][-1]["title"] == "xapi data"
    assert any(tab["id"] == "progress_tab" for tab in definition["tabs"])
    for tab in definition["tabs"]:
        assert tab["title"]
        for page in tab.get("pages") or []:
            assert page["title"]
            for graph in page["graphs"]:
                assert graph["id"] and graph["title"]
                assert graph["type"] in GraphTypes.SUPPORTED_TYPES


def test_env_override_is_loaded_and_cached(monkeypatch, tmp_path):
    source = tmp_path / "other-dashboard.json"
    source.write_text(json.dumps(_definition(name="First")), encoding="utf-8")
    monkeypatch.setenv(DefaultDashboard.ENV_VAR, str(source))
    DefaultDashboard.clear_cache()
    try:
        first = DefaultDashboard.load()
        assert first["name"] == "First"
        assert DefaultDashboard.load() is first
        source.write_text(json.dumps(_definition(name="Second")), encoding="utf-8")
        assert DefaultDashboard.load()["name"] == "First"
        DefaultDashboard.clear_cache()
        assert DefaultDashboard.load()["name"] == "Second"
    finally:
        DefaultDashboard.clear_cache()


def test_invalid_definitions_are_rejected_with_a_field_path():
    cases = []
    document = _definition()
    document["tabs"][0]["pages"][0]["graphs"][0]["type"] = "radar"
    cases.append(("unknown graph type", document))

    document = _definition()
    del document["tabs"][0]["pages"][0]["graphs"][0]["y"]
    cases.append(("needs a y definition", document))

    document = _definition()
    document["tabs"][0]["pages"][0]["graphs"][0]["type"] = "pie"
    cases.append(("cannot plot dates", document))

    document = _definition()
    document["version"] = 2
    cases.append(("unsupported dashboard version", document))

    document = _definition()
    document["tabs"].append(copy.deepcopy(document["tabs"][0]))
    cases.append(("duplicate tab id", document))

    document = _definition()
    document["xapi_data_tab"] = {"id": "other", "title": "Answer key"}
    cases.append(("", document))  # reserved id/title are forced, not rejected

    for message, document in cases[:-1]:
        with pytest.raises(DashboardDefinitionError, match=message):
            DefaultDashboard.parse_definition(json.dumps(document), source="test.json")

    forced = DefaultDashboard.parse_definition(json.dumps(cases[-1][1]))
    assert forced["xapi_data_tab"] == {
        "id": "xapi_data", "title": "xapi data", "markdown": ""}


def test_xapi_data_tab_is_always_appended_last():
    document = _definition()
    document.pop("xapi_data_tab", None)
    definition = DefaultDashboard.parse_definition(json.dumps(document))
    assert definition["tabs"][-1] == definition["xapi_data_tab"]
    assert definition["xapi_data_tab"]["markdown"] == ""

    document["xapi_data_tab"] = {"markdown": "Every loaded statement."}
    definition = DefaultDashboard.parse_definition(json.dumps(document))
    assert definition["tabs"][-1]["markdown"] == "Every loaded statement."


# --- labels are data, not translations -------------------------------------


def test_definition_labels_are_used_without_a_translation_lookup(monkeypatch):
    definition = DefaultDashboard.parse_definition(json.dumps(_definition()))
    tab, page = definition["tabs"][0], definition["tabs"][0]["pages"][0]

    def no_translation(*args, **kwargs):
        raise AssertionError("dashboard wording must not go through I18n.t")

    monkeypatch.setattr(I18n, "t", no_translation)
    content = TMonWidget.render_default_page(tab, page, _data(), _data(), {})
    figures = [child.figure for child in _walk(content) if isinstance(child, dcc.Graph)]
    assert len(figures) == 1
    assert figures[0].layout.title.text == TITLE
    assert figures[0].layout.xaxis.title.text == "Time"
    assert figures[0].layout.yaxis.title.text == "Progress"
    strings = [child for child in _walk(content) if isinstance(child, str)]
    assert "Some **markdown**." in strings
    assert "Overview" in strings


def test_a_graph_with_no_title_has_no_generated_title():
    document = _definition()
    document["tabs"][0]["pages"][0]["graphs"][0].pop("title")
    definition = DefaultDashboard.parse_definition(json.dumps(document))
    graph = definition["tabs"][0]["pages"][0]["graphs"][0]
    figure = GraphTypes.render_graph(_data(), graph)
    assert not figure.layout.title.text


def test_renderers_do_not_look_up_translation_keys():
    for module in (GraphTypes, DefaultDashboard):
        source = inspect.getsource(module)
        assert "I18n.t" not in source
        assert "figure.title." not in source
        assert "figure.axis." not in source


# --- graph types -----------------------------------------------------------


def test_registry_knows_what_each_type_needs():
    assert {"bar", "line", "scatter", "pie", "heatmap", "table"} <= set(
        GraphTypes.SUPPORTED_TYPES)
    assert GraphTypes.GRAPH_TYPES["table"].table is True
    assert GraphTypes.GRAPH_TYPES["table"].axes == ()
    assert GraphTypes.supports_date("line") is True
    assert GraphTypes.supports_date("pie") is False
    assert GraphTypes.supports_date("heatmap") is False


def test_heatmap_uses_both_axes_and_table_returns_a_datatable():
    document = _definition()
    document["tabs"][0]["pages"][0]["graphs"] = [
        {"id": "matrix", "title": "Players and activities", "type": "heatmap",
         "x": {"label": "Activity", "data": "object.id"},
         "y": {"label": "Player", "data": "actor.name"}},
        {"id": "rows", "type": "table"},
    ]
    definition = DefaultDashboard.parse_definition(json.dumps(document))
    graphs = definition["tabs"][0]["pages"][0]["graphs"]
    heatmap = GraphTypes.render_graph(_data(), graphs[0])
    assert isinstance(heatmap.data[0].z.tolist(), list)
    assert heatmap.layout.xaxis.title.text == "Activity"
    assert heatmap.layout.yaxis.title.text == "Player"
    assert isinstance(GraphTypes.render_graph(_data(), graphs[1]), dash_table.DataTable)


def test_missing_data_columns_show_the_shared_placeholder():
    graph = _definition()["tabs"][0]["pages"][0]["graphs"][0]
    definition = DefaultDashboard.parse_definition(json.dumps(_definition()))
    graph = definition["tabs"][0]["pages"][0]["graphs"][0]
    figure = GraphTypes.render_graph(pd.DataFrame({"actor.name": ["a"]}), graph)
    assert not figure.data
    assert figure.layout.title.text == TITLE


# --- filters and layout ----------------------------------------------------


def test_general_then_tab_then_page_filters_are_applied_in_order():
    document = _definition()
    document["general_filters"] = [
        {"id": "player", "label": "Player", "column": "actor.name",
         "mode": "single", "values": ["a"]}]
    document["tabs"][0]["general_filters"] = [
        {"id": "verb", "label": "Verb", "column": "verb.id",
         "mode": "single", "values": ["progressed"]}]
    document["tabs"][0]["pages"][0]["filters"] = [
        {"id": "activity", "label": "Activity", "column": "object.id",
         "mode": "single", "values": ["game"]}]
    definition = DefaultDashboard.parse_definition(json.dumps(document))
    specs = DefaultDashboard.filters_for("overview", "main", definition)
    assert [spec["id"] for spec in specs] == ["player", "verb", "activity"]
    filtered = DefaultDashboard.apply_filters(_data(), specs)
    assert len(filtered) == 1
    assert filtered.iloc[0]["timestamp"] == "2026-01-01T00:00:00Z"


def test_selected_values_override_the_definition_without_mutating_it():
    document = _definition()
    document["general_filters"] = [
        {"id": "player", "label": "Player", "column": "actor.name",
         "mode": "multi", "values": ["a"]}]
    definition = DefaultDashboard.parse_definition(json.dumps(document))
    specs = DefaultDashboard.filters_for("overview", "main", definition)
    filtered = DefaultDashboard.apply_filters(_data(), specs, {"player": ["b"]})
    assert list(filtered["actor.name"]) == ["b"]
    assert specs[0]["values"] == ["a"]


def test_page_layout_overrides_tab_and_dashboard_layout():
    document = _definition()
    document["tabs"][0]["layout"] = {"type": "vertical", "rows": 4}
    document["tabs"][0]["pages"][0]["layout"] = {
        "type": "grid", "columns": 4, "rows": 1}
    definition = DefaultDashboard.parse_definition(json.dumps(document))
    tab = definition["tabs"][0]
    page = tab["pages"][0]
    assert DefaultDashboard.layout_for(page["layout"], definition, tab) == {
        "graph-layout": "grid", "graph-rows": 1, "graph-columns": 4,
        "graph-page": 1, "graph-split-x": 2, "graph-split-y": 2}
    inherited = DefaultDashboard.layout_for(None, definition, tab)
    assert inherited["graph-layout"] == "vertical"
    assert inherited["graph-rows"] == 4
    assert DefaultDashboard.layout_for(None, definition, None)[
        "graph-columns"] == 3
    assert DefaultDashboard.layout_for(None, {}, None)["graph-layout"] == "one"


def test_filter_labels_come_from_the_definition():
    document = _definition()
    document["general_filters"] = [
        {"id": "player", "label": "Who played", "column": "actor.name",
         "mode": "multi", "values": []}]
    definition = DefaultDashboard.parse_definition(json.dumps(document))
    specs = DefaultDashboard.filters_for("overview", "main", definition)
    controls = TMonWidget.render_definition_filter_controls(specs, _data())
    strings = [child for child in _walk(controls) if isinstance(child, str)]
    assert "Who played: " in strings
    ids = [getattr(child, "id", None) for child in _walk(controls)]
    assert any(isinstance(identifier, dict)
               and identifier.get("index") == "player" for identifier in ids)


def test_definition_filter_choice_is_saved(monkeypatch):
    class Ctx:
        triggered = [{
            "prop_id": '{"type": "definition-filter", "index": "player"}.value',
            "value": ["a"],
        }]

    monkeypatch.setattr(dash, "callback_context", Ctx())
    assert TMonWidget.update_definition_filter_values([], {"player": []}) == {
        "player": ["a"]}


# --- tab wiring and reserved data tab --------------------------------------


def test_named_pages_are_appended_after_the_definition_tabs():
    pages = [{"id": "mine", "name": "Mine", "charts": [], "filters": []}]
    ids = [tab.value for tab in TMonWidget.dashboard_tab_children(pages)]
    assert ids[-2] == DefaultDashboard.XAPI_TAB_ID
    assert ids[-1] == "page:mine"


def test_legacy_tabs_remain_the_fallback():
    definition = TMonWidget.DASHBOARD_DEFINITION
    TMonWidget.DASHBOARD_DEFINITION = None
    try:
        assert TMonWidget.dashboard_tabs() == TMonWidget.DASHBOARD_TABS
        assert "dashboard-tab-data_tab" in [
            tab.id for tab in TMonWidget.dashboard_tab_children([])]
    finally:
        TMonWidget.DASHBOARD_DEFINITION = definition


def test_xapi_data_tab_shows_every_statement_without_dashboard_filters():
    definition = DefaultDashboard.load()
    content = TMonWidget.render_xapi_data_tab(
        definition["xapi_data_tab"], _data())
    tables = [child for child in _walk(content)
              if isinstance(child, dash_table.DataTable)]
    assert len(tables) == 1
    assert len(tables[0].data) == len(_data())
    strings = [child for child in _walk(content) if isinstance(child, str)]
    assert "All statements loaded for this session." in strings
