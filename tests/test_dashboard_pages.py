"""Tests for named visualisation pages, page filters and configuration files."""
import inspect
import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import pytest
from dash import dcc, html

import TMonWidgets
from TMonWidgets import I18n, TMonWidget
from TMonWidgets.ChartBuilder import (
    COUNT_LABEL, build_chart, decode_specs, describe, encode_spec, normalise_spec,
)
from TMonWidgets.MultiSelector import (
    apply_page_filters, decode_filters, encode_filters, filterable_columns,
    normalise_filter,
)
from TMonWidgets.PageConfig import (
    FORMAT_VERSION, build_document, delete_named, import_config, list_saved,
    load_named, parse_document, save_named, serialize,
)
from TMonWidgets.VisualizationCatalog import (
    GROUPED_VISUALS, VISUALS, build_named_visual, describe_named, game_ids,
)
from test_vis import ACCESSIBLE, ITEM, LEVEL, MENU, QUESTION, notebook_df


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
        "result.extensions.x": ["0.2", "0.6", "0.1", "0.5", "1", "1"],
        "timestamp": pd.date_range("2026-01-01", periods=6, freq="min"),
        "object.definition.name": ["level"] * 6,
    })


def _walk(component):
    yield component
    children = getattr(component, "children", None)
    if isinstance(children, (list, tuple)):
        for child in children:
            yield from _walk(child)
    elif children is not None:
        yield from _walk(children)


# --- named visualisations -------------------------------------------------


def test_every_named_visual_builds_a_figure_from_progress_data():
    df = progress_df()
    assert game_ids(df) == [GAME]
    for identifier in VISUALS:
        figure = build_named_visual(df, {"visual": identifier, "game": GAME})
        assert isinstance(figure, go.Figure)


def test_named_visuals_are_order_independent_and_fall_back_to_a_game():
    df = progress_df()
    # No game named: the first serious game in the data is used.
    figure = build_named_visual(df, {"visual": "progress-line"})
    assert isinstance(figure, go.Figure)
    # A second call with a different named visual must still work.
    assert isinstance(
        build_named_visual(df, {"visual": "progress-origin", "game": GAME}),
        go.Figure,
    )


def test_named_visual_without_a_game_shows_the_placeholder():
    figure = build_named_visual(pd.DataFrame(), {"visual": "progress-line"})
    assert isinstance(figure, go.Figure)


def test_video_visual_is_built_without_a_game():
    df = progress_df()
    assert isinstance(
        build_named_visual(df, {"visual": "video-seen-skipped"}), go.Figure
    )


def test_named_spec_survives_a_link_round_trip():
    spec = normalise_spec({"visual": "progress-pie", "game": GAME})
    encoded = encode_spec(spec)
    assert encoded.startswith("named|")
    decoded = decode_specs(encoded)
    assert len(decoded) == 1
    assert decoded[0]["visual"] == "progress-pie"
    assert decoded[0]["game"] == GAME
    assert "Started and completed" in describe(decoded[0])


