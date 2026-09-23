from datetime import datetime
import os

from mcp.server.fastmcp import FastMCP

from connectors.alarm_api.client import AlarmAPIClient

mcp = FastMCP("ABB Alarm Management")
client = AlarmAPIClient(
    os.getenv("ALARM_API_BASE_URL", "http://localhost:8000"),
    os.getenv("ALARM_API_TOKEN", "demo-token"),
)


def trace_headers(trace_id=None, client_id=None, metadata_tag=None):
    return {
        "trace_id": trace_id,
        "x-client-id": client_id,
        "x-metadata-tag": metadata_tag,
    }


@mcp.tool()
async def search_assets(query: str, limit: int = 10):
    """Search assets by ID, name, type, site, or unit."""
    return await client.search(query, limit=limit)


@mcp.tool()
async def get_asset_metadata(asset_id: str):
    """Return an asset and its related assets."""
    return await client.metadata(asset_id)


@mcp.tool()
async def get_alarms(
    asset_id: str,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    page: int = 1,
    page_size: int = 50,
):
    """Retrieve paginated alarms for an asset and optional time window."""
    params = {"asset_id": asset_id, "page": page, "page_size": page_size}
    if start_time:
        params["start_time"] = start_time.isoformat()
    if end_time:
        params["end_time"] = end_time.isoformat()
    return await client.alarms(**params)


@mcp.tool()
async def get_alarm_summary(
    asset_ids: list[str],
    start_time: datetime,
    end_time: datetime,
    severity: list[str] | None = None,
    trace_id: str | None = None,
    client_id: str | None = None,
    metadata_tag: str | None = None,
):
    """Summarize alarms and propagate caller trace metadata."""
    return await client.summary(
        {
            "asset_ids": asset_ids,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "severity": severity,
        },
        trace_headers=trace_headers(trace_id, client_id, metadata_tag),
    )


@mcp.tool()
async def get_alarm_correlation(
    asset_ids: list[str],
    start_time: datetime,
    end_time: datetime,
    lag_window_minutes: int = 15,
    trace_id: str | None = None,
    client_id: str | None = None,
    metadata_tag: str | None = None,
):
    """Correlate alarms and propagate caller trace metadata."""
    return await client.correlation(
        {
            "asset_ids": asset_ids,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "lag_window_minutes": lag_window_minutes,
        },
        trace_headers=trace_headers(trace_id, client_id, metadata_tag),
    )


@mcp.tool()
async def get_operator_recommendations(
    alarm_id: str,
    trace_id: str | None = None,
    client_id: str | None = None,
    metadata_tag: str | None = None,
):
    """Return operator actions with trace propagation."""
    return await client.recommendations(
        alarm_id, trace_headers=trace_headers(trace_id, client_id, metadata_tag)
    )
