from fastapi.testclient import TestClient

from alarm_api.main import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer demo-token"}


def test_health():
    assert client.get("/health").status_code == 200


def test_asset_search_exact_and_site():
    exact = client.get("/assets/search", params={"query": "BFP-101"}, headers=AUTH)
    site = client.get("/assets/search", params={"query": "East Refinery"}, headers=AUTH)
    assert exact.json()["count"] == 1
    assert site.json()["count"] >= 1


def test_authentication_and_unknown_asset():
    assert client.get("/assets/search", params={"query": "BFP-101"}).status_code == 401
    assert client.get("/assets/NOPE/metadata", headers=AUTH).status_code == 404


def test_alarm_pagination_and_validation():
    response = client.get(
        "/alarms",
        params={"asset_id": "BFP-101", "page": 1, "page_size": 2},
        headers=AUTH,
    )
    assert response.status_code == 200
    assert len(response.json()["data"]) == 2
    assert response.json()["pagination"]["total"] > 2
    assert client.get("/alarms", params={"page_size": 0}, headers=AUTH).status_code == 422


def test_active_critical_alarm_for_bfp102():
    response = client.get(
        "/alarms",
        params={"asset_id": "BFP-102", "page_size": 200},
        headers=AUTH,
    )
    assert any(
        alarm["status"] == "active" and alarm["severity"] == "critical"
        for alarm in response.json()["data"]
    )


def test_summary_severity_filter():
    response = client.post(
        "/alarms/summary",
        headers=AUTH,
        json={
            "asset_ids": ["BFP-101"],
            "start_time": "2026-04-01T00:00:00Z",
            "end_time": "2026-07-01T00:00:00Z",
            "severity": ["critical"],
        },
    )
    assert response.status_code == 200
    assert response.json()["total_alarms"] > 0
    assert all(
        group["count"] > 0 for group in response.json()["groups"]
    )


def test_correlation_priority_and_recommendations():
    window = {
        "asset_ids": ["BFP-101"],
        "start_time": "2026-04-01T00:00:00Z",
        "end_time": "2026-07-01T00:00:00Z",
    }
    correlation = client.post("/alarms/correlation", headers=AUTH, json=window)
    assert correlation.status_code == 200
    assert correlation.json()["method"] == "cooccurrence"

    alarm_id = client.get(
        "/alarms", params={"asset_id": "BFP-101", "page_size": 1}, headers=AUTH
    ).json()["data"][0]["alarm_id"]
    priority = client.post(
        "/alarms/priority-score", headers=AUTH, json={"alarm_id": alarm_id}
    )
    recommendations = client.post(
        "/recommendations/operator-actions",
        headers=AUTH,
        json={"alarm_id": alarm_id},
    )
    assert priority.status_code == 200
    assert 0 <= priority.json()["priority_score"] <= 100
    assert recommendations.status_code == 200
    assert recommendations.json()["recommendations"]


def test_unknown_alarm_is_not_silent():
    assert client.get("/alarms/NOPE", headers=AUTH).status_code == 404
    assert client.post(
        "/alarms/priority-score", headers=AUTH, json={"alarm_id": "NOPE"}
    ).status_code == 404


def test_postman_nested_summary_trends_and_trace():
    payload = {
        "asset_ids": ["BFP-101"],
        "time_range": {
            "start_time": "2026-05-01T00:00:00Z",
            "end_time": "2026-07-01T00:00:00Z",
        },
        "severity": ["high", "critical"],
        "group_by": ["alarm_name"],
        "kpis": ["alarm_count", "recurring_rate", "avg_ack_delay"],
    }
    summary = client.post(
        "/alarms/summary",
        headers={**AUTH, "trace_id": "trace-test", "x-client-id": "pytest", "x-metadata-tag": "edge"},
        json=payload,
    )
    assert summary.status_code == 200
    assert summary.json()["trace"]["trace_id"] == "trace-test"
    trends = client.post(
        "/alarms/trends",
        headers=AUTH,
        json={**payload, "bucket": "daily", "metrics": ["alarm_count", "avg_ack_delay"]},
    )
    assert trends.status_code == 200
    assert trends.json()["series"]


def test_postman_advanced_endpoints():
    time_range = {
        "start_time": "2026-05-01T00:00:00Z",
        "end_time": "2026-07-01T00:00:00Z",
    }
    flood = client.post(
        "/alarms/flood-analysis",
        headers=AUTH,
        json={"unit": "Unit 2", "time_range": time_range, "threshold_count": 10, "rolling_window_minutes": 10},
    )
    rationalization = client.post(
        "/alarms/rationalization-candidates",
        headers=AUTH,
        json={"asset_ids": ["BFP-101"], "time_range": time_range, "recurrence_threshold": 5},
    )
    assert flood.status_code == 200
    assert "flood_windows" in flood.json()
    assert rationalization.status_code == 200
    assert "candidates" in rationalization.json()


def test_postman_calculation_and_kpi_endpoints():
    generated = client.post(
        "/calculation-code/generate",
        headers=AUTH,
        json={
            "calculation_type": "alarm_flood_index",
            "filters": {
                "unit": "Unit 3",
                "start_time": "2026-05-01T00:00:00Z",
                "end_time": "2026-07-01T00:00:00Z",
            },
        },
    )
    assert generated.status_code == 200
    calculation_id = generated.json()["calculation_id"]
    executed = client.post(
        "/calculation-code/execute",
        headers=AUTH,
        json={
            "calculation_id": calculation_id,
            "filters": {
                "unit": "Unit 3",
                "start_time": "2026-05-01T00:00:00Z",
                "end_time": "2026-07-01T00:00:00Z",
            },
        },
    )
    assert executed.status_code == 200
    assert executed.json()["status"] == "completed"
    assert client.get("/analytics/kpi-definitions", headers=AUTH).status_code == 200


def test_postman_alarm_query_filters_and_sorting():
    response = client.get(
        "/alarms",
        params={
            "site": "EastRefinery",
            "status": "active",
            "sort_by": "start_time",
            "sort_order": "desc",
            "page_size": 50,
        },
        headers=AUTH,
    )
    assert response.status_code == 200
    assert response.json()["data"]
    assert all(row["status"] == "active" for row in response.json()["data"])
