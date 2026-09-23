from datetime import datetime,timedelta,timezone
from fastapi import FastAPI,Header,HTTPException,Query
from pydantic import BaseModel
app=FastAPI(title="ABB Alarm API Simulator",version="1.0.0")
TOKEN="demo-token"
ASSETS=[
{"asset_id":"BFP-101","name":"Boiler Feed Pump 101","site":"East Refinery","unit":"Unit 2","type":"boiler_feed_pump","criticality":"critical","related_asset_ids":["BFP-102","COND-101"]},
{"asset_id":"BFP-102","name":"Boiler Feed Pump 102","site":"East Refinery","unit":"Unit 2","type":"boiler_feed_pump","criticality":"critical","related_asset_ids":["BFP-101","COND-101"]},
{"asset_id":"COMP-201","name":"Compressor 201","site":"East Refinery","unit":"Unit 3","type":"compressor","criticality":"high","related_asset_ids":["MOTOR-201"]},
{"asset_id":"MOTOR-201","name":"Compressor Motor 201","site":"East Refinery","unit":"Unit 3","type":"motor","criticality":"high","related_asset_ids":["COMP-201"]},
{"asset_id":"COND-101","name":"Condenser 101","site":"East Refinery","unit":"Unit 2","type":"condenser","criticality":"high","related_asset_ids":["BFP-101","BFP-102"]}]
BASE=datetime(2026,7,1,tzinfo=timezone.utc)
ALARMS=[]
def add(asset,name,severity,hours,duration,status="cleared"):
 s=BASE-timedelta(hours=hours); e=s+timedelta(minutes=duration)
 ALARMS.append({"alarm_id":f"A{len(ALARMS)+1:04d}","asset_id":asset,"alarm_name":name,"severity":severity,"status":status,"start_time":s.isoformat(),"end_time":None if status=="active" else e.isoformat(),"duration_seconds":None if status=="active" else duration*60})
for h in [6,24,72,168,240,336,480,600,720,840,1000,1200,1400,1600,1750,1900]: add("BFP-101","High Discharge Pressure","critical" if h%3==0 else "high",h,18)
for h in [3,48,144]: add("BFP-101","Low Suction Pressure","critical",h,9)
add("BFP-101","High Discharge Pressure","critical",1,0,"active")
for h in [8,36,180]: add("BFP-102","High Discharge Pressure","high",h,20)
add("BFP-102","High Discharge Pressure","critical",2,0,"active")
class Summary(BaseModel):
 asset_ids:list[str]; start_time:datetime; end_time:datetime; severity:list[str]|None=None
class Correlation(BaseModel):
 asset_ids:list[str]; start_time:datetime; end_time:datetime; lag_window_minutes:int=15
class Priority(BaseModel): alarm_id:str
def auth(a): 
 if a!=f"Bearer {TOKEN}": raise HTTPException(401,"Invalid bearer token")
def rows(ids,start,end,severity=None):
 return [x for x in ALARMS if x["asset_id"] in ids and start<=datetime.fromisoformat(x["start_time"])<=end and (not severity or x["severity"] in severity)]
@app.get("/health")
def health(): return {"status":"ok"}
@app.get("/assets/search")
def asset_search(query:str,limit:int=10,authorization:str|None=Header(None)):
 auth(authorization); q=query.lower()
 r=[x for x in ASSETS if q in x["name"].lower() or q in x["asset_id"].lower() or q in x["type"].lower() or q in x["site"].lower() or q in x["unit"].lower()][:limit]
 return {"results":r,"count":len(r)}
@app.get("/assets/{asset_id}/metadata")
def metadata(asset_id:str,authorization:str|None=Header(None)):
 auth(authorization); a=next((x for x in ASSETS if x["asset_id"]==asset_id),None)
 if not a: raise HTTPException(404,"Asset not found")
 return {"asset":a,"related_assets":[x for x in ASSETS if x["asset_id"] in a["related_asset_ids"]]}
@app.get("/alarms")
def alarms(asset_id:str,start_time:datetime|None=None,end_time:datetime|None=None,page:int=Query(1,ge=1),page_size:int=Query(50,ge=1,le=200),authorization:str|None=Header(None)):
 auth(authorization); r=ALARMS
 if asset_id:r=[x for x in r if x["asset_id"]==asset_id]
 if start_time:r=[x for x in r if datetime.fromisoformat(x["start_time"])>=start_time]
 if end_time:r=[x for x in r if datetime.fromisoformat(x["start_time"])<=end_time]
 r=sorted(r,key=lambda x:x["start_time"],reverse=True); s=(page-1)*page_size
 return {"data":r[s:s+page_size],"pagination":{"page":page,"page_size":page_size,"total":len(r)}}
@app.get("/alarms/{alarm_id}")
def alarm(alarm_id:str,authorization:str|None=Header(None)):
 auth(authorization); a=next((x for x in ALARMS if x["alarm_id"]==alarm_id),None)
 if not a: raise HTTPException(404,"Alarm not found")
 return a
@app.post("/alarms/summary")
def summary(x:Summary,authorization:str|None=Header(None)):
 auth(authorization); r=rows(x.asset_ids,x.start_time,x.end_time,x.severity); groups={}
 for a in r: groups[a["alarm_name"]]=groups.get(a["alarm_name"],0)+1
 return {"total_alarms":len(r),"groups":[{"alarm_name":k,"count":v} for k,v in groups.items()],"kpis":{"alarm_count":len(r),"recurring_rate":round(sum(v>1 for v in groups.values())/len(groups),3) if groups else 0}}
@app.post("/alarms/correlation")
def correlation(x:Correlation,authorization:str|None=Header(None)):
 auth(authorization); r=rows(x.asset_ids,x.start_time,x.end_time); groups={}
 for a in r: groups.setdefault(a["alarm_name"],0); groups[a["alarm_name"]]+=1
 names=list(groups); pairs=[{"alarm_a":names[i],"alarm_b":names[j],"support":min(groups[names[i]],groups[names[j]])} for i in range(len(names)) for j in range(i+1,len(names))]
 return {"correlations":pairs,"method":"cooccurrence","lag_window_minutes":x.lag_window_minutes}
@app.post("/alarms/priority-score")
def priority(x:Priority,authorization:str|None=Header(None)):
 auth(authorization); a=next((x for x in ALARMS if x["alarm_id"]==x.alarm_id),None)
 if not a: raise HTTPException(404,"Alarm not found")
 n=sum(y["asset_id"]==a["asset_id"] and y["alarm_name"]==a["alarm_name"] for y in ALARMS)
 score=min(100,{"critical":50,"high":35,"medium":20,"low":5}[a["severity"]]+min(30,n*2)+(20 if a["status"]=="active" else 0))
 return {"alarm_id":a["alarm_id"],"priority_score":score,"priority_band":"critical" if score>=80 else "high" if score>=50 else "medium","recurrence_count":n}
@app.post("/recommendations/operator-actions")
def recommendations(x:Priority,authorization:str|None=Header(None)):
 auth(authorization); a=next((x for x in ALARMS if x["alarm_id"]==x.alarm_id),None)
 if not a: raise HTTPException(404,"Alarm not found")
 return {"alarm_id":a["alarm_id"],"recommendations":["Verify transmitter against local gauge.","Confirm downstream valve alignment and restrictions.","Check pump operating point, suction conditions and minimum-flow path.","Escalate persistent critical conditions using the approved site procedure."]}
