"""/api/hosts, /api/services — danh mục đối tượng hiển thị trên portal (UC13, FR-P07).

Xem: operator. Thêm/sửa/xóa: admin. Danh mục chỉ quyết định portal hiển thị gì và dựng truy vấn Prometheus từ nhãn nào;
nó không thay đổi cấu hình Prometheus.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_db, require_admin, require_operator
from app.core.errors import ApiError, not_found
from app.db import models as m
from app.schemas.inventory import Host, HostInput, Service, ServiceInput
from app.services import audit
from app.services.inventory import grafana_url

hosts = APIRouter(prefix="/api/hosts", tags=["inventory"])
services = APIRouter(prefix="/api/services", tags=["inventory"])


def _service_out(request: Request, s: m.Service, host: m.Host) -> Service:
    out = Service.model_validate(s)
    out.grafana_url = grafana_url(request.app.state.settings.grafana_public_url, s.grafana_dashboard_uid,
                                  host.prom_instance, s.name)
    return out


def _host_out(request: Request, h: m.Host) -> Host:
    out = Host.model_validate(h, from_attributes=True)
    out.grafana_url = grafana_url(request.app.state.settings.grafana_public_url, h.grafana_dashboard_uid, h.prom_instance)
    out.services = [_service_out(request, s, h) for s in h.services]
    return out


def _get_host(db: Session, host_id: int) -> m.Host:
    host = db.get(m.Host, host_id)
    if host is None:
        raise not_found("host")
    return host


def _get_service(db: Session, service_id: int) -> m.Service:
    service = db.get(m.Service, service_id)
    if service is None:
        raise not_found("service")
    return service


def _diff(obj, data: dict) -> dict:
    changes = {}
    for key, value in data.items():
        if getattr(obj, key) != value:
            changes[key] = [getattr(obj, key), value]
            setattr(obj, key, value)
    return changes


# ------------------------------------------------------------------ host
@hosts.get("", response_model=list[Host])
def list_hosts(request: Request, _: m.User = Depends(require_operator), db: Session = Depends(get_db)) -> list[Host]:
    rows = db.scalars(select(m.Host).options(selectinload(m.Host.services)).order_by(m.Host.name)).all()
    return [_host_out(request, h) for h in rows]


@hosts.post("", response_model=Host, status_code=201)
def create_host(body: HostInput, request: Request, actor: m.User = Depends(require_admin),
                db: Session = Depends(get_db)) -> Host:
    if db.scalar(select(m.Host.id).where(m.Host.name == body.name)):
        raise ApiError(409, "duplicate", f"Host '{body.name}' đã tồn tại")
    host = m.Host(**body.model_dump())
    db.add(host)
    db.flush()
    audit.record(db, request, "create", actor, "host", host.id, body.model_dump())
    db.commit()
    return _host_out(request, host)


@hosts.get("/{host_id}", response_model=Host)
def get_host(host_id: int, request: Request, _: m.User = Depends(require_operator), db: Session = Depends(get_db)) -> Host:
    return _host_out(request, _get_host(db, host_id))


@hosts.patch("/{host_id}", response_model=Host)
def update_host(host_id: int, body: HostInput, request: Request, actor: m.User = Depends(require_admin),
                db: Session = Depends(get_db)) -> Host:
    host = _get_host(db, host_id)
    if body.name != host.name and db.scalar(select(m.Host.id).where(m.Host.name == body.name)):
        raise ApiError(409, "duplicate", f"Host '{body.name}' đã tồn tại")
    changes = _diff(host, body.model_dump())
    if changes:
        audit.record(db, request, "update", actor, "host", host.id, changes)
    db.commit()
    return _host_out(request, host)


@hosts.delete("/{host_id}", status_code=204)
def delete_host(host_id: int, request: Request, actor: m.User = Depends(require_admin),
                db: Session = Depends(get_db)) -> Response:
    host = _get_host(db, host_id)
    audit.record(db, request, "delete", actor, "host", host.id,
                 {"name": host.name, "services": [s.name for s in host.services]})
    db.delete(host)  # xóa kèm service (cascade); sự cố cũ giữ nguyên vì chỉ lưu tên host
    db.commit()
    return Response(status_code=204)


# ------------------------------------------------------------------ service
def _check_service(db: Session, body: ServiceInput, current: m.Service | None = None) -> m.Host:
    host = db.get(m.Host, body.host_id)
    if host is None:
        raise ApiError(422, "validation_error", "Dữ liệu không hợp lệ",
                       [{"field": "host_id", "message": "Host không tồn tại", "type": "not_found"}])
    clash = db.scalar(select(m.Service.id).where(m.Service.host_id == body.host_id, m.Service.name == body.name))
    if clash and (current is None or clash != current.id):
        raise ApiError(409, "duplicate", f"Host '{host.name}' đã có service '{body.name}'")
    return host


@services.post("", response_model=Service, status_code=201)
def create_service(body: ServiceInput, request: Request, actor: m.User = Depends(require_admin),
                   db: Session = Depends(get_db)) -> Service:
    host = _check_service(db, body)
    service = m.Service(**body.model_dump())
    db.add(service)
    db.flush()
    audit.record(db, request, "create", actor, "service", service.id, body.model_dump())
    db.commit()
    return _service_out(request, service, host)


@services.get("/{service_id}", response_model=Service)
def get_service(service_id: int, request: Request, _: m.User = Depends(require_operator),
                db: Session = Depends(get_db)) -> Service:
    service = _get_service(db, service_id)
    return _service_out(request, service, service.host)


@services.patch("/{service_id}", response_model=Service)
def update_service(service_id: int, body: ServiceInput, request: Request, actor: m.User = Depends(require_admin),
                   db: Session = Depends(get_db)) -> Service:
    service = _get_service(db, service_id)
    host = _check_service(db, body, service)
    changes = _diff(service, body.model_dump())
    if changes:
        audit.record(db, request, "update", actor, "service", service.id, changes)
    db.commit()
    db.refresh(service)
    return _service_out(request, service, host)


@services.delete("/{service_id}", status_code=204)
def delete_service(service_id: int, request: Request, actor: m.User = Depends(require_admin),
                   db: Session = Depends(get_db)) -> Response:
    service = _get_service(db, service_id)
    audit.record(db, request, "delete", actor, "service", service.id, {"name": service.name, "host_id": service.host_id})
    db.delete(service)
    db.commit()
    return Response(status_code=204)
