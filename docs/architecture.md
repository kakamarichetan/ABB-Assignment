# Architecture

Browser → FastAPI Copilot → MCP Client → Alarm MCP Server → Alarm API.

RAG is downstream of alarm evidence: resolved asset IDs, alarm type and recurrence form the retrieval query. The final response exposes alarm facts, recommendations, citations and MCP trace. Credentials never reach the browser.