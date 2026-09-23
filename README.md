# ABB Alarm Investigation & Procedure Guidance Copilot

A production-oriented, runnable implementation of the ABB alarm-investigation assignment.

The solution demonstrates an end-to-end industrial alarm investigation workflow:

**React UI → FastAPI Copilot → MCP Client → Alarm Management MCP Server → Alarm API Simulator**

The Copilot does **not** call the Alarm API directly. MCP is the integration boundary. The workflow first collects structured alarm evidence, then uses the resolved asset/alarm context to retrieve relevant operating and maintenance procedures through RAG, and finally returns a grounded response with evidence, citations, recommendations and an MCP execution trace.

---

## 1. What this repository contains

| Component | Location | Purpose |
|---|---|---|
| Alarm API Simulator | `alarm_api/` | Deterministic REST API representing the source alarm system |
| Alarm API Connector | `connectors/alarm_api/` | HTTP client, authentication, timeout and retry handling |
| MCP Server | `mcp_servers/alarm_management/` | Exposes alarm capabilities as MCP tools |
| Copilot Backend | `apps/backend/` | Orchestrates investigation and grounded response generation |
| RAG | `rag/retrieval/` | Procedure/maintenance retrieval with asset-aware filtering |
| Procedure documents | `rag/documents/` | Sample operating and maintenance evidence |
| Frontend | `apps/frontend/` | React/Vite investigation UI |
| Tests | `tests/` | API, edge-case, RAG and MCP registration tests |
| CI | `.github/workflows/ci.yml` | Lint, tests, Docker builds and frontend build |
| Architecture docs | `docs/` | Detailed architecture, RAG design and MCP catalog |

---

## 2. High-level architecture

```text
                           ┌──────────────────────┐
                           │     React / Vite     │
                           │   Investigation UI   │
                           └──────────┬───────────┘
                                      │ HTTP
                                      ▼
                           ┌──────────────────────┐
                           │ FastAPI Copilot      │
                           │ /api/chat            │
                           │ Orchestration        │
                           └──────────┬───────────┘
                                      │ MCP
                                      ▼
                           ┌──────────────────────┐
                           │ Alarm Management MCP │
                           │ Server :9000/mcp     │
                           └──────────┬───────────┘
                                      │ REST
                                      ▼
                           ┌──────────────────────┐
                           │ Alarm API Simulator   │
                           │ :8000                 │
                           └──────────┬───────────┘
                                      │
                         structured alarm evidence
                                      │
                                      ▼
                           ┌──────────────────────┐
                           │ RAG Retrieval Layer   │
                           │ procedures/manuals    │
                           └──────────┬───────────┘
                                      │
                                      ▼
                           grounded response
                    + facts + recommendations + citations
                    + MCP execution trace + warnings
```

### Important design principle

The browser never receives or owns source-system credentials.

The dependency direction is:

```text
UI
 ↓
Copilot
 ↓
MCP
 ↓
Alarm API
```

This keeps the source-system integration behind a controlled MCP boundary and makes it possible to replace the simulator with the real Alarm Management API later.

---

## 3. End-to-end investigation flow

For a request such as:

> Investigate recurring high-severity alarms for Boiler Feed Pump 101 over the last 90 days.

the backend performs approximately this sequence:

1. Validate the incoming request.
2. Resolve the asset using `search_assets`.
3. Fetch asset metadata using `get_asset_metadata`.
4. Retrieve paginated alarm history using `get_alarms`.
5. Calculate recurrence/summary using `get_alarm_summary`.
6. Calculate alarm co-occurrence using `get_alarm_correlation`.
7. Retrieve source-system operator recommendations for the latest relevant alarm.
8. Build an evidence-aware RAG query from the resolved asset/alarm context.
9. Retrieve relevant procedure/manual sections.
10. Return:
   - investigation answer
   - confidence
   - structured alarm evidence
   - operator recommendations
   - document citations
   - MCP execution trace
   - warnings where evidence is incomplete

**Correlation is treated as co-occurrence evidence, not proof of root cause.**

---

## 4. Repository structure

