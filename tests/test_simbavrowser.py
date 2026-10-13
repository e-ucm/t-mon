from datetime import datetime, timezone

from SimvaBrowser.SimvaBrowser import (
    _join_url,
    extract_statements,
    format_lrs_instant,
    lrs_origin_url,
    lrs_statements_url,
    merge_statements,
    next_lrs_page_url,
    parse_lrs_instant,
    simva_statement_iri,
    statement_identity,
)


def test_extract_statements():
    assert extract_statements(None) == []
    statements = [{"id": "1"}]
    assert extract_statements(statements) is statements
    assert extract_statements({"statements": statements}) == statements
    assert extract_statements({"data": statements}) == statements
    assert extract_statements({"results": statements}) == statements
    assert extract_statements({"id": "1"}) == [{"id": "1"}]
    assert extract_statements("not an envelope") == []
    assert extract_statements({"statements": "wrong shape"}) == [{"statements": "wrong shape"}]


def test_statement_identity():
    assert statement_identity({"id": "abc", "verb": {"id": "v"}}) == "id:abc"
    assert statement_identity({"verb": {"id": "v"}}).startswith("hash:")
    assert statement_identity(["a", "b"]) == statement_identity(["a", "b"])
    assert statement_identity(3) != statement_identity(4)


def test_merge_statements_dedupes_keeps_incoming_and_orders():
    existing = [{"id": "a", "timestamp": "2024-01-01T10:00:00Z"}]
    incoming = [
        {"id": "b", "timestamp": "2024-01-01T09:00:00Z"},
        {"id": "a", "timestamp": "2024-01-01T11:00:00Z"},
    ]
    merged, added = merge_statements(existing, incoming)
    assert added == 1
    assert [s["id"] for s in merged] == ["b", "a"]
    assert merged[1]["timestamp"] == "2024-01-01T11:00:00Z"


def test_merge_statements_untimestamped_sort_last():
    existing = [{"id": "untimed"}]
    incoming = [{"id": "timed", "timestamp": "2024-01-01T10:00:00Z"}]
    merged, added = merge_statements(existing, incoming)
    assert [s["id"] for s in merged] == ["timed", "untimed"]


def test_merge_statements_counts_new():
    existing = [{"id": "a"}]
    incoming = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    merged, added = merge_statements(existing, incoming)
    assert added == 2
    assert len(merged) == 3


def test_next_lrs_page_url():
    assert next_lrs_page_url(None) is None
    assert next_lrs_page_url("more") is None
    assert (
        next_lrs_page_url({"more": "https://lrs.example/xapi/statements?page=2"})
        == "https://lrs.example/xapi/statements?page=2"
    )
    assert (
        next_lrs_page_url({"more_url": "https://lrs.example/xapi/statements?page=2"})
        == "https://lrs.example/xapi/statements?page=2"
    )
    assert (
        next_lrs_page_url({"more": "/xapi/statements?page=2"}, base_url="https://lrs.example")
        == "https://lrs.example/xapi/statements?page=2"
    )
    assert next_lrs_page_url({"more": {"href": "https://lrs.example/next"}}) == "https://lrs.example/next"
    assert next_lrs_page_url({"more": {"url": "https://lrs.example/next"}}) == "https://lrs.example/next"
    assert next_lrs_page_url({"more": ""}) is None
    assert next_lrs_page_url({}) is None


def test_join_url():
    assert _join_url(None, "/xapi/statements") == "/xapi/statements"
    assert _join_url("https://lrs.example", "/xapi/statements") == "https://lrs.example/xapi/statements"
    assert _join_url("https://lrs.example/", "xapi/statements") == "https://lrs.example/xapi/statements"


def test_lrs_origin_url():
    assert lrs_origin_url("https://lrs.example/xapi/statements") == "https://lrs.example/"
    assert lrs_origin_url(None) is None
    assert lrs_origin_url("") is None
    assert lrs_origin_url("not a url") is None


def test_lrs_statements_url():
    assert lrs_statements_url("https://lrs.example/xapi") == "https://lrs.example/xapi/statements"
    assert lrs_statements_url("https://lrs.example") == "https://lrs.example/xapi/statements"
    assert lrs_statements_url("https://lrs.example/XAPI") == "https://lrs.example/xapi/statements"
    assert lrs_statements_url("https://lrs.example/some/path") == "https://lrs.example/some/path/xapi/statements"
    assert lrs_statements_url(None) is None
    assert lrs_statements_url("") is None
    assert lrs_statements_url("relative/endpoint") is None


def test_simva_statement_iri():
    assert simva_statement_iri("https://simva.example", "1", "2", "3") == "https://simva.example/1/2/3"
    assert simva_statement_iri("https://simva.example/", "/1/", "2") == "https://simva.example/1/2"
    assert simva_statement_iri("", "1") is None
    assert simva_statement_iri(None, "1") is None
    assert simva_statement_iri("https://simva.example", None, "2") is None
    assert simva_statement_iri("https://simva.example", "", "2") is None


def test_parse_and_format_lrs_instant_roundtrip():
    moment = datetime(2024, 3, 1, 12, 30, 0, tzinfo=timezone.utc)
    assert parse_lrs_instant(format_lrs_instant(moment)) == moment


def test_parse_lrs_instant_applies_offset():
    parsed = parse_lrs_instant("2024-03-01T12:00:00+02:00")
    assert parsed == datetime(2024, 3, 1, 10, 0, 0, tzinfo=timezone.utc)


def test_parse_lrs_instant_trailing_z():
    parsed = parse_lrs_instant("2024-03-01T12:00:00Z")
    assert parsed == datetime(2024, 3, 1, 12, 0, 0, tzinfo=timezone.utc)


def test_parse_lrs_instant_unreadable():
    assert parse_lrs_instant("") is None
    assert parse_lrs_instant(None) is None
    assert parse_lrs_instant("not a date") is None