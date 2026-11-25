"""
Load and validate the deployment's default dashboard definition.

The definition is data: it owns tab and page titles, Markdown, filter labels,
graph titles and axis wording. Runtime configurations (ADR 0015) still record
what a user has done; this document says what the dashboard is when it starts.
A parsed definition is cached because it is deployment state, not request state.
"""
import json
import os
from functools import lru_cache
from pathlib import Path

from TMonWidgets.GraphTypes import AGGREGATIONS, GRAPH_TYPES, SUPPORTED_TYPES, supports_date
from TMonWidgets.MultiSelector import FILTER_MODES

FORMAT_VERSION = 1
ENV_VAR = "TMON_DEFAULT_DASHBOARD"
DEFAULT_PATH = Path(__file__).resolve().parent.parent / "config" / "default-dashboard.json"

XAPI_TAB_ID = "xapi_data"
XAPI_TAB_TITLE = "xapi data"

LAYOUT_TYPES = ("one", "vertical", "horizontal", "grid", "split")
LAYOUT_KEYS = ("type", "rows", "columns", "page", "split-x", "split-y")
LAYOUT_DEFAULTS = {
    "type": "one", "rows": 3, "columns": 2, "page": 1,
    "split-x": 2, "split-y": 2,
}

# The graph layout controls the dashboard already uses. A definition speaks in
# these names so a page can override the dashboard-wide arrangement directly.
CONTROL_KEYS = {
    "type": "graph-layout",
    "rows": "graph-rows",
    "columns": "graph-columns",
    "page": "graph-page",
    "split-x": "graph-split-x",
    "split-y": "graph-split-y",
}


class DashboardDefinitionError(ValueError):
    """A default dashboard file cannot be used as supplied."""


def _fail(path, where, message):
    raise DashboardDefinitionError(f"{path}: {where}: {message}")


def _string(value, where, path, required=True):
    if value is None and not required:
        return ""
    if not isinstance(value, str) or (required and not value.strip()):
        _fail(path, where, "expected a non-empty string")
    return value


def _list(value, where, path, required=True):
    if value is None and not required:
        return []
    if not isinstance(value, list) or (required and not value):
        _fail(path, where, "expected a non-empty list")
    return value


def _layout(value, where, path):
    """Validate an arrangement, allowing the file to leave pieces out."""
    if value is None:
        return {}
    if not isinstance(value, dict):
        _fail(path, where, "layout must be an object")
    cleaned = {}
    for key, raw in value.items():
        if key not in LAYOUT_KEYS:
            _fail(path, where, f"unknown layout field {key!r}")
        if key == "type":
            if raw not in LAYOUT_TYPES:
                _fail(path, where, f"unknown layout type {raw!r}")
            cleaned[key] = raw
            continue
        minimum = 0 if key.startswith("split-") else 1
        if isinstance(raw, bool) or not isinstance(raw, int) or raw < minimum:
            _fail(path, where, f"{key} must be an integer of at least {minimum}")
        cleaned[key] = raw
    return cleaned


def _filter(value, where, path, is_tab_filter=False):
    if not isinstance(value, dict):
        _fail(path, where, "filter must be an object")
    identifier = _string(value.get("id"), f"{where}.id", path)
    label = _string(value.get("label"), f"{where}.label", path)
    column = _string(value.get("column"), f"{where}.column", path)
    mode = value.get("mode", "multi")
    if mode not in FILTER_MODES:
        _fail(path, where, f"unknown filter mode {mode!r}")
    raw_values = value.get("values") or []
    if isinstance(raw_values, str):
        raw_values = [raw_values]
    if not isinstance(raw_values, (list, tuple)):
        _fail(path, where, "filter values must be a list")
    values = [str(item) for item in raw_values if item is not None and item != ""]
    if mode == "single":
        values = values[:1]
    result = {
        "id": identifier,
        "label": label,
        "column": column,
        "mode": mode,
        "values": values,
    }
    # For tab filters, also store the filter mode selection type
    if is_tab_filter:
        result["filter_mode_selection"] = value.get("filter_mode_selection", "single")
    return result