```text
ABB-Assignment/
├── alarm_api/
│   └── main.py
├── apps/
│   ├── backend/
│   │   └── main.py
│   └── frontend/
│       ├── src/
│       ├── package.json
│       ├── vite.config.ts
│       └── Dockerfile
├── connectors/
│   └── alarm_api/
│       └── client.py
├── mcp_servers/
│   └── alarm_management/
│       ├── server.py
│       └── http_server.py
├── rag/
│   ├── documents/
│   │   ├── bfp101_operating_procedure.md
│   │   └── pump_maintenance_manual.md
│   └── retrieval/
│       └── service.py
├── scripts/
│   └── ingest_documents.py
├── tests/
│   ├── test_core.py
│   └── test_rag.py
├── docs/
│   ├── architecture.md
│   ├── rag-design.md
│   └── mcp-tool-catalog.md
├── .env.example
├── docker-compose.yml
├── Dockerfile
└── pyproject.toml
```

---

## 5. Prerequisites

### Local Python execution

- Python 3.11+
- pip
- Node.js/npm if you want to run the React UI
- Git

### Docker execution

- Docker
- Docker Compose

Docker is the easiest way to start the complete stack.

---

# 6. Option A — Run everything with Docker

From the repository root:

```bash
docker compose up --build
```

Services:

| Service | URL | Purpose |
|---|---|---|
| Alarm API | http://localhost:8000 | Source-system simulator |
| MCP Server | http://localhost:9000/mcp | MCP integration boundary |
| Copilot Backend | http://localhost:8080 | Investigation API |
| React UI | http://localhost:5173 | Browser interface |

Stop the stack:

```bash
docker compose down
```

Rebuild from scratch:

```bash
docker compose down
docker compose build --no-cache
docker compose up
```

---

# 7. Option B — Run backend services locally

Create a virtual environment.

### Windows

```powershell
python -m venv .venv
.venv\Scripts\activate
```

### Linux/macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the project:

```bash
pip install -e ".[dev]"
```

Create the RAG index:

```bash
python scripts/ingest_documents.py
```

You should see the document ingestion complete and the index written under:

```text
rag/index/index.joblib
```

Start the Alarm API:

```bash
uvicorn alarm_api.main:app --host 0.0.0.0 --port 8000
```

Start MCP in another terminal:

```bash
uvicorn mcp_servers.alarm_management.http_server:app --host 0.0.0.0 --port 9000
```

Start the Copilot backend in another terminal:

```bash
uvicorn apps.backend.main:app --host 0.0.0.0 --port 8080
```

---

# 8. Environment configuration

Example configuration is available in `.env.example`.

```text
ALARM_API_BASE_URL=http://localhost:8000
ALARM_API_TOKEN=demo-token
MCP_SERVER_URL=http://localhost:9000/mcp
RAG_DOCUMENT_PATH=rag/documents
RAG_INDEX_PATH=rag/index/index.joblib
```

For Docker, the same connectivity is configured automatically by `docker-compose.yml`.

For a real deployment:

- replace `demo-token`
- use a secret manager
- do not commit credentials
- configure the real Alarm Management API URL
- configure production CORS origins
- configure an enterprise RAG backend if required

---

# 9. Health checks

### Alarm API

```bash
curl http://localhost:8000/health
```

Expected:

```json
{"status":"ok"}
```

### Copilot

```bash
curl http://localhost:8080/health
```

Expected:

```json
{"status":"ok"}
```

The MCP service is exposed through its MCP HTTP endpoint.

---

# 10. Test the Alarm API directly

The simulator uses:

```text
Authorization: Bearer demo-token
```

### Search for BFP-101

```bash
curl "http://localhost:8000/assets/search?query=BFP-101" \
  -H "Authorization: Bearer demo-token"
```

Representative response:

```json
{
  "results": [
    {
      "asset_id": "BFP-101",
      "name": "Boiler Feed Pump 101",
      "site": "EastRefinery",
      "unit": "Unit 2",
      "type": "boiler_feed_pump",
      "criticality": "critical"
    }
  ],
  "count": 1
}
```

### Retrieve asset metadata

```bash
curl "http://localhost:8000/assets/BFP-101/metadata" \
  -H "Authorization: Bearer demo-token"
```

This returns the asset plus related equipment such as BFP-102 and COND-101.

### Retrieve alarms

```bash
curl "http://localhost:8000/alarms?asset_id=BFP-101&page=1&page_size=10" \
  -H "Authorization: Bearer demo-token"
```

The response contains:

- alarm ID
- asset ID
- alarm name
- severity
- status
- start/end time
- duration
- pagination metadata

---

# 11. Alarm analytics endpoints

The simulator supports:

