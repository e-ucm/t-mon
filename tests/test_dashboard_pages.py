"""Tests for user pages, page filters and configuration documents."""
import json
from pathlib import Path

import pandas as pd
import pytest
from dash import dcc, html

from TMonWidgets import I18n, TMonWidget
from TMonWidgets.ChartBuilder import (
    COUNT_LABEL, CHART_TYPES, decode_specs, encode_spec, normalise_spec,
)
from TMonWidgets.MultiSelector import (
    apply_page_filters, decode_filters, encode_filters, filterable_columns,
    normalise_filter,
)
from TMonWidgets.PageConfig import (
    FORMAT_VERSION, build_document, delete_named, import_config, list_saved,
    load_named, parse_document, save_named, serialize,
)


GAME = "https://w3id.org/xapi/seriousgames/activities/game-1"
SERIOUS = "https://w3id.org/xapi/seriousgames/activity-types/serious-game"


def progress_df():
    return pd.DataFrame({
        "actor.name": ["a", "a", "b", "b", "a", "b"],
        "object.id": [GAME] * 6,
        "object.definition.type": [SERIOUS] * 6,
        "verb.id": [
            "http://adlnet.gov/expapi/verbs/initialized",
            "http://adlnet.gov/expapi/verbs/progressed",
            "http://adlnet.gov/expapi/verbs/initialized",
            "http://adlnet.gov/expapi/verbs/progressed",
            "http://adlnet.gov/expapi/verbs/completed",
            "http://adlnet.gov/expapi/verbs/completed",
        ],
        "result.response": ["0.2", "0.6", "0.1", "0.5", "1", "1"],
        "timestamp": pd.date_range("2026-01-01", periods=6, freq="min"),
        "object.definition.name": ["level"] * 6,
    })


def generic_spec():
    return normalise_spec({"type": "bar", "x": "actor.name"})


def _walk(component):
    yield component
    children = getattr(component, "children", None)
    if isinstance(children, (list, tuple)):
        for child in children:
            yield from _walk(child)
    elif children is not None:
        yield from _walk(children)


# --- generic chart descriptions -------------------------------------------


def test_generic_chart_survives_a_link_round_trip():
    spec = generic_spec()
    assert encode_spec(spec) == f"bar|actor.name|-|count"
    assert decode_specs(encode_spec(spec)) == [spec]


def test_old_named_links_are_read_as_ordinary_charts():
    # A first field that is not a chart type falls back to a bar, so a stale
    # link from the removed named-visual catalogue cannot break a shared URL.
    decoded = decode_specs("named|progress-pie|-|-|-|count")
    assert len(decoded) == 1
    assert normalise_spec(decoded[0], progress_df())["type"] == "bar"


def test_pie_needs_no_measured_value():
    spec = normalise_spec({"type": "pie", "x": "actor.name"}, progress_df())
    assert spec["y"] == COUNT_LABEL


# --- page filters ---------------------------------------------------------


def test_page_filters_encode_and_decode_with_selected_values():
    filters = [
        normalise_filter({"column": "actor.name", "mode": "multi",
                          "values": ["a", "b"]}),
        normalise_filter({"column": "object.id", "mode": "single",
                          "values": [GAME]}),
    ]
    encoded = encode_filters(filters)
    decoded = decode_filters(encoded)
    assert decoded == filters


def test_page_filters_narrow_every_chart_source():
    df = progress_df()
    filtered = apply_page_filters(df, [
        {"column": "actor.name", "mode": "single", "values": ["a"]},
    ])
    assert set(filtered["actor.name"]) == {"a"}
    assert "actor.name" in filterable_columns(df)


def test_invalid_filter_is_dropped():
    assert normalise_filter({"mode": "single", "values": ["a"]}) is None
    assert decode_filters("not-a-filter") == []


# --- configuration documents ---------------------------------------------


