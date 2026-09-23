from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator

app = FastAPI(title="ABB Alarm API Simulator", version="1.2.0")
TOKEN = "demo-token"

ASSETS = [
    {"asset_id": "BFP-101", "name": "Boiler Feed Pump 101", "site": "EastRefinery", "unit": "Unit 2",
     "type": "boiler_feed_pump", "criticality": "critical", "related_asset_ids": ["BFP-102", "COND-101"]},
    {"asset_id": "BFP-102", "name": "Boiler Feed Pump 102", "site": "EastRefinery", "unit": "Unit 2",
     "type": "boiler_feed_pump", "criticality": "critical", "related_asset_ids": ["BFP-101", "COND-101"]},
    {"asset_id": "COMP-201", "name": "Compressor 201", "site": "EastRefinery", "unit": "Unit 3",
     "type": "compressor", "criticality": "high", "related_asset_ids": ["MOTOR-201"]},
    {"asset_id": "MOTOR-201", "name": "Compressor Motor 201", "site": "EastRefinery", "unit": "Unit 3",
     "type": "motor", "criticality": "high", "related_asset_ids": ["COMP-201"]},
    {"asset_id": "COND-101", "name": "Condenser 101", "site": "EastRefinery", "unit": "Unit 2",
     "type": "condenser", "criticality": "high", "related_asset_ids": ["BFP-101", "BFP-102"]},
]
BASE = datetime(2026, 7, 1, tzinfo=timezone.utc)
ALARMS: list[dict[str, Any]] = []
CALCULATIONS: dict[str, dict[str, Any]] = {}


def add(asset, name, severity, hours, duration, status="cleared"):
    start = BASE - timedelta(hours=hours)
    end = start + timedelta(minutes=duration)
    ALARMS.append({
        "alarm_id": f"A{len(ALARMS) + 1:04d}",
        "asset_id": asset,
        "alarm_name": name,
        "severity": severity,
        "status": status,
        "start_time": start.isoformat(),
        "end_time": None if status == "active" else end.isoformat(),
        "duration_seconds": None if status == "active" else duration * 60,
    })


for hours in [6, 24, 72, 168, 240, 336, 480, 600, 720, 840, 1000, 1200, 1400, 1600, 1750, 1900]:
    add("BFP-101", "High Discharge Pressure", "critical" if hours % 3 == 0 else "high", hours, 18)
for hours in [3, 48, 144]:
    add("BFP-101", "Low Suction Pressure", "critical", hours, 9)
add("BFP-101", "High Discharge Pressure", "critical", 1, 0, "active")
for hours in [8, 36, 180]:
    add("BFP-102", "High Discharge Pressure", "high", hours, 20)
add("BFP-102", "High Discharge Pressure", "critical", 2, 0, "active")
for hours in [8, 36, 180]:
    add("COMP-201", "High Discharge Pressure", "high", hours, 20)
for hours in [12, 48, 120]:
    add("MOTOR-201", "Motor Trip", "critical", hours, 5)
for hours in [18, 60, 180]:
    add("COND-101", "High Condenser Pressure", "high", hours, 15)


class TimeRange(BaseModel):
    start_time: datetime
    end_time: datetime


class QueryModel(BaseModel):
    model_config = ConfigDict(extra="allow")
    asset_ids: list[str] = Field(default_factory=list)
    start_time: datetime | None = None
    end_time: datetime | None = None
    time_range: TimeRange | None = None
    severity: list[str] | None = None
    site: str | None = None
    unit: str | None = None

    @model_validator(mode="after")
    def normalize_time_range(self):
        if self.time_range:
            self.start_time = self.time_range.start_time
            self.end_time = self.time_range.end_time
        if self.start_time is None or self.end_time is None:
            raise ValueError("start_time/end_time or time_range is required")
        if self.start_time > self.end_time:
            raise ValueError("start_time must be before end_time")
        return self


class CorrelationModel(QueryModel):
    lag_window_minutes: int = Field(default=15, ge=1, le=1440)
    min_support: int = Field(default=1, ge=1)
    severity_threshold: str | None = None
    correlation_method: str = "cooccurrence"


class TrendsModel(QueryModel):
    bucket: str = "daily"
    metrics: list[str] = Field(default_factory=lambda: ["alarm_count"])


