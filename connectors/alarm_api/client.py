import httpx
from tenacity import retry,retry_if_exception_type,wait_exponential,stop_after_attempt
class AlarmAPIClient:
 def __init__(self,base_url,token): self.base_url=base_url.rstrip("/"); self.token=token
 @retry(retry=retry_if_exception_type((httpx.TimeoutException,httpx.NetworkError)),wait=wait_exponential(min=.2,max=2),stop=stop_after_attempt(3),reraise=True)
 async def request(self,method,path,**kwargs):
  async with httpx.AsyncClient(timeout=10) as c:
   r=await c.request(method,self.base_url+path,headers={"Authorization":f"Bearer {self.token}"},**kwargs)
   r.raise_for_status(); return r.json()
 async def search(self,q): return await self.request("GET","/assets/search",params={"query":q})
 async def metadata(self,i): return await self.request("GET",f"/assets/{i}/metadata")
 async def alarms(self,**p): return await self.request("GET","/alarms",params=p)
 async def summary(self,p): return await self.request("POST","/alarms/summary",json=p)
 async def correlation(self,p): return await self.request("POST","/alarms/correlation",json=p)
 async def recommendations(self,i): return await self.request("POST","/recommendations/operator-actions",json={"alarm_id":i})
