"""
Display helpers for values that are drawn on a chart axis.

xAPI identifiers are IRIs, so grouping by the whole IRI makes an axis unreadable:
``https://yyyuyugjh.com/xxx`` says the same thing to a reader as ``xxx``. These
helpers change only how a value is shown. The statements, the filters and the links
keep the original identifier, so shortening never changes what was selected.
"""
from urllib.parse import unquote, urlsplit


def shorten_url_value(value):
    """
    Return the last segment of a URL, or the value unchanged when it is not one.

    A value is treated as a URL only when it has both a scheme and a host, so plain
    text and relative paths are left alone. A query string or a fragment is dropped;
    a URL with no path falls back to its host, which is its readable name.

    Args:
        value: A cell of a statements DataFrame.

    Returns:
        The shortened text for a URL, otherwise the original value.
    """
    if not isinstance(value, str):
        return value
    text = value.strip()
    try:
        parts = urlsplit(text)
    except ValueError:
        return value
    if not parts.scheme or not parts.netloc:
        return value
    segments = [segment for segment in parts.path.split("/") if segment]
    last = segments[-1] if segments else parts.netloc
    return unquote(last) or value


def full_url_map(series):
    """
    Map each shortened URL of a column back to the full URL(s) it stands for.

    Only values that shortening actually changed appear in the result, so an axis
    with no URL in it yields an empty map and needs no custom hover. Distinct URLs
    that share a last segment are joined, since they are drawn as one mark.

    Args:
        series (pandas.Series): The column before it was shortened.

    Returns:
        dict: ``{shortened: "full url[, full url]"}``.
    """
    found = {}
    for value in series.dropna().unique():
        short = shorten_url_value(value)
        if short != value:
            found.setdefault(short, []).append(str(value))
    return {short: ", ".join(sorted(full)) for short, full in found.items()}


def hover_values(values, mapping):
    """The text to show on hover for each plotted value: the full URL when known."""
    return [mapping.get(value, value) for value in values]
