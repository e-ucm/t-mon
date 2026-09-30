"""
Build a chart out of the loaded xAPI statements, from a small description of it.

The visualisations under `vis/` answer one question each and know the shape of the
xAPI-SG statements they are about. This module answers a different one: given a chart
type, a column to put on each axis and how to reduce the statements, what does that
look like? It therefore works on any statement set, including the objects and results a
named visualisation would never look at.

A description is kept as plain data, so the dashboard can hold several of them, redraw
them whenever the data or the filters change, and carry them in a link.
"""
import math

import pandas as pd
import plotly.express as px

from vis import xAPISGnoDataToFillVisualization

# Chart types offered. A pie reads a single column of values against labels, which is
# why it is drawn apart from the other three.
CHART_TYPES = ("bar", "line", "pie", "scatter")

# How the statements of a group are reduced to the number a bar or a point shows.
AGGREGATIONS = ("count", "sum", "mean", "nunique")

AGGREGATION_LABELS = {
    "count": "number of statements",
    "sum": "sum",
    "mean": "mean",
    "nunique": "number of different values",
}

# Choice offered where a chart counts statements rather than measuring a value.
COUNT_LABEL = "(count of statements)"

# Column holding the statement timestamps, which is a date and not a text to group by.
TIME_COLUMN = "timestamp"

# Separator and placeholder of the compact form a description takes in a link. None of
# the values can hold a vertical bar: they are a chart type, two column names and one of
# the aggregations, none of which contains one.
SPEC_SEPARATOR = "|"
SPEC_EMPTY = "-"
CREATED_CHARTS_PARAM = "chart"

# Ceiling on how many charts the dashboard holds at once, so neither a link nor a user
# can arrive with a list long enough to be unreadable.
MAX_CREATED_CHARTS = 8


def is_scalar(value):
    """
    Tell a value a chart can plot from one it cannot.

    `pandas.json_normalize` flattens the objects of a statement into columns but keeps
    its arrays whole, a statement ref or a set of context activities being the usual
    ones, and those have no place on an axis.

    Args:
        value: A cell of a statements DataFrame.

    Returns:
        bool: True when the value is a single number, a string or a boolean.
    """
    if value is None:
        return False
    if isinstance(value, float):
        # NaN is a cell a statement left out rather than a value, and it is the one
        # float shape that cannot be plotted.
        return not math.isnan(value)
    return isinstance(value, (str, int, float, bool))


def numeric_columns(df):
    """
    Return the columns that hold a number, which is what a measured axis needs.

    Args:
        df (pandas.DataFrame): The normalized statements.

    Returns:
        list: The column names, in the order the frame holds them.
    """
    found = []
    for column in df.columns:
        present = df[column].dropna()
        if present.empty:
            continue
        if pd.api.types.is_numeric_dtype(present) or isinstance(present.iloc[0], (int, float, bool)):
            found.append(column)
    return found


def chartable_columns(df):
    """
    Return the columns that can go on an axis, texts and numbers alike.

    A column every statement left out carries no value to group by, so it is left out
    of the choices rather than offered and then refused.

    Args:
        df (pandas.DataFrame): The normalized statements.

    Returns:
        list: The column names, in the order the frame holds them.
    """
    found = []
    for column in df.columns:
        present = df[column].dropna()
        if not present.empty and is_scalar(present.iloc[0]):
            found.append(column)
    return found


def normalise_spec(spec, df=None):
    """
    Read a chart description, filling in what it leaves out and dropping what it names wrongly.

    A description may come from a link, so it is treated as input and not as intent: an
    unknown chart type falls back to a bar chart and an unknown column to the first one
    there is. Anything that cannot be drawn at all comes back as None.

    Args:
        spec (dict): The description, with the keys `type`, `x`, `y` and `aggregation`.
        df (pandas.DataFrame, optional): The statements, to check the columns against.

    Returns:
        dict or None: The description to draw, or None when there is nothing to draw.
    """
    if not isinstance(spec, dict):
        return None
    chart_type = spec.get("type") if spec.get("type") in CHART_TYPES else "bar"
    aggregation = spec.get("aggregation") if spec.get("aggregation") in AGGREGATIONS else "count"
    x = spec.get("x")
    y = spec.get("y") or COUNT_LABEL
    if df is not None and not df.empty:
        columns = chartable_columns(df)
        if x not in columns:
            x = columns[0] if columns else None
        if y != COUNT_LABEL and y not in numeric_columns(df):
            # A column that holds no number cannot be measured, so the chart counts
            # statements instead of failing on the value it cannot read.
            y = COUNT_LABEL
    if not x:
        return None
    return {"type": chart_type, "x": x, "y": y, "aggregation": aggregation}


def describe(spec):
    """
    Return a one-line title for a chart, naming what it groups and what it shows.

    Args:
        spec (dict): The chart description.

    Returns:
        str: The title to put above the figure.
    """
    x = str(spec.get("x") or "").split(".")[-1]
    y = spec.get("y") or COUNT_LABEL
    if y == COUNT_LABEL:
        return f"{x} - number of statements"
    measure = AGGREGATION_LABELS.get(spec.get("aggregation"), spec.get("aggregation"))
    return f"{measure} of {y.split('.')[-1]} by {x}"


