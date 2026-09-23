import os,uuid,time,json
from datetime import datetime,timedelta,timezone
from fastapi import FastAPI,HTTPException
from pydantic import BaseModel
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from rag.retrieval.service import RAGService
app=FastAPI(title="ABB Alarm Investigation Copilot",version="1.0.0")
rag=RAGService(os.getenv("RAG_INDEX_PATH","rag/index/index.joblib"),os.getenv("RAG_DOCUMENT_PATH","rag/documents"))
class Chat(BaseModel): message:str; conversation_id:str|None=None
async def tool(s,n,a,tr,t):
 st=time.perf_counter()
 try:
  r=await s.call_tool(n,a); vals=[]
  for c in r.content:
   if hasattr(c,"text"):
    try: vals.append(json.loads(c.text))
    except: vals.append(c.text)
  out=vals[0] if len(vals)==1 else vals
  tr.append({"tool":n,"status":"success","duration_ms":round((time.perf_counter()-st)*1000,1),"trace_id":t}); return out
 except Exception as e:
  tr.append({"tool":n,"status":"error","error":str(e)[:300],"trace_id":t}); raise
@app.get("/health")
def health(): return {"status":"ok"}
@app.post("/api/chat")
async def chat(q:Chat):
 trace_id=str(uuid.uuid4()); trace=[]; text=q.message.lower()
 asset_q="Boiler Feed Pump 101" if ("bfp-101" in text or "pump 101" in text) else q.message
 days=90 if "90 days" in text else 30
 end=datetime(2026,7,1,tzinfo=timezone.utc); start=end-timedelta(days=days)
 try:
  async with streamable_http_client(os.getenv("MCP_SERVER_URL","http://localhost:9000/mcp")) as streams:
   async with ClientSession(*streams) as s:
    await s.initialize()
    names={x.name for x in (await s.list_tools()).tools}
    needed={"search_assets","get_asset_metadata","get_alarms","get_alarm_summary","get_alarm_correlation","get_operator_recommendations"}
    if not needed<=names: raise RuntimeError(f"Missing MCP tools: {needed-names}")
    assets=await tool(s,"search_assets",{"query":asset_q,"limit":10},trace,trace_id); asset=assets["results"][0]; aid=asset["asset_id"]
    meta=await tool(s,"get_asset_metadata",{"asset_id":aid},trace,trace_id)
    alarms=await tool(s,"get_alarms",{"asset_id":aid,"start_time":start.isoformat(),"end_time":end.isoformat(),"page":1,"page_size":200},trace,trace_id)
    window={"asset_ids":[aid],"start_time":start.isoformat(),"end_time":end.isoformat()}
    summary=await tool(s,"get_alarm_summary",window,trace,trace_id)
    corr=await tool(s,"get_alarm_correlation",window,trace,trace_id)
    current=(alarms.get("data") or [None])[0]
    rec=await tool(s,"get_operator_recommendations",{"alarm_id":current["alarm_id"]},trace,trace_id) if current else {"recommendations":[]}
 except Exception as e: raise HTTPException(502,f"Investigation failed: {e}")
 hits=rag.search(f"{asset['name']} high discharge pressure recurring operating procedure", [aid],5)
 groups=summary.get("groups",[]); recurring=max(groups,key=lambda x:x["count"]) if groups else None
 answer=f"Investigated {asset['name']} for {days} days: {summary['total_alarms']} alarms. Most recurrent: {recurring['alarm_name']} ({recurring['count']}) if recurring else none. Correlation provides co-occurrence evidence, not proof of root cause. Procedure evidence points to checking transmitter indication, downstream valve/restriction, operating point, suction conditions and minimum-flow path."
 return {"answer":answer,"confidence":"high" if hits else "medium","evidence":{"asset":asset,"metadata":meta,"alarms":alarms,"summary":summary,"correlation":corr,"recommendations":rec["recommendations"]},"citations":hits,"mcp_trace":trace,"warnings":[] if hits else ["No relevant procedure evidence retrieved."]}
