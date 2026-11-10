import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from TMonWidgets.ChartBuilder import (
    COUNT_LABEL,
    build_chart,
    chartable_columns,
    decode_specs,
    describe,
    encode_spec,
    is_scalar,
    normalise_spec,
    numeric_columns,
)


def sample_df():
    return pd.DataFrame(
        {
            "actor.name": ["a", "b", "a"],
            "score": [1, 2, 3],
        }
    )


def test_is_scalar():
    assert is_scalar("x")
    assert is_scalar(5)
    assert is_scalar(5.0)
    assert is_scalar(True)
    assert not is_scalar(None)
    assert not is_scalar(math.nan)
    assert not is_scalar(["x"])
    assert is_scalar(np.int64(5))
    assert not is_scalar(np.float64("nan"))


def test_numeric_columns():
    df = sample_df()
    df["empty"] = [float("nan")] * 3
    assert numeric_columns(df) == ["score"]


def test_chartable_columns():
    df = sample_df()
    df["empty"] = [float("nan")] * 3
    assert chartable_columns(df) == ["actor.name", "score"]


def test_normalise_spec_fills_defaults():
    df = sample_df()
    spec = normalise_spec({"type": "bar", "x": "actor.name"}, df)
    assert spec == {"type": "bar", "x": "actor.name", "y": COUNT_LABEL, "aggregation": "count"}


def test_normalise_spec_rejects_unknown_type_and_column():
    df = sample_df()
    spec = normalise_spec({"type": "scatterplot", "x": "nope"}, df)
    assert spec == {"type": "bar", "x": "actor.name", "y": COUNT_LABEL, "aggregation": "count"}


def test_normalise_spec_resets_non_numeric_y_to_count():
    df = sample_df()
    spec = normalise_spec({"type": "bar", "x": "actor.name", "y": "actor.name"}, df)
    assert spec["y"] == COUNT_LABEL


def test_normalise_spec_rejects_non_dict_and_missing_x():
    assert normalise_spec("bar") is None
    assert normalise_spec({"type": "bar"}) is None


def test_describe():
    assert (
        describe({"x": "actor.name", "y": COUNT_LABEL, "aggregation": "count"})
        == "name - number of statements"
    )
    assert (
        describe({"x": "actor.name", "y": "result.score", "aggregation": "sum"})
        == "sum of score by name"
    )


def test_encode_spec():
    spec = {"type": "bar", "x": "actor.name", "y": COUNT_LABEL, "aggregation": "count"}
    assert encode_spec(spec) == "bar|actor.name|-|count"
    assert (
        encode_spec({"x": "a", "y": "result.score", "aggregation": "sum"})
        == "-|a|result.score|sum"
    )
    assert encode_spec(None) is None
    assert encode_spec({"type": "bar"}) is None


def test_decode_specs_roundtrip():
    spec = {"type": "pie", "x": "actor.name", "y": COUNT_LABEL, "aggregation": "count"}
    encoded = encode_spec(spec)
    assert decode_specs(encoded) == [spec]


def test_decode_specs_drops_empty_and_caps_length():
    assert decode_specs("") == []
    assert decode_specs("-") == []
    long = ",".join(["bar|actor.name|-|count"] * 12)
    assert len(decode_specs(long)) == 8


def test_build_chart_counting_bar():
    spec = {"type": "bar", "x": "actor.name", "y": COUNT_LABEL, "aggregation": "count"}
    fig = build_chart(sample_df(), spec)
    assert isinstance(fig, go.Figure)


def test_build_chart_measured_line():
    spec = {"type": "line", "x": "actor.name", "y": "score", "aggregation": "sum"}
    fig = build_chart(sample_df(), spec)
    assert isinstance(fig, go.Figure)


def test_build_chart_empty_data_returns_placeholder():
    spec = {"type": "bar", "x": "actor.name", "y": COUNT_LABEL, "aggregation": "count"}
    fig = build_chart(pd.DataFrame(), spec)
    assert isinstance(fig, go.Figure)