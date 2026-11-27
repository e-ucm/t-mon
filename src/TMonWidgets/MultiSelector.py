"""
Selection helpers for the dashboard.

The first function keeps the two fixed header dropdowns working. The rest carry
the page filters a user adds through the UI: their compact link form, their
application to the statements, and the columns that can be filtered.
"""
import base64
import json

FILTER_MODES = ("multi", "single")
PAGE_FILTER_PARAM = "filter"
MAX_PAGE_FILTERS = 8
# Total filters a page may show: definition (all-tabs + this-tab) filters plus
# the ones the user adds to the page (ADR 0024).
MAX_TOTAL_FILTERS = 6


def searchValueFromMultiSelector(df, object, search_value,value):
    filtered_df=df
    # Make sure that the set values are in the option list, else they will disappear
    # from the shown select list, but still part of the `value`.
    # Convert the dictionary keys to the appropriate format for dropdown options
    all_options = [{'label': k, 'value': k} for k in df[object].unique()]
    # Filter options based on the search value
    if search_value is not None:
        filtered_options = [o for o in all_options if search_value.lower() in o['label'].lower()]
    else:
        filtered_options = all_options
    # Ensure selected values remain in the options list
    if value:
        selected_options = [o for o in all_options if o['value'] in value]
        filtered_options = selected_options + filtered_options
        filtered_df = df.loc[df[object].isin(value)]
    # Remove duplicates while preserving order
    unique_options = list({v['value']:v for v in filtered_options}.values())
    return filtered_df, unique_options


def filterable_columns(df):
    """Columns whose values can be offered as filter choices."""
    if df is None or df.empty:
        return []
    return [
        column for column in df.columns
        if df[column].dropna().map(
            lambda value: isinstance(value, (str, int, float, bool))
        ).any()
    ]


def normalise_filter(spec, df=None):
    """Validate one filter description, or return None when it is unusable."""
    if not isinstance(spec, dict):
        return None
    column = spec.get("column")
    mode = spec.get("mode") if spec.get("mode") in FILTER_MODES else "multi"
    if not column:
        return None
    column = str(column)
    if df is not None and not df.empty and column not in df.columns:
        return None
    values = spec.get("values") or []
    if isinstance(values, str):
        values = [values]
    values = [str(value) for value in values if value is not None and value != ""]
    if df is not None and not df.empty and column in df.columns:
        # A value the statements no longer contain would narrow the view for no
        # reason; drop it and let the remaining choices speak for the page.
        present = {str(value) for value in df[column].dropna().unique()}
        values = [value for value in values if value in present]
    if mode == "single":
        values = values[:1]
    normalised = {
        "column": column,
        "mode": mode,
        "values": values[:MAX_PAGE_FILTERS],
    }
    if "name" in spec:
        normalised["name"] = str(spec.get("name") or "").strip()[:80]
    if "hidden" in spec:
        normalised["hidden"] = bool(spec.get("hidden"))
    if "target_tab" in spec:
        target_tab = spec.get("target_tab")
        normalised["target_tab"] = str(target_tab).strip()[:160] if target_tab else ""
    return normalised


def apply_page_filters(df, filters):
    """Narrow the statements with every page filter, in order."""
    for spec in filters or []:
        normalised = normalise_filter(spec, df)
        if normalised is None or not normalised["values"]:
            continue
        column = normalised["column"]
        if column not in df.columns:
            continue
        df = df.loc[df[column].astype(str).isin(normalised["values"])]
    return df


def filter_options(df, column):
    """Distinct choices for a filter, in the order the data names them."""
    if df is None or df.empty or column not in df.columns:
        return []
    values = [
        value for value in df[column].dropna().unique()
        if isinstance(value, (str, int, float, bool))
    ]
    return [{"label": str(value), "value": str(value)} for value in values]


def encode_filter(spec):
    """One filter as ``mode|column|base64(values)`` for a link or a file."""
    normalised = normalise_filter(spec)
    if normalised is None:
        return None
    metadata = {key: normalised[key] for key in ("name", "hidden", "target_tab")
                if key in normalised}
    payload = {"values": normalised["values"], **metadata} if metadata else normalised["values"]
    encoded = base64.b64encode(
        json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).decode("ascii")
    return "|".join([normalised["mode"], normalised["column"], encoded])


def encode_filters(filters):
    """All filters as one URL value, joined by commas."""
    encoded = [encode_filter(spec) for spec in filters or []]
    return ",".join(value for value in encoded if value)


def decode_filters(value):
    """Read the filters a link carries, keeping only valid descriptions."""
    specs = []
    for entry in (value or "").split(","):
        parts = entry.split("|")
        if len(parts) < 3:
            continue
        mode, column, encoded = parts[0], parts[1], "|".join(parts[2:])
        try:
            values = json.loads(base64.b64decode(encoded).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            continue
        if isinstance(values, dict):
            payload = values
            values = payload.get("values")
        else:
            # Legacy links encoded only the selected values as a JSON array.
            payload = {}
        if isinstance(values, list):
            spec = normalise_filter({
                **payload, "mode": mode, "column": column, "values": values,
            })
            if spec is not None:
                specs.append(spec)
    return specs[:MAX_PAGE_FILTERS]