def test_named_visual_config_keeps_its_game_without_data():
    spec = normalise_spec({"visual": "progress-line", "game": GAME})
    assert spec["game"] == GAME
    assert describe_named(spec).endswith(GAME)
    assert build_chart(None, spec) is not None


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
        charts=[normalise_spec({"visual": "progress-line", "game": GAME})],
        filters=[normalise_filter({"column": "actor.name", "mode": "single",
                                   "values": ["a"]})],
        pages=[{
            "id": "p1", "name": "My page",
            "charts": [normalise_spec({"type": "bar", "x": "actor.name"})],
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
    assert TMonWidget.page_key("create_tab") == "create_tab"
    assert TMonWidget.page_key("page:abc") == "page:abc"
    pages = [{"id": "abc", "name": "Page", "charts": [1], "filters": [2]}]
    assert TMonWidget.page_by_key(pages, "page:abc") == pages[0]
    assert TMonWidget.items_for_key("page:abc", pages, [9], [8]) == ([1], [2])
    assert TMonWidget.items_for_key("create_tab", pages, [9], [8]) == ([9], [8])


def test_custom_tabs_are_built_from_named_pages():
    tabs = TMonWidget.dashboard_tab_children([
        {"id": "abc", "name": "My page", "charts": [], "filters": []},
    ])
    assert any(getattr(tab, "value", None) == "page:abc" for tab in tabs)
    assert any("My page" in str(tab.label) for tab in tabs)


def test_page_rendering_has_filter_row_charts_and_one_add_slot():
    df = progress_df()
    items = TMonWidget.render_page_items(
        df,
        [normalise_spec({"visual": "video-seen-skipped"})],
        [normalise_filter({"column": "actor.name", "mode": "single"})],
        "page:abc",
    )
    ids = [getattr(child, "id", None) for child in _walk(html.Div(items))]
    assert any(isinstance(i, dict) and i.get("type") == "page-filter" for i in ids)
    assert any(isinstance(i, dict) and i.get("type") == "item-add-slot" for i in ids)
    assert any(isinstance(child, dcc.Graph) for child in _walk(html.Div(items)))


def test_current_config_contains_everything_that_defines_a_page():
    document = TMonWidget.current_config(
        [normalise_spec({"visual": "video-seen-skipped"})],
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
    assert parsed["create_tab"]["charts"][0]["visual"] == "video-seen-skipped"
    assert parsed["create_tab"]["filters"][0]["column"] == "actor.name"
    assert parsed["layout"]["graph-layout"] == "one"
    assert parsed["header"]["actor.name"] == ["a"]
    assert parsed["hidden_activities"] == ["hidden"]


def test_page_state_loads_charts_and_filters_from_a_link(monkeypatch):
    import dash

    class Ctx:
        triggered = [{'prop_id': 'output-t-mon.style'}]

    monkeypatch.setattr(dash, 'callback_context', Ctx())
    spec = normalise_spec({'visual': 'video-seen-skipped'})
    filter_spec = normalise_filter({'column': 'actor.name', 'mode': 'single',
                                    'values': ['a']})
    pathname = 'tab=create_tab&chart=' + encode_spec(spec) + '&filter=' + encode_filters(
        [filter_spec])
    pages, charts, filters, _, _ = TMonWidget.update_page_state(
        None, None, None, None, None, None, None, None,
        {'display': 'block'}, None, 'create_tab', None, None,
        None, None, None, None, None, None, None, None, None, None,
        [], [], [], pathname)
    assert pages == []
    assert charts == [spec]
    assert filters == [filter_spec]


def test_page_state_replaces_and_appends_imported_pages(monkeypatch):
    import dash

    existing = [{'id': 'one', 'name': 'First', 'charts': [], 'filters': []}]
    imported = [{
        'id': 'one', 'name': 'Imported',
        'charts': [normalise_spec({'visual': 'video-seen-skipped'})],
        'filters': [normalise_filter({'column': 'actor.name', 'mode': 'single'})],
    }]
    document = build_document(pages=imported)

    class Ctx:
        triggered = [{'prop_id': 'config-command.data'}]

    monkeypatch.setattr(dash, 'callback_context', Ctx())
    result = TMonWidget.update_page_state(
        None, None, None, None, None, None, None, None,
        {'display': 'block'}, {'action': 'replace', 'config': document},
        'create_tab', None, None, None, None, None, None,
        None, None, None, None, None, None, existing, [], [], None)
    assert [page['id'] for page in result[0]] == ['one']

    result = TMonWidget.update_page_state(
        None, None, None, None, None, None, None, None,
        {'display': 'block'}, {'action': 'append', 'config': document},
        'create_tab', None, None, None, None, None, None,
        None, None, None, None, None, None, existing, [], [], None)
    assert len(result[0]) == 2
    assert result[0][0]['id'] != result[0][1]['id']


def test_dashboard_layout_exposes_page_and_config_controls():
    ids = [getattr(child, "id", None) for child in _walk(TMonWidget.TMonBody)]
    for expected in (
        "dashboard-pages", "page-filters", "page-name-input", "page-add",
        "page-rename", "item-modal", "item-kind", "item-game", "item-column",
        "item-add", "item-cancel", "config-name-input", "config-save",
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


# --- ADR 0016: full notebook catalogue -------------------------------------


EXPECTED_VISUAL_IDS = {
    "progress-line", "progress-origin", "progress-pie", "video-seen-skipped",
    "completable-progress-change", "completable-progress", "completable-scores",
    "completable-times", "correct-incorrect-by-player",
    "correct-incorrect-by-question", "alternatives-selected",
    "item-interaction-time", "item-interaction-heatmap", "item-interaction-count",
    "item-action-type-count", "accessible-time", "accessible-heatmap",
    "accessible-count", "menu-selection-count",
}


def test_catalogue_covers_every_notebook_visual_once():
    assert set(VISUALS) == EXPECTED_VISUAL_IDS
    assert len(VISUALS) == 19
    grouped = [identifier for _, identifiers in GROUPED_VISUALS
               for identifier in identifiers]
    assert len(grouped) == len(set(grouped)) == len(VISUALS)
    assert set(grouped) == set(VISUALS)
    group_keys = [key for key, _ in GROUPED_VISUALS]
    assert group_keys[:2] == ["visual.group.progress", "visual.group.videos"]
    assert set(group_keys[2:]) == {
        "visual.group.completables", "visual.group.alternatives",
        "visual.group.interactions", "visual.group.accessibles",
        "visual.group.menus",
    }


def test_popup_offers_every_catalogue_visual():
    values = []
    for group in TMonWidget.visual_kind_options():
        values.extend(option["value"] for option in group["options"])
    catalogue_values = [value for value in values if value in VISUALS]
    assert len(catalogue_values) == len(VISUALS)
    assert set(catalogue_values) == set(VISUALS)


def test_builtin_tabs_map_to_the_whole_catalogue_without_placeholders():
    expected = {
        "progress_tab": {"progress-line", "progress-origin", "progress-pie"},
        "video_tab": {"video-seen-skipped"},
        "completable_tab": {"completable-progress-change", "completable-progress",
                            "completable-scores", "completable-times"},
        "alternative_tab": {"correct-incorrect-by-player",
                            "correct-incorrect-by-question", "alternatives-selected"},
        "interaction_tab": {"item-interaction-time", "item-interaction-heatmap",
                            "item-interaction-count", "item-action-type-count"},
        "accessible_tab": {"accessible-time", "accessible-heatmap",
                           "accessible-count"},
        "menu_tab": {"menu-selection-count"},
    }
    mapping = TMonWidget.BUILTIN_TAB_VISUALS
    assert set(mapping) == set(expected)
    for tab, visuals in expected.items():
        assert set(mapping[tab]["visuals"]) == visuals
    builtin = {visual for item in mapping.values() for visual in item["visuals"]}
    assert builtin == set(VISUALS)
    source = inspect.getsource(TMonWidget)
    for number in range(3, 8):
        assert f"Tab content {number}" not in source


def test_builtin_tabs_render_catalogue_figures_with_unique_ids():
    df = notebook_df()
    for tab in TMonWidget.BUILTIN_TAB_VISUALS:
        content = TMonWidget.render_builtin_tab(df, tab)
        graphs = [child for child in _walk(content) if isinstance(child, dcc.Graph)]
        assert graphs, tab
        assert all(str(graph.id).startswith("builtin-") for graph in graphs)
        ids = [graph.id for graph in graphs]
        assert len(ids) == len(set(ids))
        assert any(graph.figure.data for graph in graphs), tab
        for graph in graphs:
            for trace in graph.figure.data:
                values = getattr(trace, "y", None)
                if values is not None:
                    assert list(values) != [5, 10, 6]


def test_builtin_tabs_show_no_data_instead_of_fabricated_charts():
    for tab in ("completable_tab", "alternative_tab", "interaction_tab",
                "accessible_tab", "menu_tab"):
        content = TMonWidget.render_builtin_tab(pd.DataFrame(), tab)
        texts = [child for child in _walk(content) if isinstance(child, str)]
        assert I18n.t("figure.no-data") in texts, tab
        graphs = [child for child in _walk(content) if isinstance(child, dcc.Graph)]
        assert graphs and all(not graph.figure.data for graph in graphs)


def test_builtin_tabs_cap_the_number_of_figures():
    rows = []
    for index in range(6):
        identifier = f"game-{index}"
        for verb in ("initialized", "completed"):
            rows.append({
                "actor.name": "p1",
                "verb.id": f"http://adlnet.gov/expapi/verbs/{verb}",
                "object.id": identifier,
                "object.definition.type": SERIOUS,
                "timestamp": f"2026-01-01T00:{index:02d}:00Z",
            })
    df = pd.DataFrame(rows)
    content = TMonWidget.render_builtin_tab(df, "progress_tab")
    graphs = [child for child in _walk(content) if isinstance(child, dcc.Graph)]
    assert len(graphs) == TMonWidget.MAX_BUILTIN_FIGURES


def test_target_and_mode_survive_a_link_and_a_config_document():
    df = notebook_df()
    spec = normalise_spec({
        "visual": "completable-progress-change",
        "target": LEVEL,
        "mode": "relative",
    }, df)
    assert spec["target"] == LEVEL
    encoded = encode_spec(spec)
    assert encoded == f"named|completable-progress-change|-|{LEVEL}|relative|count"
    decoded = decode_specs(encoded)[0]
    assert decoded["target"] == LEVEL
    assert decoded["mode"] == "relative"
    assert normalise_spec(decoded, df) == spec
    document = parse_document(serialize(build_document(charts=[spec])))
    assert document["create_tab"]["charts"][0] == spec


def test_old_named_links_and_generic_links_still_decode():
    old_four = decode_specs(f"named|progress-pie|{GAME}|-")[0]
    old_six = decode_specs(f"named|progress-pie|{GAME}|-|-|count")[0]
    for spec in (old_four, old_six):
        assert spec["visual"] == "progress-pie"
        assert spec["game"] == GAME
        assert spec["target"] == ""
        assert spec["mode"] == ""
    assert decode_specs("bar|actor.name|-|count") == [{
        "type": "bar", "x": "actor.name", "y": COUNT_LABEL,
        "aggregation": "count",
    }]


def test_short_legacy_target_resolves_to_the_full_id():
    spec = normalise_spec({
        "visual": "correct-incorrect-by-player", "target": "question-1",
    }, notebook_df())
    assert spec["target"] == QUESTION


def test_popup_shows_targets_and_modes_for_notebook_figures(monkeypatch):
    monkeypatch.setattr(TMonWidgets, "xapiData", notebook_df().to_dict("records"))
    result = TMonWidget.update_item_modal_fields(
        "completable-progress-change", 1, {"display": "block"})
    games, columns, targets, target_value, modes, mode_value, game_style, \
        column_style, target_style, mode_style = result
    assert any(option["value"] == LEVEL for option in targets)
    assert target_value == LEVEL
    assert [option["value"] for option in modes] == ["absolute", "relative"]
    assert mode_value == "absolute"
    assert target_style == {"display": "block"}
    assert mode_style == {"display": "block"}
    assert game_style == {"display": "none"}
    assert column_style == {"display": "none"}

    progress = TMonWidget.update_item_modal_fields(
        "progress-line", 1, {"display": "block"})
    assert progress[6] == {"display": "block"}
    assert progress[8] == {"display": "none"}
    assert progress[9] == {"display": "none"}

    generic = TMonWidget.update_item_modal_fields(
        "bar", 1, {"display": "block"})
    assert generic[7] == {"display": "block"}
    assert generic[8] == {"display": "none"}
    assert generic[9] == {"display": "none"}


def test_page_state_writes_target_and_mode_to_the_chart_store(monkeypatch):
    import dash

    class Ctx:
        triggered = [{"prop_id": "item-add.n_clicks"}]

    monkeypatch.setattr(dash, "callback_context", Ctx())
    result = TMonWidget.update_page_state(
        page_add_n=None, page_rename_n=None, page_delete_n=None, item_add_n=1,
        item_remove_n=None, filter_values=None, chart_add_n=None,
        chart_remove_n=None, panel_style=None, config_command=None,
        tab="create_tab", target="create_tab", page_name=None,
        item_kind="completable-progress-change", item_chart_type=None,
        item_column=None, item_game=None, item_target=LEVEL, item_mode="relative",
        chart_type=None, chart_x=None, chart_y=None, chart_aggregation=None,
        pages=[], charts=[], filters=[], pathname=None,
    )
    charts = result[1]
    assert len(charts) == 1
    assert charts[0]["visual"] == "completable-progress-change"
    assert charts[0]["target"] == LEVEL
    assert charts[0]["mode"] == "relative"


def test_notebook_labels_exist_in_every_language():
    locales = Path(I18n.__file__).parent.parent / "locales"
    english = json.loads((locales / "en.json").read_text(encoding="utf-8"))
    keys = [entry.label_key for entry in VISUALS.values()]
    keys += [key for key, _ in GROUPED_VISUALS]
    keys += [
        "visual.group.generic", "visual.group.filters", "visual.target",
        "visual.option", "visual.mode.absolute", "visual.mode.relative",
    ]
    keys += [key for key in english if key.startswith("figure.")]
    for language in ("en", "es", "fr"):
        translations = json.loads(
            (locales / f"{language}.json").read_text(encoding="utf-8"))
        for key in keys:
            assert translations.get(key), (language, key)
