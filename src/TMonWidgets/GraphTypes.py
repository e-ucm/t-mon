"""
Renderers for the graph types a default dashboard definition may use.

A graph type is code: it says how a figure is drawn and what data shape it needs.
It knows nothing about the wording of a title or an axis. Those strings come from
the dashboard definition and are applied by :func:`render_graph`, so a deployment
can name a figure anything it likes without touching this module or a locale file.
"""
from dataclasses import dataclass
from typing import Callable

import pandas as pd
import plotly.express as px
from dash import dash_table

from TMonWidgets.EmptyFigure import no_data_figure
from TMonWidgets.ValueLabels import full_url_map, hover_values, shorten_url_value

# A code-defined measure rather than a column of the statements. It is a data
# source, not a label; the definition still supplies the human wording.
COUNT_DATA = "count"

# Reductions accepted for a measured y axis.
AGGREGATIONS = ("count", "sum", "mean", "nunique", "min", "max")


@dataclass(frozen=True)
class GraphType:
    """One registered graph type.

    ``axes`` names the axes a definition must provide. ``date_axis`` says whether
    ``x.date`` is meaningful for the type, ``table`` whether it returns a Dash
    table instead of a Plotly figure. ``renderer`` only draws data.
    """

    identifier: str
    axes: tuple
    date_axis: bool
    table: bool
    renderer: Callable


def _placeholder():
    """The shared empty figure used everywhere in T-Mon when data is absent."""
    return no_data_figure(10)


def _summary(df, graph):
    """Group the statements by x and reduce y to one value per group."""
    x_column = graph["x"]["data"]
    y_column = graph["y"]["data"]
    aggregation = graph.get("aggregation") or (
        "count" if y_column == COUNT_DATA else "mean")
    if aggregation not in AGGREGATIONS:
        raise ValueError(f"Unsupported aggregation: {aggregation!r}.")
    needed = [x_column]
    if y_column != COUNT_DATA and aggregation != "count":
        needed.append(y_column)
    if df is None or any(column not in df.columns for column in needed):
        return None

    data = df.copy()
    full_x = {}
    if graph["x"].get("date"):
        data[x_column] = pd.to_datetime(data[x_column], errors="coerce", utc=True)
    else:
        # An xAPI id is a URL. Show its last segment on the axis instead of the
        # whole IRI, without changing the statements that filters still use.
        full_x = full_url_map(data[x_column])
        data[x_column] = data[x_column].map(shorten_url_value)
    if y_column != COUNT_DATA and aggregation != "count":
        data[y_column] = data[y_column].map(shorten_url_value)
        data[y_column] = pd.to_numeric(data[y_column], errors="coerce")
    data = data.dropna(subset=[x_column] if aggregation == "count"
                       or y_column == COUNT_DATA else [x_column, y_column])
    if data.empty:
        return None
    grouped = data.groupby(x_column, dropna=False)
    if aggregation == "count":
        summary = grouped.size().rename("value").reset_index()
    else:
        summary = grouped[y_column].agg(aggregation).rename("value").reset_index()
    summary.attrs["full_x"] = full_x
    return summary


def _with_url_hover(figure, summary, graph, template):
    """Show the full URL on hover for marks whose axis value was shortened."""
    full_x = summary.attrs.get("full_x") or {}
    if full_x:
        figure.update_traces(
            customdata=[[full] for full in hover_values(
                summary[graph["x"]["data"]], full_x)],
            hovertemplate=template)
    return figure


def _cartesian(df, graph, kind):
    """A bar, line or scatter of one value per x group."""
    summary = _summary(df, graph)
    if summary is None:
        return _placeholder()
    draw = {"bar": px.bar, "line": px.line, "scatter": px.scatter}[kind]
    options = {"markers": True} if kind == "line" else {}
    figure = draw(summary, x=graph["x"]["data"], y="value", **options)
    return _with_url_hover(figure, summary, graph,
                           "%{customdata[0]}<br>%{y}<extra></extra>")


def _bar(df, graph):
    return _cartesian(df, graph, "bar")


def _line(df, graph):
    return _cartesian(df, graph, "line")


