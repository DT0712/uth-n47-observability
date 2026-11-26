"""/api/overview, /api/overview/series, /api/hosts/{id}/metrics, /api/services/{id}/metrics, /api/thresholds."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_operator
from app.core.errors import ApiError, not_found
from app.db import models as m
from app.services import monitoring as mon
from app.services.prometheus import PrometheusError

router = APIRouter(tags=["monitoring"])


def _prom(request: Request):
    return request.app.state.prometheus


@router.get("/api/overview")
def overview(request: Request, host: str | None = None, service: str | None = None,
             _: m.User = Depends(require_operator), db: Session = Depends(get_db)) -> dict:
    """Trang tổng quan (FR-P03). Prometheus lỗi vẫn trả 200 với metrics_available=false."""
    return mon.overview(db, _prom(request), request.app.state.clock.now(),
                        request.app.state.settings.grafana_public_url, host, service)


@router.get("/api/overview/series")
def overview_series(request: Request, range: Literal["1h", "6h", "24h"] = "1h", host: str | None = None,  # noqa: A002
                    service: str | None = None, _: m.User = Depends(require_operator),
                    db: Session = Depends(get_db)) -> dict:
    return mon.overview_series(db, _prom(request), request.app.state.clock.now(), range, host, service)


@router.get("/api/hosts/{host_id}/metrics")
def host_metrics(host_id: int, request: Request, range: Literal["15m", "1h", "6h", "24h", "7d"] = "1h",  # noqa: A002
                 start: datetime | None = None, end: datetime | None = None,
                 metrics: str | None = Query(None, description="cpu,memory,disk,network_rx,network_tx"),
                 _: m.User = Depends(require_operator), db: Session = Depends(get_db)) -> dict:
    host = db.get(m.Host, host_id)
    if host is None:
        raise not_found("host")
    names = [x.strip() for x in metrics.split(",") if x.strip()] if metrics else list(mon.HOST_METRICS)
    bad = [x for x in names if x not in mon.HOST_METRICS]
    if bad:
        raise ApiError(422, "validation_error", "Dữ liệu không hợp lệ",
                       [{"field": "metrics", "message": f"Không có chỉ số {bad}; chọn trong {list(mon.HOST_METRICS)}",
                         "type": "enum"}])
    w = mon.window(request.app.state.clock.now(), range, start, end)
    try:
        return mon.host_metrics(_prom(request), host, w, names)
    except PrometheusError as e:
        raise mon.unavailable(e) from None


@router.get("/api/services/{service_id}/metrics")
def service_metrics(service_id: int, request: Request, range: Literal["15m", "1h", "6h", "24h", "7d"] = "1h",  # noqa: A002
                    start: datetime | None = None, end: datetime | None = None,
                    _: m.User = Depends(require_operator), db: Session = Depends(get_db)) -> dict:
    service = db.get(m.Service, service_id)
    if service is None:
        raise not_found("service")
    w = mon.window(request.app.state.clock.now(), range, start, end)
    try:
        return mon.service_metrics(_prom(request), service, w)
    except PrometheusError as e:
        raise mon.unavailable(e) from None


@router.get("/api/thresholds")
def thresholds(request: Request, _: m.User = Depends(require_operator)) -> list[dict]:
    try:
        return mon.thresholds(_prom(request))
    except PrometheusError as e:
        raise mon.unavailable(e) from None
