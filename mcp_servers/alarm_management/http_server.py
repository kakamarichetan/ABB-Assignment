from fastapi import FastAPI
from .server import mcp
app=FastAPI(title="ABB MCP Server")
@app.get("/health")
def health(): return {"status":"ok"}
app.mount("/mcp",mcp.streamable_http_app())