def test_config_round_trip_preserves_pages_charts_filters_and_layout(monkeypatch, tmp_path):
    monkeypatch.setenv("TMON_CONFIG_DIR", str(tmp_path))
    document = build_document(
        charts=[generic_spec()],
        filters=[normalise_filter({"column": "actor.name", "mode": "single",
                                   "values": ["a"]})],
        pages=[{
            "id": "p1", "name": "My page",
            "charts": [generic_spec()],
            "filters": [],
        }],
        layout={"graph-layout": "grid", "graph-rows": 2},
        header={"actor.name": ["a"]},
        hidden=["hidden-activity"],
        active_tab="page:p1",
    )
    text = serialize(document)
    parsed = parse_document(text)
    assert parsed == document
    assert parsed["version"] == FORMAT_VERSION

    assert save_named("example", document) == "example"
    assert list_saved() == ["example"]
    assert load_named("example") == document
    assert delete_named("example") is True
    assert list_saved() == []


def test_config_upload_accepts_a_data_uri():
    document = build_document()
    contents = "data:application/json;base64," + __import__("base64").b64encode(
        serialize(document).encode("utf-8")
    ).decode("ascii")
    assert import_config(contents) == document


def test_config_rejects_unknown_versions_and_bad_names():
    with pytest.raises(ValueError):
        parse_document(json.dumps({"version": FORMAT_VERSION + 1}))
    with pytest.raises(ValueError):
        parse_document("not json")
    with pytest.raises(ValueError):
        save_named("../escape", build_document())


def test_config_endpoints(monkeypatch, tmp_path):
    monkeypatch.setenv("TMON_CONFIG_DIR", str(tmp_path))
    import TMonSimvaApp

    client = TMonSimvaApp.app.server.test_client()
    document = build_document()
    assert client.post("/api/tmon/configs/example", json=document).status_code == 200
    assert client.get("/api/tmon/configs").get_json() == {"names": ["example"]}
    assert client.get("/api/tmon/configs/example").get_json() == document
    assert client.get("/api/tmon/configs/missing").status_code == 404
    assert client.delete("/api/tmon/configs/example").get_json() == {"deleted": True}


# --- dashboard widgets ----------------------------------------------------


def test_new_page_keys_and_lookups():
    assert TMonWidget.page_key("create_tab") is None
    assert TMonWidget.page_key("page:abc") == "page:abc"
    pages = [{"id": "abc", "name": "Page", "charts": [1], "filters": [2]}]
    assert TMonWidget.page_by_key(pages, "page:abc") == pages[0]
    assert TMonWidget.items_for_key("page:abc", pages, [9], [8]) == ([1], [2])
    assert TMonWidget.items_for_key(None, pages, [9], [8]) == ([9], [8])


def test_custom_tabs_are_built_from_named_pages():
    tabs = TMonWidget.dashboard_tab_children([
        {"id": "abc", "name": "My page", "charts": [], "filters": []},
    ])
    assert any(getattr(tab, "value", None) == "page:abc" for tab in tabs)
    assert any("My page" in str(tab.label) for tab in tabs)


def test_page_rendering_has_filter_row_charts_and_one_add_slot():
    items = TMonWidget.render_page_items(
        progress_df(),
        [generic_spec()],
        [normalise_filter({"column": "actor.name", "mode": "single"})],
        "page:abc",
    )
    ids = [getattr(child, "id", None) for child in _walk(html.Div(items))]
    assert any(isinstance(i, dict) and i.get("type") == "item-add-slot" for i in ids)
    assert any(isinstance(child, dcc.Graph) for child in _walk(html.Div(items)))


def test_current_config_contains_everything_that_defines_a_page():
    document = TMonWidget.current_config(
        [generic_spec()],
        [normalise_filter({"column": "actor.name", "mode": "single"})],
        [{"id": "abc", "name": "My page", "charts": [], "filters": []}],
        {"graph-layout": "one"},
        {"actor.name": ["a"]},
        ["hidden"],
        "page:abc",
    )
    parsed = parse_document(serialize(document))
    assert parsed["active_tab"] == "page:abc"
    assert parsed["tabs"]["custom"][0]["name"] == "My page"
    assert parsed["charts"][0]["type"] == "bar"
    assert parsed["charts"][0]["x"] == "actor.name"
    assert parsed["filters"][0]["column"] == "actor.name"
    assert parsed["layout"]["graph-layout"] == "one"
    assert parsed["header"]["actor.name"] == ["a"]
    assert parsed["hidden_activities"] == ["hidden"]


