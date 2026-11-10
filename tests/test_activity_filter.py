import math

import pandas as pd

from TMonWidgets.ActivityFilter import (
    activity_id_of_iri,
    activity_ids_of_context_activities,
    filter_df_by_activities,
    is_missing,
    statement_activity_ids,
    statements_activity_ids,
)


def test_is_missing():
    assert is_missing(None)
    assert is_missing(math.nan)
    assert not is_missing("x")
    assert not is_missing(5.0)


def test_activity_id_of_iri():
    assert activity_id_of_iri("http://host/api/activities/123") == "123"
    assert (
        activity_id_of_iri("http://host/api/simlets/1/sessions/2/activities/3") == "3"
    )
    assert activity_id_of_iri("http://host/something/else") is None
    assert activity_id_of_iri("http://example.com/profile") is None
    assert activity_id_of_iri("") is None
    assert activity_id_of_iri(None) is None
    assert activity_id_of_iri(123) is None


def test_activity_ids_of_context_activities():
    assert activity_ids_of_context_activities(None) == set()
    assert activity_ids_of_context_activities("profile") == set()
    assert activity_ids_of_context_activities({"id": "http://host/api/activities/7"}) == {"7"}
    assert activity_ids_of_context_activities(
        [
            {"id": "http://host/api/activities/7"},
            {"id": "http://host/api/activities/9"},
            {"id": "http://example.com/profile"},
        ]
    ) == {"7", "9"}


def test_statement_activity_ids():
    statement = {
        "context": {
            "contextActivities": {
                "grouping": [{"id": "http://host/api/simlets/1/activities/12"}],
                "parent": [{"id": "http://host/api/simlets/1/sessions/2/activities/3"}],
                "category": [{"id": "http://example.com/profile"}],
                "other": [{"id": "http://host/api/activities/5"}],
            }
        }
    }
    assert statement_activity_ids(statement) == {"12", "3", "5"}


def test_statement_activity_ids_without_context():
    assert statement_activity_ids({"verb": {"id": "v"}}) == set()
    assert statement_activity_ids({}) == set()
    assert statement_activity_ids(None) == set()


def test_statements_activity_ids_first_seen_order():
    statements = [
        {"context": {"contextActivities": {"grouping": [{"id": "http://h/api/activities/1"}]}}},
        {
            "context": {
                "contextActivities": {
                    "grouping": [
                        {"id": "http://h/api/activities/2"},
                        {"id": "http://h/api/activities/1"},
                    ]
                }
            }
        },
        {},
    ]
    assert statements_activity_ids(statements) == ["1", "2"]
    assert statements_activity_ids(None) == []


def test_filter_df_by_activities_removes_hidden_rows():
    df = pd.DataFrame(
        {
            "context.contextActivities.grouping": [
                [{"id": "http://h/api/activities/1"}],
                [{"id": "http://h/api/activities/2"}],
            ]
        }
    )
    filtered, known = filter_df_by_activities(df, hidden=["2"])
    assert filtered.index.tolist() == [0]
    assert known == ["1", "2"]


def test_filter_df_by_activities_keeps_row_of_shared_activity():
    df = pd.DataFrame(
        {
            "context.contextActivities.grouping": [
                [{"id": "http://h/api/activities/1"}, {"id": "http://h/api/activities/2"}],
            ]
        }
    )
    filtered, _ = filter_df_by_activities(df, hidden=["2"])
    assert len(filtered) == 1


def test_filter_df_by_activities_without_activity_columns():
    df = pd.DataFrame({"verb.id": ["a"]})
    filtered, known = filter_df_by_activities(df, hidden=["1"])
    assert filtered.equals(df)
    assert known == []


def test_filter_df_by_activities_ignores_unknown_hidden_ids():
    df = pd.DataFrame(
        {"context.contextActivities.grouping": [[{"id": "http://h/api/activities/1"}]]}
    )
    filtered, known = filter_df_by_activities(df, hidden=["999"])
    assert filtered.equals(df)
    assert known == ["1"]