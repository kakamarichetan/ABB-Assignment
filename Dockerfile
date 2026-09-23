FROM python:3.11-slim AS base
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY pyproject.toml .
RUN pip install --no-cache-dir .
COPY . .
FROM base AS alarm-api
CMD ["uvicorn","alarm_api.main:app","--host","0.0.0.0","--port","8000"]
FROM base AS alarm-mcp
CMD ["uvicorn","mcp_servers.alarm_management.http_server:app","--host","0.0.0.0","--port","9000"]
FROM base AS backend
CMD ["uvicorn","apps.backend.main:app","--host","0.0.0.0","--port","8080"]