def _scatter(df, graph):
    return _cartesian(df, graph, "scatter")


def _pie(df, graph):
    summary = _summary(df, graph)
    if summary is None:
        return _placeholder()
    figure = px.pie(summary, names=graph["x"]["data"], values="value")
    return _with_url_hover(figure, summary, graph,
                           "%{customdata[0]}<br>%{value}<extra></extra>")


def _heatmap(df, graph):
    """Count statements for every x/y pair."""
    x_column = graph["x"]["data"]
    y_column = graph["y"]["data"]
    if graph["x"].get("date") or df is None or df.empty:
        return _placeholder()
    if x_column not in df.columns or y_column not in df.columns:
        return _placeholder()
    data = df.dropna(subset=[x_column, y_column]).copy()
    full_x = full_url_map(data[x_column])
    full_y = full_url_map(data[y_column])
    data[x_column] = data[x_column].map(shorten_url_value)
    data[y_column] = data[y_column].map(shorten_url_value)
    if data.empty:
        return _placeholder()
    counts = data.groupby([x_column, y_column], dropna=False).size().reset_index(
        name="value")
    matrix = counts.pivot(index=y_column, columns=x_column, values="value").fillna(0)
    figure = px.imshow(matrix, aspect="auto", origin="lower")
    if full_x or full_y:
        # customdata[row][column] = [y value, x value], both as full URLs.
        figure.update_traces(
            customdata=[[[full_y.get(row, row), full_x.get(column, column)]
                         for column in matrix.columns] for row in matrix.index],
            hovertemplate=("x: %{customdata[1]}<br>y: %{customdata[0]}"
                           "<br>%{z}<extra></extra>"))
    return figure


def _table(df, graph):
    """The audit view of the statements a graph would have received."""
    table_df = df if df is not None else pd.DataFrame()
    return dash_table.DataTable(
        id=f"default-table-{graph.get('id', 'table')}",
        columns=[{"name": column, "id": column} for column in table_df.columns],
        data=table_df.where(pd.notna(table_df), None).to_dict("records"),
        filter_action="native",
        sort_action="native",
        sort_mode="multi",
    )


GRAPH_TYPES = {
    entry.identifier: entry
    for entry in (
        GraphType("bar", ("x", "y"), True, False, _bar),
        GraphType("line", ("x", "y"), True, False, _line),
        GraphType("scatter", ("x", "y"), True, False, _scatter),
        GraphType("pie", ("x", "y"), False, False, _pie),
        GraphType("heatmap", ("x", "y"), False, False, _heatmap),
        GraphType("table", (), False, True, _table),
    )
}

# Kept separate so callers do not have to import the dataclass to list the types.
SUPPORTED_TYPES = tuple(GRAPH_TYPES)


def supports_date(graph_type):
    """Whether a graph type can plot a parsed date on its x axis."""
    entry = GRAPH_TYPES.get(graph_type)
    return bool(entry and entry.date_axis)


def render_graph(df, graph):
    """
    Draw one validated graph definition against ``df``.

    The definition supplies every piece of wording: a missing ``title`` leaves the
    figure untitled, and axis labels are only set when the definition names them.
    No translation lookup happens here.
    """
    if not isinstance(graph, dict):
        raise ValueError("A graph definition must be an object.")
    graph_type = graph.get("type")
    entry = GRAPH_TYPES.get(graph_type)
    if entry is None:
        raise ValueError(f"Unknown graph type: {graph_type!r}.")
    if (graph.get("x") or {}).get("date") and not entry.date_axis:
        raise ValueError(f"Graph type {graph_type!r} cannot plot dates.")
    figure = entry.renderer(df, graph)
    if entry.table:
        return figure
    if graph.get("title"):
        figure.update_layout(title=graph["title"])
    else:
        figure.update_layout(title=None)
    if "x" in entry.axes and graph["x"].get("label"):
        figure.update_xaxes(title_text=graph["x"]["label"])
    if "y" in entry.axes and graph["y"].get("label"):
        figure.update_yaxes(title_text=graph["y"]["label"])
    return figure
