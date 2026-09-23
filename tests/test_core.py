from fastapi.testclient import TestClient
from alarm_api.main import app
def test_health(): assert TestClient(app).get("/health").status_code==200
def test_asset_search(): assert TestClient(app).get("/assets/search",params={"query":"BFP-101"},headers={"Authorization":"Bearer demo-token"}).json()["count"]==1
def test_summary():
 r=TestClient(app).post("/alarms/summary",headers={"Authorization":"Bearer demo-token"},json={"asset_ids":["BFP-101"],"start_time":"2026-04-01T00:00:00Z","end_time":"2026-07-01T00:00:00Z"})
 assert r.status_code==200 and r.json()["total_alarms"]>0
