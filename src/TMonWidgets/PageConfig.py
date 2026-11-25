"""
Versioned configuration documents for a T-Mon dashboard.

A document describes everything that defines a page or the whole dashboard:
named pages, their charts and page filters (with the selected values), the
layout controls, the header selections, hidden activities and the active tab.
The same parser is used for uploaded files and for server-side saved names, so
the two import paths cannot disagree about what a valid file is.
"""
import base64
import json
import os
import re
import tempfile
from pathlib import Path

from TMonWidgets.ChartBuilder import MAX_CREATED_CHARTS, normalise_spec
from TMonWidgets.MultiSelector import MAX_PAGE_FILTERS, normalise_filter

FORMAT_VERSION = 1
MAX_PAGES = 12
MAX_OVERRIDES = 100
LAYOUT_KEYS = (
    "graph-layout", "graph-rows", "graph-columns", "graph-page",
    "graph-split-x", "graph-split-y",
)
SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]{1,80}$")


def _clean_overrides(value):
    """Keep the graph overrides that are still chart specs T-Mon can draw."""
    if not isinstance(value, dict):
        return {}
    overrides = {}
    for key, spec in list(value.items())[:MAX_OVERRIDES]:
        if not isinstance(key, str) or not key.strip():
            continue
        normalised = normalise_spec(spec)
        if normalised is not None:
            overrides[key.strip()[:160]] = normalised
    return overrides


def build_document(charts=None, filters=None, pages=None, layout=None,
                   header=None, hidden=None, active_tab=None,
                   default_graph_overrides=None):
    """Build the plain dict that is written to a file or a saved name."""
    return {
        "version": FORMAT_VERSION,
        "active_tab": active_tab or "",
        "tabs": {
            "custom": list(pages or []),
        },
        "create_tab": {
            "charts": list(charts or []),
            "filters": list(filters or []),
        },
        # An administrator's edits of the default dashboard's graphs. Empty for
        # a document that never touched them, so old files stay the same shape.
        "default_graph_overrides": _clean_overrides(
            default_graph_overrides or {}),
        "header": {
            "actor.name": [str(value) for value in
                           (header or {}).get('actor.name') or []],
            "object.id": [str(value) for value in
                          (header or {}).get('object.id') or []],
        },
        "hidden_activities": list(hidden or []),
        "layout": dict(layout or {}),
    }


def serialize(document):
    """Write a configuration document as readable JSON."""
    return json.dumps(document, indent=2, ensure_ascii=False)


def _clean_charts(value):
    if not isinstance(value, list):
        raise ValueError("charts must be a list")
    charts = []
    for spec in value[:MAX_CREATED_CHARTS]:
        normalised = normalise_spec(spec)
        if normalised is not None:
            charts.append(normalised)
    return charts


def _clean_filters(value):
    if not isinstance(value, list):
        raise ValueError("filters must be a list")
    filters = []
    for spec in value[:MAX_PAGE_FILTERS]:
        normalised = normalise_filter(spec)
        if normalised is not None:
            filters.append(normalised)
    return filters


def _clean_pages(value):
    if not isinstance(value, list):
        raise ValueError("pages must be a list")
    pages = []
    for page in value[:MAX_PAGES]:
        if not isinstance(page, dict):
            continue
        identifier = str(page.get("id") or "").strip()
        name = str(page.get("name") or "").strip()
        if not identifier or not name:
            continue
        pages.append({
            "id": identifier,
            "name": name[:80],
            "charts": _clean_charts(page.get("charts") or []),
            "filters": _clean_filters(page.get("filters") or []),
        })
    return pages


