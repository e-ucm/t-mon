import json

import pandas as pd

from LoadProcessStatements import (
    flatten_for_display,
    is_json_and_not_list,
    load_from_string,
    processxapisgdata,
    resolve_actor_name,
    resolve_actor_name_column,
)


def new_statement():
    return {
        "context": {
            "contextActivities": {
                "category": [
                    {"id": "http://example.com/profile"},
                    {"id": "http://example.com/second"},
                ]
            }
        },
        "actor": {"account": {"name": "player-12"}},
        "verb": {"id": "http://adlnet.gov/expapi/verbs/initialized"},
    }


def test_is_json_and_not_list():
    assert is_json_and_not_list('{"actor": {"name": "a"}}')
    assert not is_json_and_not_list('[{"actor": {"name": "a"}}]')
    assert not is_json_and_not_list("not json")


def test_resolve_actor_name_copies_account_when_name_missing():
    statement = resolve_actor_name({"actor": {"account": {"name": "player-12"}}})
    assert statement["actor"]["name"] == "player-12"


def test_resolve_actor_name_keeps_existing_name():
    statement = resolve_actor_name({"actor": {"name": "Jane", "account": {"name": "jane-01"}}})
    assert statement["actor"]["name"] == "Jane"


def test_resolve_actor_name_leaves_other_shapes_untouched():
    assert resolve_actor_name({"verb": {"id": "v"}}) == {"verb": {"id": "v"}}
    assert resolve_actor_name({}) == {}


def test_processxapisgdata_collapses_category_and_resolves_actor():
    data = []
    statement = new_statement()
    processxapisgdata(statement, data)
    assert data == [statement]
    assert statement["context"]["contextActivities"]["category"] == "http://example.com/profile"
    assert statement["actor"]["name"] == "player-12"


def test_load_from_string_rejects_empty_content():
    info, err, data = [], [], []
    result = load_from_string("", data, info, err)
    assert isinstance(result, ValueError)
    assert data == []
    assert any("no content to load" in line for line in err)


def test_load_from_string_one_statement_per_line():
    info, err, data = [], [], []
    lines = "\n".join(json.dumps(new_statement()) for _ in range(3))
    result = load_from_string(lines, data, info, err)
    assert result is None
    assert len(data) == 3
    assert all(s["actor"]["name"] == "player-12" for s in data)
    assert any("one-statement-per-line" in line for line in info)
    assert any("processed 3/3" in line for line in info)
    assert err == []


def test_load_from_string_statement_array():
    info, err, data = [], [], []
    doc = json.dumps([new_statement() for _ in range(2)])
    result = load_from_string(doc, data, info, err)
    assert result is None
    assert len(data) == 2
    assert any("statement-array" in line for line in info)
    assert any("total statements = 2" in line for line in info)


def test_load_from_string_bad_json_returns_exception():
    info, err, data = [], [], []
    result = load_from_string("this is not json", data, info, err)
    assert isinstance(result, Exception)
    assert data == []
    assert any("ERROR loading at line/statement" in line for line in err)


def test_resolve_actor_name_column_only_account_column():
    df = pd.DataFrame({"actor.account.name": ["u1", "u2"]})
    out = resolve_actor_name_column(df)
    assert out["actor.name"].tolist() == ["u1", "u2"]


def test_resolve_actor_name_column_coalesces_both_columns():
    df = pd.DataFrame({"actor.name": ["u1", None], "actor.account.name": ["x", "u2"]})
    out = resolve_actor_name_column(df)
    assert out["actor.name"].tolist() == ["u1", "u2"]


def test_resolve_actor_name_column_unchanged_without_actor_columns():
    df = pd.DataFrame({"other": [1, 2]})
    out = resolve_actor_name_column(df)
    assert out.columns.tolist() == ["other"]


def test_flatten_for_display_expands_single_object():
    df = pd.DataFrame(
        {"context.contextActivities.parent": [{"id": "http://x/activities/1"}]}
    )
    out = flatten_for_display(df)
    assert out["context.contextActivities.parent.id"].tolist() == ["http://x/activities/1"]
    assert "context.contextActivities.parent" not in out.columns


def test_flatten_for_display_joins_arrays():
    df = pd.DataFrame(
        {
            "parent": [
                [{"id": "http://x/activities/1"}, {"id": "http://x/activities/2"}],
                [{"id": "http://x/activities/3"}],
            ]
        }
    )
    out = flatten_for_display(df)
    assert out["parent.id"].tolist() == [
        "http://x/activities/1, http://x/activities/2",
        "http://x/activities/3",
    ]


def test_flatten_for_display_joins_scalar_arrays():
    df = pd.DataFrame({"nums": [[1, 2], [3]]})
    out = flatten_for_display(df)
    assert out["nums"].tolist() == ["1, 2", "3"]


def test_flatten_for_display_preserves_row_count():
    df = pd.DataFrame({"a": [1, 2], "ctx": [[{"x": 1}], [{"x": 2}]]})
    out = flatten_for_display(df)
    assert len(out) == 2
    assert out["ctx.x"].tolist() == ["1", "2"]