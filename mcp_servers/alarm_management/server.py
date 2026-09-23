from mcp.server.fastmcp import FastMCP
from connectors.alarm_api.client import AlarmAPIClient
from datetime import datetime
import os
mcp=FastMCP("ABB Alarm Management")
c=AlarmAPIClient(os.getenv("ALARM_API_BASE_URL","http://localhost:8000"),os.getenv("ALARM_API_TOKEN","demo-token"))
@mcp.tool()
async def search_assets(query:str,limit:int=10): return await c.search(query)
@mcp.tool()
async def get_asset_metadata(asset_id:str): return await c.metadata(asset_id)
@mcp.tool()
async def get_alarms(asset_id:str,start_time:datetime|None=None,end_time:datetime|None=None,page:int=1,page_size:int=50):
 p={"asset_id":asset_id,"page":page,"page_size":page_size}
 if start_time:p["start_time"]=start_time.isoformat()
 if end_time:p["end_time"]=end_time.isoformat()
 return await c.alarms(**p)
@mcp.tool()
async def get_alarm_summary(asset_ids:list[str],start_time:datetime,end_time:datetime,severity:list[str]|None=None):
 return await c.summary({"asset_ids":asset_ids,"start_time":start_time.isoformat(),"end_time":end_time.isoformat(),"severity":severity})
@mcp.tool()
async def get_alarm_correlation(asset_ids:list[str],start_time:datetime,end_time:datetime,lag_window_minutes:int=15):
 return await c.correlation({"asset_ids":asset_ids,"start_time":start_time.isoformat(),"end_time":end_time.isoformat(),"lag_window_minutes":lag_window_minutes})
@mcp.tool()
async def get_operator_recommendations(alarm_id:str): return await c.recommendations(alarm_id)