def _filters(value, where, path):
    return [_filter(spec, f"{where}[{index}]", path)
            for index, spec in enumerate(_list(value, where, path, required=False))]


def _graph(value, where, path):
    if not isinstance(value, dict):
        _fail(path, where, "graph must be an object")
    identifier = _string(value.get("id"), f"{where}.id", path)
    graph_type = value.get("type")
    if graph_type not in SUPPORTED_TYPES:
        _fail(path, where, f"unknown graph type {graph_type!r}")
    title = _string(value.get("title"), f"{where}.title", path, required=False)

    def axis(name):
        definition = value.get(name)
        if not isinstance(definition, dict):
            _fail(path, where, f"{name} must be an object with label and data")
        label = _string(definition.get("label"), f"{where}.{name}.label", path,
                        required=False)
        data = _string(definition.get("data"), f"{where}.{name}.data", path)
        result = {"label": label, "data": data}
        if name == "x":
            date = definition.get("date", False)
            if not isinstance(date, bool):
                _fail(path, where, "x.date must be true or false")
            result["date"] = date
        return result

    x = axis("x") if "x" in value else None
    y = axis("y") if "y" in value else None
    for needed in GRAPH_TYPES[graph_type].axes:
        if (x if needed == "x" else y) is None:
            _fail(path, where, f"a {graph_type} graph needs a {needed} definition")
    if x and x["date"] and not supports_date(graph_type):
        _fail(path, where, f"graph type {graph_type!r} cannot plot dates")
    aggregation = value.get("aggregation") or (
        "count" if y and y["data"] == "count" else "mean")
    if aggregation not in AGGREGATIONS:
        _fail(path, where, f"unknown aggregation {aggregation!r}")
    return {
        "id": identifier,
        "title": title,
        "type": graph_type,
        "x": x,
        "y": y,
        "aggregation": aggregation,
    }


def _page(value, where, path, seen_ids):
    if not isinstance(value, dict):
        _fail(path, where, "page must be an object")
    identifier = _string(value.get("id"), f"{where}.id", path)
    if identifier in seen_ids:
        _fail(path, where, f"duplicate page id {identifier!r}")
    seen_ids.add(identifier)
    graphs = []
    for index, spec in enumerate(_list(value.get("graphs"), f"{where}.graphs", path,
                                       required=False)):
        graph = _graph(spec, f"{where}.graphs[{index}]", path)
        graphs.append(graph)
    graph_ids = [graph["id"] for graph in graphs]
    if len(graph_ids) != len(set(graph_ids)):
        _fail(path, where, "graph ids must be unique within a page")
    return {
        "id": identifier,
        "title": _string(value.get("title"), f"{where}.title", path),
        "markdown": _string(value.get("markdown"), f"{where}.markdown", path,
                            required=False),
        "layout": _layout(value.get("layout"), f"{where}.layout", path),
        "filters": _filters(value.get("filters"), f"{where}.filters", path),
        "graphs": graphs,
    }


