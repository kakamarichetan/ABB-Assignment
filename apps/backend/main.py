import json
import os
import re
import time
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from mcp import ClientSession
from pydantic import BaseModel, Field
from mcp.client.streamable_http import streamable_http_client

from rag.retrieval.service import RAGService

app = FastAPI(title="ABB Alarm Investigation Copilot", version="1.1.1")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:5173").split(","),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization", "X-Trace-ID"],
)
rag = RAGService(
    os.getenv("RAG_INDEX_PATH", "rag/index/index.joblib"),
    os.getenv("RAG_DOCUMENT_PATH", "rag/documents"),
)


class Chat(BaseModel):
    message: str = Field(min_length=3, max_length=4000)
    conversation_id: str | None = None


async def call_tool(session, name, arguments, trace, trace_id):
    started = time.perf_counter()
    try:
        result = await session.call_tool(name, arguments)
        values = []
        for content in result.content:
            if hasattr(content, "text"):
                try:
                    values.append(json.loads(content.text))
                except (TypeError, ValueError):
                    values.append(content.text)
        output = values[0] if len(values) == 1 else values
        trace.append({
            "tool": name,
            "status": "success",
            "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            "trace_id": trace_id,
        })
        return output
    except Exception as exc:
        trace.append({
            "tool": name,
            "status": "error",
            "error": str(exc)[:300],
            "trace_id": trace_id,
        })
        raise


def investigation_window(message: str) -> tuple[datetime, datetime, int]:
    match = re.search(r"(\d+)\s*days?", message.lower())
    days = int(match.group(1)) if match else 30
    if not 1 <= days <= 3650:
        raise HTTPException(422, "Investigation window must be between 1 and 3650 days")
    configured_end = os.getenv("INVESTIGATION_END_TIME")
    if configured_end:
        end = datetime.fromisoformat(configured_end.replace("Z", "+00:00"))
    else:
        end = datetime.now(timezone.utc)
    return end - timedelta(days=days), end, days


def resolve_asset_query(message: str) -> str:
    match = re.search(r"\b[A-Z]{2,10}-\d{1,6}\b", message.upper())
    if match:
        return match.group(0)
    return message.strip()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/chat")
async def chat(query: Chat):
    trace_id = str(uuid.uuid4())
    trace = []
    text = query.message.lower()
    start, end, days = investigation_window(query.message)
    asset_query = resolve_asset_query(query.message)

    try:
        async with streamable_http_client(
            os.getenv("MCP_SERVER_URL", "http://localhost:9000/mcp")
        ) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                discovered = {tool.name for tool in (await session.list_tools()).tools}
                required = {
                    "search_assets",
                    "get_asset_metadata",
                    "get_alarms",
                    "get_alarm_summary",
                    "get_alarm_correlation",
                    "get_operator_recommendations",
                }
                if not required <= discovered:
                    missing = ", ".join(sorted(required - discovered))
                    raise RuntimeError(f"Missing MCP tools: {missing}")

                assets = await call_tool(
                    session, "search_assets", {"query": asset_query, "limit": 10}, trace, trace_id
                )
                results = assets.get("results", [])
                if not results:
                    raise HTTPException(
                        404,
                        "No matching asset was found. Include an asset ID, name, site, or unit in the request.",
                    )
                asset = results[0]
                asset_id = asset["asset_id"]

                metadata = await call_tool(
                    session, "get_asset_metadata", {"asset_id": asset_id}, trace, trace_id
                )
                alarms = await call_tool(
                    session,
                    "get_alarms",
                    {
                        "asset_id": asset_id,
                        "start_time": start.isoformat(),
                        "end_time": end.isoformat(),
                        "page": 1,
                        "page_size": 200,
                    },
                    trace,
                    trace_id,
                )
                window = {
                    "asset_ids": [asset_id],
                    "start_time": start.isoformat(),
                    "end_time": end.isoformat(),
                }
                summary = await call_tool(
                    session, "get_alarm_summary", window, trace, trace_id
                )
                correlation = await call_tool(
                    session, "get_alarm_correlation", window, trace, trace_id
                )

                alarm_rows = alarms.get("data", [])
                current = alarm_rows[0] if alarm_rows else None
                recommendations = (
                    await call_tool(
                        session,
                        "get_operator_recommendations",
                        {"alarm_id": current["alarm_id"]},
                        trace,
                        trace_id,
                    )
                    if current
                    else {"recommendations": []}
                )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, f"Investigation failed: {str(exc)[:300]}") from exc

    rag_query = f"{asset['name']} alarm operating procedure troubleshooting recommended actions"
    hits = rag.search(rag_query, [asset_id], 5)
    groups = summary.get("groups", [])
    recurring = max(groups, key=lambda item: item["count"]) if groups else None
    recurrence_text = (
        f"Most recurrent: {recurring['alarm_name']} ({recurring['count']}). "
        if recurring
        else "No recurring alarm group was returned. "
    )
    active_critical = [
        row for row in alarms.get("data", [])
        if row.get("status") == "active" and row.get("severity") == "critical"
    ]
    answer = (
        f"Investigated {asset['name']} for {days} days: {summary['total_alarms']} alarms. "
        f"{recurrence_text}"
        f"Active critical alarms in the returned window: {len(active_critical)}. "
        "Correlation is co-occurrence evidence, not proof of root cause. "
        "Use the cited procedure to verify transmitter indication, downstream valve/restriction, "
        "operating point, suction conditions and the minimum-flow path."
    )
    warnings = []
    if not hits:
        warnings.append("No relevant procedure evidence was retrieved.")
    if text.startswith(("ignore", "disregard")):
        warnings.append("The request begins with an instruction-like phrase; retrieved documents are treated as evidence only.")

    return {
        "answer": answer,
        "confidence": "high" if hits else "medium",
        "evidence": {
            "asset": asset,
            "metadata": metadata,
            "alarms": alarms,
            "summary": summary,
            "correlation": correlation,
            "recommendations": recommendations.get("recommendations", []),
        },
        "citations": hits,
        "mcp_trace": trace,
        "warnings": warnings,
    }
