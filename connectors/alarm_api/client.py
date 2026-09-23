import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential


def retryable(exc):
    if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
        return exc.response.status_code in {429, 500, 502, 503, 504}
    return False


class AlarmAPIClient:
    def __init__(self, base_url: str, token: str, timeout_seconds: float = 10):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout_seconds = timeout_seconds

    @retry(
        retry=retry_if_exception(retryable),
        wait=wait_exponential(min=0.2, max=2),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def request(self, method, path, trace_headers=None, **kwargs):
        headers = {"Authorization": f"Bearer {self.token}"}
        if trace_headers:
            headers.update({key: value for key, value in trace_headers.items() if value})
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.request(
                method, self.base_url + path, headers=headers, **kwargs
            )
            if response.status_code in {429, 500, 502, 503, 504}:
                response.raise_for_status()
            response.raise_for_status()
            return response.json()

    async def search(self, q, **params):
        return await self.request("GET", "/assets/search", params={"query": q, **params})

    async def metadata(self, asset_id):
        return await self.request("GET", f"/assets/{asset_id}/metadata")

    async def alarms(self, **params):
        return await self.request("GET", "/alarms", params=params)

    async def summary(self, payload, trace_headers=None):
        return await self.request("POST", "/alarms/summary", json=payload, trace_headers=trace_headers)

    async def trends(self, payload):
        return await self.request("POST", "/alarms/trends", json=payload)

    async def correlation(self, payload, trace_headers=None):
        return await self.request(
            "POST", "/alarms/correlation", json=payload, trace_headers=trace_headers
        )

    async def recommendations(self, alarm_id, trace_headers=None):
        return await self.request(
            "POST",
            "/recommendations/operator-actions",
            json={"alarm_id": alarm_id},
            trace_headers=trace_headers,
        )
