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

from app.api import audit, auth, faults, incidents, inventory, monitoring, runbooks, system, users
from app.core.clock import Clock
from app.core.config import Settings, get_settings
from app.core.errors import install_error_handlers
from app.db.base import Database
from app.services import runbooks as runbook_loader
from app.services.inventory import seed_inventory
from app.services.fault_runner import FaultRunner
from app.services.fault_ssh import FaultSSH, OpenSSHFaultClient
from app.services.login_guard import LoginGuard
from app.services.lab_checks import LabChecks, LabChecksAPI
from app.services.prometheus import PrometheusAPI, PrometheusClient
from app.services.users import ensure_bootstrap_admin


def create_app(settings: Settings | None = None, clock: Clock | None = None,
               prometheus: PrometheusAPI | None = None, fault_ssh: FaultSSH | None = None,
               lab_checks: LabChecksAPI | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        with application.state.db.SessionLocal() as db:
            ensure_bootstrap_admin(db, application.state.settings, application.state.clock)
            if application.state.settings.seed_inventory:
                seed_inventory(db)
            if application.state.settings.load_runbooks:
                try:
                    runbook_loader.load(db, runbook_loader.resolve_dir(application.state.settings.runbooks_dir),
                                        application.state.clock)
                except Exception:  # thiếu bảng hoặc thư mục: portal vẫn chạy, admin nạp lại sau
                    db.rollback()
        runner: FaultRunner = application.state.fault_runner
        try:
            runner.recover_on_startup()  # gỡ các lần chạy dở khi backend chết giữa chừng (luồng 6)
        except Exception:
            pass
        if application.state.settings.fault_background:
            runner.start_background()
        yield
        runner.stop_background()

    app = FastAPI(title="Obslab Portal API", version=settings.version, lifespan=lifespan,
                  description="Hợp đồng: docs/02-thiet-ke/api/openapi.yaml", docs_url="/api/docs",
                  openapi_url="/api/openapi.json", redoc_url=None)
    app.state.settings = settings
    app.state.clock = clock or Clock()
    app.state.db = Database(settings.database_url)
    app.state.login_guard = LoginGuard(settings.login_max_failures, settings.login_window_s, settings.login_lockout_s)
    if prometheus is None and settings.fake_prometheus:
        from app.services.fake_prometheus import SyntheticPrometheus
        prometheus = SyntheticPrometheus()
    app.state.prometheus = prometheus or PrometheusClient(settings.prometheus_url)  # test truyền bản giả
    # Chế độ xem thử (PORTAL_FAKE_PROMETHEUS=true): SSH, điều kiện đo và cảnh báo cũng giả lập -> KHÔNG BAO GIỜ gọi VM thật
    app.state.fault_simulated = bool(settings.fake_prometheus and fault_ssh is None)
    if app.state.fault_simulated:
        from app.services import alert_ingest
        from app.services.fake_faults import SimulatedFaultSSH, SimulatedLabChecks

        def deliver(payload: dict) -> None:
            with app.state.db.SessionLocal() as db:
                alert_ingest.ingest(db, payload, app.state.clock, app.state.alert_hooks)

        fault_ssh, lab_checks = SimulatedFaultSSH(app.state.clock, deliver), lab_checks or SimulatedLabChecks()
    ssh = fault_ssh or OpenSSHFaultClient(settings.lab_keys_dir, {"web": settings.vm_web_ip, "db": settings.vm_db_ip})
    app.state.fault_runner = FaultRunner(ssh, lab_checks or LabChecks(app.state.prometheus), app.state.clock,
                                         app.state.db.SessionLocal, settings.fault_resolve_wait_s)
    # Hàm gọi khi có đợt cảnh báo firing mới: khớp với lần chạy kịch bản lỗi đang hoạt động
    app.state.alert_hooks = [app.state.fault_runner.on_firing]

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
    for router in (system.router, auth.router, users.router, audit.router, inventory.hosts, inventory.services,
                   incidents.webhooks, incidents.incidents, incidents.alerts, incidents.report, runbooks.router,
                   monitoring.router, faults.faults, faults.report):
        app.include_router(router)

    # Kiểm kết nối CSDL ngay khi tạo app để lỗi cấu hình lộ sớm
    with app.state.db.engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return app


def __getattr__(name: str):  # `uvicorn app.main:app` — chỉ tạo app khi thật sự cần, không tạo lúc import trong test
    if name == "app":
        return create_app()
    raise AttributeError(name)
