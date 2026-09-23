# ABB Alarm Investigation and Procedure Guidance Copilot

This repository now contains a runnable production-oriented vertical slice for the assignment.

## Architecture

React/GUI → FastAPI Copilot → MCP Client → Alarm Management MCP Server → Alarm API Simulator.

The copilot never calls the Alarm API directly. MCP is the integration boundary. The investigation first collects structured alarm evidence, then uses the resolved asset/alarm context to retrieve relevant operating and maintenance procedures through RAG. The final response exposes facts, recommendations, citations and an MCP execution trace.

## Run locally

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows: .venv\\Scripts\\activate
pip install -e ".[dev]"
python scripts/ingest_documents.py
uvicorn alarm_api.main:app --port 8000
# terminal 2
uvicorn mcp_servers.alarm_management.http_server:app --port 9000
# terminal 3
uvicorn apps.backend.main:app --port 8080
```

Example:

```bash
curl -X POST http://localhost:8080/api/chat -H "Content-Type: application/json" -d '{"message":"Investigate recurring high-severity alarms for Boiler Feed Pump 101 over the last 90 days, identify likely contributing factors, retrieve the relevant operating procedure, and provide recommended actions with source evidence."}'
```

## Docker

`docker compose up --build`

Services: Alarm API simulator `:8000`, MCP server `:9000`, Copilot backend `:8080`.

## Production considerations

- Server-side credentials only.
- MCP runtime tool discovery and typed boundaries.
- HTTP timeout and transient-network retry policy.
- Deterministic simulator data for repeatable acceptance tests.
- RAG document/section citations.
- No claim that alarm co-occurrence proves root cause.
- Health endpoints for service orchestration.
- `.env.example` and `.gitignore` prevent secret/artifact commits.

The simulator can be replaced with the real Alarm Management API without changing the copilot workflow. The RAG service is isolated so an enterprise embedding/vector backend can be introduced without changing the MCP contract.

## Assignment alignment

The implementation includes the requested MCP server, MCP client, Alarm API simulator, RAG layer, combined investigation workflow, source citations, execution trace, tests, Docker packaging and architecture documentation.
