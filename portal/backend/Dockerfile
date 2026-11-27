# portal-api (kien-truc-portal.md §2): FastAPI một tiến trình uvicorn, CSDL PostgreSQL trong Compose của VM monitor.
# Build từ monitor/docker-compose.yml (context = portal/backend).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
# openssh-client: gọi obslab-fault trên VM web/db (ADR-0007)
RUN apt-get update && apt-get install -y --no-install-recommends openssh-client && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY alembic.ini .
COPY migrations ./migrations
COPY app ./app
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod 0755 /usr/local/bin/docker-entrypoint.sh

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"
ENTRYPOINT ["docker-entrypoint.sh"]
# --proxy-headers: IP người dùng trong audit lấy từ X-Forwarded-For do portal-web (Nginx) gắn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