```text
GET  /alarms
GET  /alarms/{alarm_id}

POST /alarms/summary
POST /alarms/trends
POST /alarms/correlation
POST /alarms/flood-analysis
POST /alarms/rationalization-candidates
POST /alarms/priority-score

POST /recommendations/operator-actions

POST /calculation-code/generate
POST /calculation-code/execute

GET  /analytics/kpi-definitions
```

These endpoints cover the assignment's alarm investigation and analytics scenarios.

---

# 12. MCP tools

The MCP server exposes these primary investigation tools:

| Tool | Purpose |
|---|---|
| `search_assets` | Resolve asset by ID, name, type, site or unit |
| `get_asset_metadata` | Retrieve asset and related equipment |
| `get_alarms` | Retrieve paginated alarm history |
| `get_alarm_summary` | Calculate alarm counts and recurrence |
| `get_alarm_correlation` | Calculate co-occurrence relationships |
| `get_operator_recommendations` | Retrieve recommended operator actions |

The Copilot validates the MCP tool catalog at runtime before beginning the investigation.

This prevents silent operation when an expected integration capability is missing.

---

# 13. RAG implementation

The current RAG implementation is deliberately self-contained.

### Retrieval flow

```text
Alarm evidence
     ↓
resolved asset ID
     ↓
alarm terminology
     ↓
procedure query
     ↓
TF-IDF retrieval
     ↓
asset-aware filtering
     ↓
document/section citation
```

Documents are Markdown files under:

```text
rag/documents/
```

The ingestion script sections the documents and creates a persisted index.

Run:

```bash
python scripts/ingest_documents.py
```

The RAG service preserves asset IDs as metadata and returns citations in the form:

```text
document — section
```

### Why TF-IDF?

It keeps the assignment:

- deterministic
- offline-capable
- inexpensive
- easy to reproduce
- free from external model/API credentials

The retrieval abstraction is isolated so an enterprise deployment can replace it with:

```text
BM25 + dense embeddings + vector database + reranker
```

without changing the MCP contract or Copilot workflow.

---

# 14. Complete Copilot example

Request:

```bash
curl -X POST http://localhost:8080/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Investigate recurring high-severity alarms for Boiler Feed Pump 101 over the last 90 days, identify likely contributing factors, retrieve the relevant operating procedure, and provide recommended actions with source evidence."
  }'
```

Representative response structure:

```json
{
  "answer": "Investigated Boiler Feed Pump 101 for 90 days: ...",
  "confidence": "high",
  "evidence": {
    "asset": {},
    "metadata": {},
    "alarms": {},
    "summary": {},
    "correlation": {},
    "recommendations": []
  },
  "citations": [
    {
      "document": "bfp101_operating_procedure.md",
      "section": "High Discharge Pressure"
    }
  ],
  "mcp_trace": [
    {
      "tool": "search_assets",
      "status": "success",
      "duration_ms": 10.2,
      "trace_id": "..."
    },
    {
      "tool": "get_asset_metadata",
      "status": "success",
      "duration_ms": 8.4,
      "trace_id": "..."
    },
    {
      "tool": "get_alarms",
      "status": "success",
      "duration_ms": 11.7,
      "trace_id": "..."
    },
    {
      "tool": "get_alarm_summary",
      "status": "success",
      "duration_ms": 9.8,
      "trace_id": "..."
    },
    {
      "tool": "get_alarm_correlation",
      "status": "success",
      "duration_ms": 9.2,
      "trace_id": "..."
    }
  ],
  "warnings": []
}
```

The exact counts/timestamps can change when the investigation window is based on the current time; the simulator itself uses deterministic alarm data.

---

# 15. Example investigation interpretation

For BFP-101, the simulator intentionally contains recurring:

```text
High Discharge Pressure
Low Suction Pressure
```

The RAG procedure provides evidence around checks such as:

- transmitter indication verification
- downstream valve/restriction checks
- operating-point verification
- suction conditions
- minimum-flow path

The application does **not** convert correlation into a confirmed root cause.

This distinction is important for an industrial copilot because the system should distinguish:

```text
Observed fact
     ≠
Statistical/co-occurrence relationship
     ≠
Confirmed root cause
```

---

# 16. Edge cases covered by tests

The automated test suite covers more than the happy path.

Examples include:

### Authentication

Missing/invalid bearer token:

```text
401 Unauthorized
```

### Unknown asset

```text
404 Asset not found
```