def test_page_state_loads_charts_and_filters_from_a_link(monkeypatch):
    import dash

    class Ctx:
        triggered = [{'prop_id': 'output-t-mon.style'}]

    monkeypatch.setattr(dash, 'callback_context', Ctx())
    spec = generic_spec()
    filter_spec = normalise_filter({'column': 'actor.name', 'mode': 'single',
                                    'values': ['a']})
    pathname = 'tab=create_tab&chart=' + encode_spec(spec) + '&filter=' + encode_filters(
        [filter_spec])
    pages, charts, filters, _ = TMonWidget.update_page_state(
        None, None, None, None, None, None,
        {'display': 'block'}, None, None, None, None,
        'create_tab', None, None, None,
        None, None, None, None, None, None,
        [], [], [], pathname)
    assert pages == []
    assert charts == [spec]
    assert filters == [filter_spec]


def test_page_state_replaces_and_appends_imported_pages(monkeypatch):
    import dash

    existing = [{'id': 'one', 'name': 'First', 'charts': [], 'filters': []}]
    imported = [{
        'id': 'one', 'name': 'Imported',
        'charts': [generic_spec()],
        'filters': [normalise_filter({'column': 'actor.name', 'mode': 'single'})],
    }]
    document = build_document(pages=imported)

    class Ctx:
        triggered = [{'prop_id': 'config-command.data'}]

    monkeypatch.setattr(dash, 'callback_context', Ctx())
    result = TMonWidget.update_page_state(
        None, None, None, None, None, None,
        {'display': 'block'}, {'action': 'replace', 'config': document},
        None, None, None,
        'create_tab', None, None, None, None, None, None, None, None, None,
        existing, [], [], None)
    assert [page['id'] for page in result[0]] == ['one']

    result = TMonWidget.update_page_state(
        None, None, None, None, None, None,
        {'display': 'block'}, {'action': 'append', 'config': document},
        None, None, None,
        'create_tab', None, None, None, None, None, None, None, None, None,
        existing, [], [], None)
    assert len(result[0]) == 2
    assert result[0][0]['id'] != result[0][1]['id']


def test_dashboard_layout_exposes_page_and_config_controls():
    ids = [getattr(child, "id", None) for child in _walk(TMonWidget.TMonBody)]
    for expected in (
        "dashboard-pages", "page-filters", "page-name-input", "page-add",
        "page-rename", "edit-floater", "edit-floater-mode",
        "edit-floater-create", "edit-floater-pages", "edit-floater-layout-section",
        "edit-floater-config",
        "item-kind", "item-column",
        "item-add", "item-cancel", "edit-floater-close",
        "graph-layout", "graph-rows", "graph-columns", "graph-page",
        "graph-split-x", "graph-split-y",
        "config-name-input", "config-save",
        "config-load", "config-delete", "config-export", "config-import",
        "config-confirm-modal", "config-confirm-replace", "config-confirm-append",
        "config-confirm-cancel", "config-download", "config-command",
    ):
        assert expected in ids or any(
            isinstance(i, dict) and i.get("index") == expected for i in ids
        ), expected


# --- translations ---------------------------------------------------------


def test_new_labels_exist_in_every_language():
    keys = [
        "visual.open", "visual.add", "visual.game", "visual.mode.single",
        "page.add", "page.rename", "page.delete", "config.export",
        "config.import", "config.save", "config.load", "config.confirm",
        "config.replace", "config.append",
    ]
    for language in ("en", "es", "fr"):
        for key in keys:
            assert I18n.translate(key, language) != key


def test_popup_offers_only_generic_charts_and_filters():
    values = []
    for group in TMonWidget.visual_kind_options():
        values.extend(option["value"] for option in group["options"])
    assert set(values) == set(CHART_TYPES) | {'filter-multi', 'filter-single'}


def test_notebook_labels_exist_in_every_language():
    locales = Path(I18n.__file__).parent.parent / "locales"
    english = json.loads((locales / "en.json").read_text(encoding="utf-8"))
    keys = [
        "visual.group.generic", "visual.group.filters", "visual.target",
        "visual.option", "visual.mode.absolute", "visual.mode.relative",
    ]
    keys += [key for key in english if key.startswith("figure.")]
    for language in ("en", "es", "fr"):
        translations = json.loads(
            (locales / f"{language}.json").read_text(encoding="utf-8"))
        for key in keys:
            assert translations.get(key), (language, key)