def parse_document(text):
    """
    Validate a configuration document, dropping what T-Mon cannot use.

    Args:
        text (str): JSON text, either from an uploaded file or a saved name.

    Returns:
        dict: The validated document in the shape ``build_document`` writes.

    Raises:
        ValueError: When the text is not a supported configuration.
    """
    try:
        raw = json.loads(text)
    except (TypeError, ValueError) as error:
        raise ValueError("The file is not valid JSON.") from error
    if not isinstance(raw, dict):
        raise ValueError("The configuration must be a JSON object.")
    version = raw.get("version")
    if version != FORMAT_VERSION:
        raise ValueError(f"Unsupported configuration version: {version!r}.")
    tabs = raw.get("tabs") if isinstance(raw.get("tabs"), dict) else {}
    create = raw.get("create_tab") if isinstance(raw.get("create_tab"), dict) else {}
    header = raw.get("header") if isinstance(raw.get("header"), dict) else {}
    hidden = raw.get("hidden_activities") if isinstance(raw.get("hidden_activities"), list) else []
    layout = raw.get("layout") if isinstance(raw.get("layout"), dict) else {}
    return {
        "version": FORMAT_VERSION,
        "active_tab": str(raw.get("active_tab") or ""),
        "tabs": {"custom": _clean_pages(tabs.get("custom") or [])},
        "create_tab": {
            "charts": _clean_charts(create.get("charts") or []),
            "filters": _clean_filters(create.get("filters") or []),
        },
        "default_graph_overrides": _clean_overrides(
            raw.get("default_graph_overrides") or {}),
        "header": {
            "actor.name": [str(value) for value in header.get("actor.name") or []],
            "object.id": [str(value) for value in header.get("object.id") or []],
        },
        "hidden_activities": [str(value) for value in hidden],
        "layout": {key: value for key, value in layout.items() if key in LAYOUT_KEYS},
    }


def import_config(contents):
    """
    Read a configuration from a ``dcc.Upload`` contents string or plain JSON.

    Dash uploads a data URI; saved names hold plain JSON. Both are accepted so
    the confirmation and apply steps need only one representation.
    """
    if not contents:
        raise ValueError("No configuration was provided.")
    text = str(contents)
    if text.startswith("data:"):
        try:
            text = base64.b64decode(text.split(",", 1)[1]).decode("utf-8")
        except (IndexError, ValueError, UnicodeDecodeError) as error:
            raise ValueError("The uploaded file could not be read.") from error
    return parse_document(text)


def sanitise_name(name):
    """Return a safe file name, or None when the name cannot be used."""
    candidate = str(name or "").strip()
    if not SAFE_NAME.match(candidate) or candidate in (".", ".."):
        return None
    return candidate


def config_root():
    """Directory holding per-user saved configurations."""
    configured = os.environ.get("TMON_CONFIG_DIR")
    return Path(configured) if configured else Path(tempfile.gettempdir()) / "tmon-configs"


def user_key():
    """The logged-in username, or ``shared`` when there is no login."""
    try:
        from flask import session
        profile = session.get("oidc_auth_profile") or {}
        name = profile.get("preferred_username")
        if name:
            return re.sub(r"[^A-Za-z0-9._-]", "_", str(name))[:80]
    except (RuntimeError, ImportError, AttributeError):
        pass
    return "shared"


def _user_dir(simlet_id=None, session_id=None):
    if simlet_id is not None:
        base = Path('/mnt/tmon-dashboards') / 'simlets' / str(simlet_id)
        if session_id is None:
            base = base / 'general'
        else:
            base = base / 'sessions' / str(session_id)
        return base / 'users' / user_key()
    return config_root() / user_key()


def list_saved(simlet_id=None, session_id=None):
    """Names of configurations saved for the current user."""
    directory = _user_dir(simlet_id=simlet_id, session_id=session_id)
    if not directory.is_dir():
        return []
    return sorted(path.stem for path in directory.glob("*.json"))


def save_named(name, document, simlet_id=None, session_id=None):
    """Atomically save a validated document under ``name``."""
    safe = sanitise_name(name)
    if safe is None:
        raise ValueError("Use a name of letters, numbers, dot, dash or underscore.")
    directory = _user_dir(simlet_id=simlet_id, session_id=session_id)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{safe}.json"
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(serialize(parse_document(serialize(document))), encoding="utf-8")
    os.replace(temporary, target)
    return safe


def load_named(name, simlet_id=None, session_id=None):
    """Read a saved document, validating it before it is returned."""
    safe = sanitise_name(name)
    if safe is None:
        raise ValueError("Invalid configuration name.")
    source = _user_dir(simlet_id=simlet_id, session_id=session_id) / f"{safe}.json"
    if not source.is_file():
        raise ValueError(f"No saved configuration named {safe}.")
    return parse_document(source.read_text(encoding="utf-8"))


def delete_named(name, simlet_id=None, session_id=None):
    """Remove a saved configuration. Returns True when one was removed."""
    safe = sanitise_name(name)
    if safe is None:
        raise ValueError("Invalid configuration name.")
    source = _user_dir(simlet_id=simlet_id, session_id=session_id) / f"{safe}.json"
    if not source.is_file():
        return False
    source.unlink()
    return True