### Unknown alarm

```text
404 Alarm not found
```

### Pagination

Tests verify:

- page number
- page size
- total count
- returned record count

### Invalid pagination

```text
page_size=0
→ 422
```

### Invalid sorting

Unsupported `sort_by` values return validation errors.

### Active critical alarms

The simulator contains deterministic active critical alarm cases to test current-state investigations.

### Time-range validation

Invalid ranges where:

```text
start_time > end_time
```

are rejected.

### Investigation-window validation

The Copilot rejects unreasonable investigation periods above 3650 days.

### Empty asset search

The Copilot returns a meaningful 404-style investigation error instead of silently producing an empty answer.

### RAG filtering

Retrieved evidence is checked against the requested asset.

### MCP registration

Tests verify that the required MCP tools are actually registered.

### Transient HTTP failures

The connector retries:

```text
429
500
502
503
504
timeouts
network failures
```

with exponential backoff.

---

# 17. Run the automated test suite

Install development dependencies:

```bash
pip install -e ".[dev]"
```

Run:

```bash
pytest -q
```

Current verified CI result:

```text
18 passed, 1 warning
```

Run linting:

```bash
ruff check .
```

Build containers:

```bash
docker build --target alarm-api -t abb-alarm-api .
docker build --target alarm-mcp -t abb-alarm-mcp .
docker build --target backend -t abb-backend .
```

Build the frontend:

```bash
cd apps/frontend
npm install
npm run build
```

---

# 18. CI/CD verification

GitHub Actions executes:

```text
1. Checkout
2. Python 3.11 setup
3. Install package + dev dependencies
4. RAG ingestion
5. Ruff
6. Pytest
7. Alarm API Docker build
8. MCP Docker build
9. Backend Docker build
10. Frontend production build
```

The latest verified workflow completed successfully.

Verified result:

```text
pytest: 18 passed
ruff: passed
Alarm API container: passed
MCP container: passed
Backend container: passed
Frontend build: passed
```

---

# 19. Production hardening already included

The implementation includes:

- typed Pydantic request models
- API input validation
- bearer authentication on simulator APIs
- server-side credentials
- HTTP timeouts
- transient HTTP retry handling
- MCP tool discovery validation
- structured MCP execution trace
- trace propagation to the Alarm API
- deterministic simulator data
- RAG citations
- asset-aware retrieval
- health endpoints
- Docker packaging
- Compose orchestration
- configurable CORS
- automated tests
- CI validation
- frontend production build
- separation between UI, orchestration, MCP and source-system integration

---

# 20. Security considerations

For a real production deployment, replace the demonstration authentication with enterprise identity and authorization.

Recommended controls:

- OAuth2/OIDC or enterprise SSO
- short-lived service credentials
- AWS Secrets Manager / Azure Key Vault / Vault
- TLS between services
- network segmentation
- API gateway
- RBAC
- audit logging
- rate limiting
- request-size limits
- PII/secret redaction
- centralized observability
- immutable audit trails

Never place `ALARM_API_TOKEN` in browser-side JavaScript.

---

# 21. Replacing the simulator with the real Alarm API

The simulator is intentionally isolated.

The main integration boundary is:

```text
connectors/alarm_api/client.py
```

The production migration path is:

```text
Current:
MCP → AlarmAPIClient → simulator

Production:
MCP → AlarmAPIClient → real Alarm Management API
```

The Copilot/MCP contract can remain unchanged.

Configure:

```text
ALARM_API_BASE_URL=<real API>
ALARM_API_TOKEN=<secret>
```

and replace/adjust the connector authentication and endpoint mapping as required by the real API.

---

# 22. Extending RAG for enterprise production

The current abstraction can be upgraded to:

```text
Document ingestion
      ↓
Chunking
      ↓
BM25 sparse retrieval
      +
Dense embedding retrieval
      ↓
Weighted/hybrid fusion
      ↓
Reranker
      ↓
Asset/metadata filtering
      ↓
Grounded answer generation
```

Possible enterprise components include:

- OpenSearch
- Elasticsearch
- pgvector
- Pinecone
- Milvus
- Weaviate
- enterprise embedding models
- cross-encoder reranking

The important architectural constraint is to keep retrieval behind the RAG service interface so the MCP contract does not change.

---

# 23. Observability

The MCP trace returned by the backend provides a request-level view of:

- tool name
- success/error status
- duration
- trace ID

