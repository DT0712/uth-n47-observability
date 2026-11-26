"""Tạo ứng dụng FastAPI.

  uvicorn app.main:app --reload            # chạy thử trên Windows (SQLite, dữ liệu giả)

create_app() nhận Settings/Clock để test dựng app riêng với CSDL trong bộ nhớ và đồng hồ giả.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, generate_latest
from sqlalchemy import text

from app.api import audit, auth, inventory, system, users
from app.core.clock import Clock
from app.core.config import Settings, get_settings
from app.core.errors import install_error_handlers
from app.db.base import Database
from app.services.inventory import seed_inventory
from app.services.users import ensure_bootstrap_admin


def create_app(settings: Settings | None = None, clock: Clock | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        with application.state.db.SessionLocal() as db:
            ensure_bootstrap_admin(db, application.state.settings, application.state.clock)
            if application.state.settings.seed_inventory:
                seed_inventory(db)
        yield

    app = FastAPI(title="Obslab Portal API", version=settings.version, lifespan=lifespan,
                  description="Hợp đồng: docs/02-thiet-ke/api/openapi.yaml", docs_url="/api/docs",
                  openapi_url="/api/openapi.json", redoc_url=None)
    app.state.settings = settings
    app.state.clock = clock or Clock()
    app.state.db = Database(settings.database_url)

    # Metric riêng của portal (NFR-13); registry riêng để nhiều app trong test không đụng nhau
    registry = CollectorRegistry()
    requests_total = Counter("portal_http_requests_total", "Số request HTTP", ["method", "status"], registry=registry)
    app.state.metrics_registry = registry

    @app.middleware("http")
    async def _count(request, call_next):
        response = await call_next(request)
        requests_total.labels(request.method, str(response.status_code)).inc()
        return response

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)

    install_error_handlers(app)
    for router in (system.router, auth.router, users.router, audit.router, inventory.hosts, inventory.services):
        app.include_router(router)

    # Kiểm kết nối CSDL ngay khi tạo app để lỗi cấu hình lộ sớm
    with app.state.db.engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return app


def __getattr__(name: str):  # `uvicorn app.main:app` — chỉ tạo app khi thật sự cần, không tạo lúc import trong test
    if name == "app":
        return create_app()
    raise AttributeError(name)