class FloodModel(BaseModel):
    model_config = ConfigDict(extra="allow")
    unit: str | None = None
    site: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    time_range: TimeRange | None = None
    threshold_count: int = Field(default=10, ge=1)
    rolling_window_minutes: int = Field(default=10, ge=1, le=1440)

    @model_validator(mode="after")
    def normalize_time_range(self):
        if self.time_range:
            self.start_time = self.time_range.start_time
            self.end_time = self.time_range.end_time
        if self.start_time is None or self.end_time is None:
            raise ValueError("start_time/end_time or time_range is required")
        return self


class RationalizationModel(QueryModel):
    recurrence_threshold: int = Field(default=5, ge=1)
    stale_minutes_threshold: int = Field(default=180, ge=1)


class Priority(BaseModel):
    alarm_id: str


class CalculationGenerate(BaseModel):
    calculation_type: str
    filters: dict[str, Any] = Field(default_factory=dict)


class CalculationExecute(BaseModel):
    calculation_id: str
    filters: dict[str, Any] = Field(default_factory=dict)


def auth(authorization: str | None):
    if authorization != f"Bearer {TOKEN}":
        raise HTTPException(401, "Invalid bearer token")


def trace_metadata(trace_id: str | None, client_id: str | None, metadata_tag: str | None):
    return {
        "trace_id": trace_id,
        "x_client_id": client_id,
        "x_metadata_tag": metadata_tag,
    }


def asset_map():
    return {asset["asset_id"]: asset for asset in ASSETS}


def filtered_rows(
    asset_ids=None,
    start_time=None,
    end_time=None,
    severity=None,
    site=None,
    unit=None,
    status=None,
):
    amap = asset_map()
    return [
        alarm for alarm in ALARMS
        if (not asset_ids or alarm["asset_id"] in asset_ids)
        and (not start_time or datetime.fromisoformat(alarm["start_time"]) >= start_time)
        and (not end_time or datetime.fromisoformat(alarm["start_time"]) <= end_time)
        and (not severity or alarm["severity"] in severity)
        and (not site or amap[alarm["asset_id"]]["site"].lower().replace(" ", "") == site.lower().replace(" ", ""))
        and (not unit or amap[alarm["asset_id"]]["unit"].lower() == unit.lower())
        and (not status or alarm["status"] == status)
    ]


def common_trace(
    trace_id: str | None, client_id: str | None, metadata_tag: str | None
):
    return trace_metadata(trace_id, client_id, metadata_tag)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/assets/search")
def asset_search(
    query: str,
    limit: int = Query(10, ge=1, le=100),
    unit: str | None = None,
    site: str | None = None,
    authorization: str | None = Header(None),
):
    auth(authorization)
    q = query.lower()
    normalized_q = q.replace(" ", "")
    results = [
        asset for asset in ASSETS
        if (q in asset["name"].lower() or q in asset["asset_id"].lower()
            or q in asset["type"].lower() or normalized_q in asset["site"].lower().replace(" ", "") or q in asset["unit"].lower())
        and (not unit or asset["unit"].lower() == unit.lower())
        and (not site or asset["site"].lower() == site.lower())
    ][:limit]
    return {"results": results, "count": len(results)}


@app.get("/assets/{asset_id}/metadata")
def metadata(asset_id: str, authorization: str | None = Header(None)):
    auth(authorization)
    asset = next((x for x in ASSETS if x["asset_id"] == asset_id), None)
    if not asset:
        raise HTTPException(404, "Asset not found")
    related = [x for x in ASSETS if x["asset_id"] in asset["related_asset_ids"]]
    return {"asset": asset, "related_assets": related}