def _tab(value, where, path, seen_ids, seen_filter_ids, is_root_tab=False):
    if not isinstance(value, dict):
        _fail(path, where, "tab must be an object")
    identifier = _string(value.get("id"), f"{where}.id", path)
    if identifier == XAPI_TAB_ID:
        _fail(path, where, f"{XAPI_TAB_ID!r} is reserved for the data tab")
    if identifier in seen_ids:
        _fail(path, where, f"duplicate tab id {identifier!r}")
    seen_ids.add(identifier)
    general = _filters(value.get("general_filters"), f"{where}.general_filters", path)
    for spec in general:
        if spec["id"] in seen_filter_ids:
            _fail(path, where, f"duplicate filter id {spec['id']!r}")
        seen_filter_ids.add(spec["id"])
    # Parse per-tab filter configuration (ADR 0026)
    tab_filter_config = value.get("tab_filter_config")
    if tab_filter_config is not None:
        if not isinstance(tab_filter_config, dict):
            _fail(path, where, "tab_filter_config must be an object")
        # Validate filter_mode_selection
        filter_mode_selection = tab_filter_config.get("filter_mode_selection", "single")
        if filter_mode_selection not in FILTER_MODES:
            _fail(path, where, f"unknown filter_mode_selection {filter_mode_selection!r}")
        # Validate and parse individual tab filters
        tab_filters_raw = tab_filter_config.get("filters") or []
        tab_filters = []
        for index, spec in enumerate(_list(tab_filters_raw, f"{where}.tab_filter_config.filters", path, required=False)):
            parsed = _filter(spec, f"{where}.tab_filter_config.filters[{index}]", path, is_tab_filter=True)
            # Check for duplicate filter ids within this tab
            if parsed["id"] in seen_filter_ids:
                _fail(path, where, f"duplicate filter id {parsed['id']!r} within tab")
            seen_filter_ids.add(parsed["id"])
            tab_filters.append(parsed)
    else:
        tab_filters = []
    page_ids = set()
    pages = [_page(page, f"{where}.pages[{index}]", path, page_ids)
             for index, page in enumerate(_list(value.get("pages"),
                                                f"{where}.pages", path))]
    for page in pages:
        for spec in page["filters"]:
            if spec["id"] in seen_filter_ids:
                _fail(path, where, f"duplicate filter id {spec['id']!r}")
            seen_filter_ids.add(spec["id"])
    return {
        "id": identifier,
        "title": _string(value.get("title"), f"{where}.title", path),
        "markdown": _string(value.get("markdown"), f"{where}.markdown", path,
                            required=False),
        "layout": _layout(value.get("layout"), f"{where}.layout", path),
        "general_filters": general,
        "pages": pages,
        "tab_filter_config": {
            "filter_mode_selection": tab_filter_config.get("filter_mode_selection", "single") if tab_filter_config else "single",
            "filters": tab_filters,
        } if tab_filter_config else {"filter_mode_selection": "single", "filters": []},
    }


def parse_definition(text, source="<definition>"):
    """
    Validate dashboard definition JSON, returning a normalised document.

    Raises:
        DashboardDefinitionError: with the path of the first invalid field.
    """
    try:
        raw = json.loads(text)
    except (TypeError, ValueError) as error:
        raise DashboardDefinitionError(f"{source}: the file is not valid JSON") from error
    if not isinstance(raw, dict):
        raise DashboardDefinitionError(f"{source}: the definition must be a JSON object")
    if raw.get("version") != FORMAT_VERSION:
        raise DashboardDefinitionError(
            f"{source}: unsupported dashboard version {raw.get('version')!r}")
    _string(raw.get("name"), "name", source)
    general = _filters(raw.get("general_filters"), "general_filters", source)
    seen_filter_ids = {spec["id"] for spec in general}
    seen_tab_ids = set()
    # Parse per-tab filter configurations (ADR 0026)
    tabs = [_tab(tab, f"tabs[{index}]", source, seen_tab_ids, seen_filter_ids)
            for index, tab in enumerate(_list(raw.get("tabs"), "tabs", source))]

    data = raw.get("xapi_data_tab") or {}
    if not isinstance(data, dict):
        raise DashboardDefinitionError(f"{source}: xapi_data_tab must be an object")
    # The id and label are fixed by the ADR; only Markdown may be supplied.
    data_tab = {
        "id": XAPI_TAB_ID,
        "title": XAPI_TAB_TITLE,
        "markdown": _string(data.get("markdown"), "xapi_data_tab.markdown",
                            source, required=False),
    }
    return {
        "version": FORMAT_VERSION,
        "name": raw["name"],
        "layout": _layout(raw.get("layout"), "layout", source),
        "general_filters": general,
        "tabs": tabs + [data_tab],
        "xapi_data_tab": data_tab,
    }


def _resolved_path(path=None):
    candidate = path or os.environ.get(ENV_VAR) or str(DEFAULT_PATH)
    return str(Path(candidate).expanduser())


@lru_cache(maxsize=8)
def _load_cached(path):
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as error:
        raise DashboardDefinitionError(
            f"Cannot read default dashboard {path}: {error}") from error
    return parse_definition(text, source=path)


def load(path=None):
    """Load, validate and cache the default dashboard definition."""
    return _load_cached(_resolved_path(path))