For a production deployment, extend this with:

```text
OpenTelemetry
Prometheus metrics
centralized structured logs
distributed tracing
request correlation IDs
latency/error dashboards
alarm investigation audit events
```

Useful metrics include:

- investigation latency
- MCP tool latency
- Alarm API error rate
- RAG retrieval latency
- empty retrieval rate
- number of alarms investigated
- active critical alarms detected
- recommendation retrieval failures

---

# 24. API documentation

When the services are running, FastAPI provides interactive documentation.

Alarm API:

```text
http://localhost:8000/docs
```

Copilot backend:

```text
http://localhost:8080/docs
```

OpenAPI JSON:

```text
http://localhost:8000/openapi.json
http://localhost:8080/openapi.json
```

These are useful for testing individual endpoints without the frontend.

---

# 25. Troubleshooting

### Port already in use

Check:

```text
8000 → Alarm API
9000 → MCP
8080 → Copilot
5173 → React UI
```

Stop the conflicting process or change the published Docker port.

### RAG index missing

Run:

```bash
python scripts/ingest_documents.py
```

### MCP connection failure

Verify:

```text
Alarm API → http://localhost:8000
MCP → http://localhost:9000/mcp
```

and ensure both services are running.

### Docker networking

Inside Compose, services must use service names rather than `localhost`.

For example:

```text
MCP → http://alarm-api:8000
Backend → http://alarm-mcp:9000/mcp
```

### Frontend cannot call backend

Verify:

```text
VITE_API_BASE_URL=http://localhost:8080
CORS_ALLOW_ORIGINS=http://localhost:5173
```

---

# 26. Assignment mapping

| Assignment capability | Implementation |
|---|---|
| Alarm API integration | `connectors/alarm_api` |
| Alarm API simulator | `alarm_api` |
| MCP server | `mcp_servers/alarm_management` |
| MCP client | Copilot backend |
| Asset search | `search_assets` |
| Alarm retrieval | `get_alarms` |
| Alarm summary | `get_alarm_summary` |
| Alarm correlation | `get_alarm_correlation` |
| Operator actions | `get_operator_recommendations` |
| Procedure retrieval | RAG |
| Source citations | RAG response |
| Investigation orchestration | `apps/backend/main.py` |
| GUI | React/Vite |
| Containerization | Docker + Compose |
| Automated testing | Pytest |
| Static validation | Ruff |
| CI | GitHub Actions |

---

# 27. Design decisions worth explaining in an interview

### Why MCP?

MCP creates a controlled tool boundary between the AI orchestration layer and enterprise systems. It avoids coupling the Copilot directly to every source-system API.

### Why RAG after alarm retrieval?

The alarm context provides the equipment and failure terminology needed to retrieve the most relevant operating procedure. This is more targeted than performing generic document retrieval first.

### Why deterministic simulator data?

It makes automated acceptance testing reproducible. Every test run sees known assets, alarms, timestamps and scenarios.

### Why not claim root cause?

Alarm correlation identifies relationships/co-occurrence. It does not establish causality. An industrial copilot should explicitly distinguish evidence from inference.

### Why isolate the RAG layer?

The current TF-IDF implementation is lightweight and deterministic, while the interface allows production replacement with hybrid sparse+dense retrieval and a vector store.

### Why return an MCP trace?

It makes the Copilot explainable from an integration perspective. Reviewers can see which tools were called and whether each operation succeeded.

---

# 28. Quick-start checklist

For the fastest evaluation:

```bash
git clone https://github.com/kakamarichetan/ABB-Assignment.git
cd ABB-Assignment

docker compose up --build
```

Then open:

```text
React UI:
http://localhost:5173

Copilot API:
http://localhost:8080/docs

Alarm API:
http://localhost:8000/docs
```

Run the automated tests separately if required:

```bash
pip install -e ".[dev]"
python scripts/ingest_documents.py
pytest -q
```

Expected verified result:

```text
18 passed, 1 warning
```

---

## 29. Current verification status

The repository has been executed through the GitHub CI pipeline after the latest fixes.

Verified:

- Python dependency installation
- RAG ingestion
- Ruff
- Pytest
- 18 automated tests
- Alarm API Docker build
- MCP Docker build
- Copilot Docker build
- Frontend production build

**Latest verified CI status: SUCCESS.**

Repository:

https://github.com/kakamarichetan/ABB-Assignment