@app.get("/alarms")
def alarms(
    asset_id: str | None = None,
    site: str | None = None,
    unit: str | None = None,
    status: str | None = None,
    severity: list[str] | None = Query(None),
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    sort_by: str = Query("start_time"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    authorization: str | None = Header(None),
):
    auth(authorization)
    if sort_by not in {"start_time", "severity", "alarm_name"}:
        raise HTTPException(422, "Unsupported sort_by")
    rows = filtered_rows([asset_id] if asset_id else None, start_time, end_time, severity, site, unit, status)
    if sort_by == "severity":
        rank = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        rows.sort(key=lambda x: rank.get(x["severity"], 0), reverse=sort_order == "desc")
    else:
        rows.sort(key=lambda x: x[sort_by], reverse=sort_order == "desc")
    offset = (page - 1) * page_size
    return {
        "data": rows[offset:offset + page_size],
        "pagination": {"page": page, "page_size": page_size, "total": len(rows)},
    }


@app.get("/alarms/{alarm_id}")
def alarm(alarm_id: str, authorization: str | None = Header(None)):
    auth(authorization)
    found = next((x for x in ALARMS if x["alarm_id"] == alarm_id), None)
    if not found:
        raise HTTPException(404, "Alarm not found")
    return found


@app.post("/alarms/summary")
def summary(
    request: QueryModel,
    trace_id: str | None = Header(None, alias="trace_id"),
    x_client_id: str | None = Header(None),
    x_metadata_tag: str | None = Header(None),
    authorization: str | None = Header(None),
):
    auth(authorization)
    rows = filtered_rows(
        request.asset_ids, request.start_time, request.end_time, request.severity,
        request.site, request.unit
    )
    groups = Counter(row["alarm_name"] for row in rows)
    return {
        "total_alarms": len(rows),
        "groups": [{"alarm_name": name, "count": count} for name, count in groups.items()],
        "kpis": {
            "alarm_count": len(rows),
            "recurring_rate": round(sum(v > 1 for v in groups.values()) / len(groups), 3) if groups else 0,
            "avg_ack_delay": 0,
        },
        "trace": common_trace(trace_id, x_client_id, x_metadata_tag),
    }


@app.post("/alarms/trends")
def trends(
    request: TrendsModel,
    authorization: str | None = Header(None),
):
    auth(authorization)
    rows = filtered_rows(
        request.asset_ids, request.start_time, request.end_time, request.severity,
        request.site, request.unit
    )
    bucket_minutes = {"hourly": 60, "daily": 1440, "weekly": 10080}.get(request.bucket)
    if not bucket_minutes:
        raise HTTPException(422, "bucket must be hourly, daily, or weekly")
    counts = Counter()
    for row in rows:
        timestamp = datetime.fromisoformat(row["start_time"])
        minutes = int(timestamp.timestamp() // 60)
        bucket_start = minutes - minutes % bucket_minutes
        counts[datetime.fromtimestamp(bucket_start * 60, tz=timezone.utc).isoformat()] += 1
    series = [{"timestamp": key, "alarm_count": counts[key]} for key in sorted(counts)]
    return {"bucket": request.bucket, "metrics": request.metrics, "series": series}


@app.post("/alarms/correlation")
def correlation(
    request: CorrelationModel,
    trace_id: str | None = Header(None),
    x_client_id: str | None = Header(None),
    x_metadata_tag: str | None = Header(None),
    authorization: str | None = Header(None),
):
    auth(authorization)
    rows = filtered_rows(
        request.asset_ids, request.start_time, request.end_time, request.severity,
        request.site, request.unit
    )
    groups = Counter(row["alarm_name"] for row in rows)
    names = list(groups)
    pairs = [
        {"alarm_a": names[i], "alarm_b": names[j], "support": min(groups[names[i]], groups[names[j]])}
        for i in range(len(names)) for j in range(i + 1, len(names))
        if min(groups[names[i]], groups[names[j]]) >= request.min_support
    ]
    return {
        "correlations": pairs,
        "method": request.correlation_method,
        "lag_window_minutes": request.lag_window_minutes,
        "trace": common_trace(trace_id, x_client_id, x_metadata_tag),
    }


@app.post("/alarms/flood-analysis")
def flood_analysis(request: FloodModel, authorization: str | None = Header(None)):
    auth(authorization)
    rows = filtered_rows(start_time=request.start_time, end_time=request.end_time, site=request.site, unit=request.unit)
    rows.sort(key=lambda x: x["start_time"])
    windows = []
    window = timedelta(minutes=request.rolling_window_minutes)
    for row in rows:
        start = datetime.fromisoformat(row["start_time"])
        end = start + window
        count = sum(start <= datetime.fromisoformat(candidate["start_time"]) <= end for candidate in rows)
        if count >= request.threshold_count:
            windows.append({"start": start.isoformat(), "end": end.isoformat(), "count": count})
    unique = {(x["start"], x["end"]): x for x in windows}
    return {"flood_windows": list(unique.values()), "threshold_count": request.threshold_count}


@app.post("/alarms/rationalization-candidates")
def rationalization(
    request: RationalizationModel,
    authorization: str | None = Header(None),
):
    auth(authorization)
    rows = filtered_rows(
        request.asset_ids, request.start_time, request.end_time, request.severity,
        request.site, request.unit
    )
    counts = Counter(row["alarm_name"] for row in rows)
    candidates = [
        {
            "alarm_name": name,
            "recurrence_count": count,
            "reason": "High recurrence; review against alarm philosophy and operating need.",
        }
        for name, count in counts.items() if count >= request.recurrence_threshold
    ]
    return {"candidates": candidates, "threshold": request.recurrence_threshold}


@app.post("/alarms/priority-score")
def priority(request: Priority, authorization: str | None = Header(None)):
    auth(authorization)
    found = next((alarm for alarm in ALARMS if alarm["alarm_id"] == request.alarm_id), None)
    if not found:
        raise HTTPException(404, "Alarm not found")
    recurrence = sum(
        alarm["asset_id"] == found["asset_id"] and alarm["alarm_name"] == found["alarm_name"]
        for alarm in ALARMS
    )
    score = min(
        100,
        {"critical": 50, "high": 35, "medium": 20, "low": 5}[found["severity"]]
        + min(30, recurrence * 2)
        + (20 if found["status"] == "active" else 0),
    )
    return {
        "alarm_id": found["alarm_id"],
        "priority_score": score,
        "priority_band": "critical" if score >= 80 else "high" if score >= 50 else "medium",
        "recurrence_count": recurrence,
    }


@app.post("/recommendations/operator-actions")
def recommendations(
    request: Priority,
    trace_id: str | None = Header(None),
    x_client_id: str | None = Header(None),
    x_metadata_tag: str | None = Header(None),
    authorization: str | None = Header(None),
):
    auth(authorization)
    found = next((alarm for alarm in ALARMS if alarm["alarm_id"] == request.alarm_id), None)
    if not found:
        raise HTTPException(404, "Alarm not found")
    return {
        "alarm_id": found["alarm_id"],
        "recommendations": [
            "Verify transmitter against local gauge.",
            "Confirm downstream valve alignment and restrictions.",
            "Check pump operating point, suction conditions and minimum-flow path.",
            "Escalate persistent critical conditions using the approved site procedure.",
        ],
        "trace": common_trace(trace_id, x_client_id, x_metadata_tag),
    }


@app.post("/calculation-code/generate")
def calculation_generate(request: CalculationGenerate, authorization: str | None = Header(None)):
    auth(authorization)
    calculation_id = f"CAL-{len(CALCULATIONS) + 1:04d}"
    CALCULATIONS[calculation_id] = {
        "calculation_id": calculation_id,
        "calculation_type": request.calculation_type,
        "filters": request.filters,
    }
    return {
        "calculation_id": calculation_id,
        "calculation_type": request.calculation_type,
        "code": "SAFE_SERVER_SIDE_CALCULATION_TEMPLATE",
        "status": "generated",
    }


@app.post("/calculation-code/execute")
def calculation_execute(request: CalculationExecute, authorization: str | None = Header(None)):
    auth(authorization)
    calculation = CALCULATIONS.get(request.calculation_id)
    if not calculation:
        raise HTTPException(404, "Calculation not found")
    filters = {**calculation["filters"], **request.filters}
    start = datetime.fromisoformat(filters["start_time"].replace("Z", "+00:00"))
    end = datetime.fromisoformat(filters["end_time"].replace("Z", "+00:00"))
    rows = filtered_rows(start_time=start, end_time=end, site=filters.get("site"), unit=filters.get("unit"))
    return {
        "calculation_id": request.calculation_id,
        "calculation_type": calculation["calculation_type"],
        "result": {"alarm_count": len(rows), "unique_assets": len({x["asset_id"] for x in rows})},
        "status": "completed",
    }


@app.get("/analytics/kpi-definitions")
def kpi_definitions(authorization: str | None = Header(None)):
    auth(authorization)
    return {
        "definitions": [
            {"name": "alarm_count", "description": "Number of alarms in the selected window."},
            {"name": "recurring_rate", "description": "Fraction of alarm groups occurring more than once."},
            {"name": "avg_ack_delay", "description": "Average acknowledgement delay in seconds; simulator returns 0."},
        ]
    }