def clear_cache():
    """Forget cached definitions, for tests or a deployment file replaced at run time."""
    _load_cached.cache_clear()


def find_tab(tab_id, dashboard=None):
    """Return ``(tab, page)`` for a tab id, accepting the legacy ``data_tab``."""
    dashboard = dashboard if dashboard is not None else load()
    identifier = XAPI_TAB_ID if tab_id == "data_tab" else tab_id
    for tab in dashboard.get("tabs") or []:
        if tab.get("id") == identifier:
            pages = tab.get("pages") or []
            return tab, pages[0] if pages else None
    return None, None


def filters_for(tab_id, page_id=None, dashboard=None):
    """Filters that apply before a graph, in dashboard, tab then page order (ADR 0026)."""
    dashboard = dashboard if dashboard is not None else load()
    tab, page = find_tab(tab_id, dashboard)
    if tab is None:
        return []
    specs = list(dashboard.get("general_filters") or [])
    # ADR 0026: tab-specific filters take highest priority
    tab_specs = tab.get("tab_filter_config", {}).get("filters") or []
    specs += tab_specs
    specs += list(tab.get("general_filters") or [])
    if page is not None and (page_id is None or page.get("id") == page_id):
        specs += list(page.get("filters") or [])
    return specs


def with_selected_values(specs, selected):
    """Overlay the values chosen in the UI onto the definitions."""
    merged = []
    for spec in specs or []:
        # Handle both old format (dict with id/label/column/mode/values) and new format
        if isinstance(spec, dict):
            item = dict(spec)
            spec_id = item.get("id", "")
        else:
            # Old format: spec might be a list/tuple, convert to dict
            item = {"id": spec[0] if len(spec) > 0 else "", 
                    "label": spec[1] if len(spec) > 1 else "",
                    "column": spec[2] if len(spec) > 2 else "",
                    "mode": spec[3] if len(spec) > 3 else "multi",
                    "values": spec[4] if len(spec) > 4 else []}
            spec_id = item.get("id", "")
        
        values = (selected or {}).get(spec_id)
        if values is not None:
            item["values"] = (list(values) if isinstance(values, (list, tuple))
                              else [values])
        # Ensure required keys exist
        item.setdefault("id", spec_id)
        item.setdefault("label", item.get("label", ""))
        item.setdefault("column", item.get("column", ""))
        item.setdefault("mode", item.get("mode", "multi"))
        item.setdefault("values", item.get("values", []))
        merged.append(item)
    return merged


def apply_filters(df, specs, selected=None):
    """Narrow the statements with dashboard, tab and page filters in order."""
    from TMonWidgets.MultiSelector import apply_page_filters, normalise_filter

    normalised = [normalise_filter(spec)
                  for spec in with_selected_values(specs, selected)]
    return apply_page_filters(df, [spec for spec in normalised if spec is not None])


def initial_filter_values(dashboard=None):
    """The selected values a fresh dashboard starts with, keyed by filter id (ADR 0026)."""
    dashboard = dashboard if dashboard is not None else load()
    specs = list(dashboard.get("general_filters") or [])
    tab_modes = {}
    for tab in dashboard.get("tabs") or []:
        # Include tab-specific filters
        tab_specs = tab.get("tab_filter_config", {}).get("filters") or []
        tab_mode = tab.get("tab_filter_config", {}).get("filter_mode_selection", "single")
        tab_modes[tab["id"]] = tab_mode
        specs += tab_specs
        for page in tab.get("pages") or []:
            specs += list(page.get("filters") or [])
    return {spec["id"]: list(spec.get("values") or []) for spec in specs}, tab_modes


def layout_for(layout=None, dashboard=None, tab=None):
    """Translate a tab/page arrangement into the existing layout controls."""
    dashboard = dashboard if dashboard is not None else load()
    values = dict(LAYOUT_DEFAULTS)
    values.update(dashboard.get("layout") or {})
    values.update((tab or {}).get("layout") or {})
    values.update(layout or {})
    return {CONTROL_KEYS[key]: values.get(key, LAYOUT_DEFAULTS[key])
            for key in CONTROL_KEYS}