def _as_datetime(series):
    """
    Read a column as dates when it holds dates.

    Args:
        series (pandas.Series): The column to read.

    Returns:
        pandas.Series: The column as dates when it could be read as such, and unchanged
            otherwise, so a column of texts is still grouped as text.
    """
    try:
        return pd.to_datetime(series, format="ISO8601", utc=True, errors="raise")
    except (ValueError, TypeError):
        return series


def build_chart(df, spec):
    """
    Draw the chart a description asks for.

    Anything that leaves nothing to draw, or that cannot be measured, comes back as the
    same placeholder the other visualisations use, so a chart that cannot be built looks
    the same as one with no data instead of raising.

    Args:
        df (pandas.DataFrame): The normalized statements to draw.
        spec (dict): The chart description.

    Returns:
        plotly.graph_objects.Figure: The figure to show.
    """
    spec = normalise_spec(spec, df)
    if spec is None or df is None or df.empty:
        return xAPISGnoDataToFillVisualization.noDataToFillVis(10)
    x, y, aggregation = spec["x"], spec["y"], spec["aggregation"]
    counting = y == COUNT_LABEL
    if counting:
        # Without a value to reduce, the only thing left to count is the statements.
        aggregation = "count"
    data = df.copy()
    if x == TIME_COLUMN:
        data[x] = _as_datetime(data[x])
    if not counting:
        # A description from a link may name a column that is not a number after all;
        # the values that do not read as one are dropped rather than failing the chart.
        data[y] = pd.to_numeric(data[y], errors="coerce")
        data = data.dropna(subset=[x, y])
    else:
        data = data.dropna(subset=[x])
    if data.empty:
        return xAPISGnoDataToFillVisualization.noDataToFillVis(10)
    grouped = data.groupby(x, dropna=False)
    if counting:
        summarised = grouped.size().rename(COUNT_LABEL).reset_index()
        value_column, value_label = COUNT_LABEL, "statements"
    else:
        # The reduction is asked of the one column rather than of the whole group: a
        # group holds text columns too, and averaging those is not a number at all.
        reduced = {
            "sum": lambda: grouped[y].sum(),
            "mean": lambda: grouped[y].mean(),
            "nunique": lambda: grouped[y].nunique(),
        }[aggregation]
        summarised = reduced().reset_index()
        value_column, value_label = y, y.split(".")[-1]
    labels = {x: x.split(".")[-1], value_column: value_label}
    if spec["type"] == "pie":
        # A pie reads one column of values against labels and takes no measure of its own.
        figure = px.pie(summarised, names=x, values=value_column, labels=labels)
    elif spec["type"] == "line":
        figure = px.line(summarised, x=x, y=value_column, markers=True, labels=labels)
    elif spec["type"] == "scatter":
        figure = px.scatter(summarised, x=x, y=value_column, labels=labels)
    else:
        figure = px.bar(summarised, x=x, y=value_column, labels=labels)
    figure.update_layout(title=describe(spec))
    return figure


def encode_spec(spec):
    """
    Return the compact form of a chart description, for a link.

    Args:
        spec (dict): The chart description.

    Returns:
        str or None: The description as `type|x|y|aggregation`, or None when there is
            nothing worth writing down.
    """
    if not isinstance(spec, dict) or not spec.get("x"):
        return None
    # Counting statements is the absence of a value to measure, so it is written as the
    # absence rather than as its label: a link stays readable, and the label changes
    # without stranding the links that already carry the charts.
    y = spec.get("y") or COUNT_LABEL
    values = [
        spec.get("type") or "",
        spec.get("x") or "",
        "" if y == COUNT_LABEL else y,
        spec.get("aggregation") or "count",
    ]
    return SPEC_SEPARATOR.join(SPEC_EMPTY if not value else str(value) for value in values)


def decode_specs(value):
    """
    Read the chart descriptions a link carries.

    Args:
        value (str): The value of the link parameter, descriptions separated by commas.

    Returns:
        list: The descriptions, in the order the link lists them, without one that names
            no axis to draw, and never more than the dashboard holds.
    """
    specs = []
    for entry in (value or "").split(","):
        parts = [part if part != SPEC_EMPTY else "" for part in entry.split(SPEC_SEPARATOR)]
        parts += [""] * (4 - len(parts))
        # A description read back is held in the same shape as one just built, so the
        # list the dashboard keeps never carries two ways of saying the same thing. The
        # link stays the short one it is, since encode_spec writes the label back as the
        # absence it was read from.
        spec = {
            "type": parts[0] or "bar",
            "x": parts[1],
            "y": parts[2] or COUNT_LABEL,
            "aggregation": parts[3] or "count",
        }
        if spec["x"]:
            specs.append(spec)
    return specs[:MAX_CREATED_CHARTS]
