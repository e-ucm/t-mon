from datetime import datetime, timezone

from SimvaBrowser.SimvaBrowser import (
    SimvaBrowser,
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


class _FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self.payload = payload
        self.text = text

    def json(self):
        return self.payload


def _bare_browser():
    """A browser with only the fields the participant-count call needs."""
    browser = SimvaBrowser.__new__(SimvaBrowser)
    browser.simva_api_url = "https://simva.example/"
    browser.simlet_endpoint = "simlets"
    browser.jwt = "a-token"
    browser.ca_file = None
    browser.health_ok = True
    browser.accepted_studies = []
    browser.simlet_directories = []
    return browser


def test_participants_count_uses_the_groups_endpoint(monkeypatch):
    browser = _bare_browser()
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return _FakeResponse(payload={"count": 3})

    monkeypatch.setattr("SimvaBrowser.SimvaBrowser.requests.get", fake_get)
    assert browser._load_simlet_participants_count(1) == 3
    url, kwargs = calls[0]
    assert url == "https://simva.example/simlets/1/groups/participants/count"
    assert kwargs["headers"]["Authorization"] == "Bearer a-token"
    assert kwargs["verify"] is None


def test_participants_count_accepts_bare_grouped_and_enveloped_numbers(monkeypatch):
    browser = _bare_browser()
    for payload, expected in (
        (4, 4),
        ("7", 7),
        ({"participants": 2}, 2),
        ({"data": {"count": 5}}, 5),
        # The endpoint reports a count per group; the tile shows their total.
        ({"1": 1, "2": 5}, 6),
        ({}, 0),
    ):
        monkeypatch.setattr(
            "SimvaBrowser.SimvaBrowser.requests.get",
            lambda url, **kwargs: _FakeResponse(payload=payload))
        assert browser._load_simlet_participants_count(1) == expected


def test_studies_list_gets_grouped_participant_total(monkeypatch):
    browser = _bare_browser()
    studies = [{"simlet_id": 1, "simlet_name": "test", "groups": [1, 2]}]

    def fake_get(url, **kwargs):
        if url.endswith("/groups/participants/count"):
            return _FakeResponse(payload={"1": 1, "2": 5})
        return _FakeResponse(payload=studies)

    monkeypatch.setattr("SimvaBrowser.SimvaBrowser.requests.get", fake_get)
    browser._load_selected_studies_from_simva_api()
    assert browser.accepted_studies[0]["participants_count"] == 6


def test_participants_count_failure_does_not_break_the_studies_list(monkeypatch):
    browser = _bare_browser()
    studies = [{"simlet_id": 1, "simlet_name": "test"}]

    def fake_get(url, **kwargs):
        if url.endswith("/groups/participants/count"):
            return _FakeResponse(status_code=500, text="boom")
        return _FakeResponse(payload=studies)

    monkeypatch.setattr("SimvaBrowser.SimvaBrowser.requests.get", fake_get)
    browser._load_selected_studies_from_simva_api()
    assert browser.accepted_studies[0]["participants_count"] == 0
    assert browser.simlet_directories[0]["id"] == "1/"