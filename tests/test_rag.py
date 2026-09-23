from datetime import datetime, timezone

from apps.backend.main import investigation_window, resolve_asset_query
from rag.retrieval.service import RAGService


def test_rag_returns_procedure(tmp_path):
    service = RAGService(str(tmp_path / "index.joblib"), "rag/documents")
    service.ingest()
    hits = service.search("BFP-101 high discharge pressure operating procedure", ["BFP-101"])
    assert hits
    assert "High Discharge Pressure" in hits[0]["section"]


def test_rag_filters_to_requested_asset(tmp_path):
    service = RAGService(str(tmp_path / "index.joblib"), "rag/documents")
    service.ingest()
    hits = service.search("maintenance procedure", ["BFP-101"], 10)
    assert all(
        not hit["asset_ids"] or "BFP-101" in hit["asset_ids"]
        for hit in hits
    )


def test_asset_query_resolution():
    assert resolve_asset_query("investigate BFP-102 alarms") == "BFP-102"
    assert resolve_asset_query("investigate Boiler Feed Pump 101") == "investigate Boiler Feed Pump 101"


def test_investigation_window_parsing(monkeypatch):
    monkeypatch.setenv("INVESTIGATION_END_TIME", "2026-07-01T00:00:00Z")
    start, end, days = investigation_window("show recurring alarms for 90 days")
    assert days == 90
    assert end == datetime(2026, 7, 1, tzinfo=timezone.utc)
    assert (end - start).days == 90


def test_investigation_window_rejects_unreasonable_range():
    try:
        investigation_window("show alarms for 5000 days")
    except Exception as exc:
        assert "3650" in str(exc)
    else:
        raise AssertionError("Expected range validation to fail")
