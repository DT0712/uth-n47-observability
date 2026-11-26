"""/api/incidents, /api/alerts, /api/webhooks/alertmanager, /api/reports/false-positives (UC05–UC09, UC12; FR-P08–FR-P10)."""

from __future__ import annotations

import hmac
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, Query, Request
from pydantic import ValidationError
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.api.deps import bearer_token, get_db, require_operator
from app.core.errors import ApiError, not_found
from app.db import models as m
from app.schemas.common import Page, PageParams
from app.schemas.incidents import (
    AlertEpisode,
    CloseIn,
    FalsePositiveIn,
    FalsePositiveReport,
    IncidentDetail,
    IncidentEvent,
    IncidentSummary,
    NoteIn,
    RunbookRef,
    WebhookResult,
)
from app.services import alert_ingest
from app.services import incidents as svc
from app.services.inventory import grafana_url

incidents = APIRouter(prefix="/api/incidents", tags=["incidents"])
alerts = APIRouter(prefix="/api/alerts", tags=["incidents"])
webhooks = APIRouter(prefix="/api/webhooks", tags=["webhooks"])
report = APIRouter(prefix="/api/reports", tags=["incidents"])

STATUSES = {"open", "acknowledged", "closed"}
SEVERITY_ORDER = case({"critical": 0, "warning": 1, "info": 2}, value=m.Incident.severity, else_=3)


# ------------------------------------------------------------------ webhook
def require_webhook_token(request: Request) -> None:
    """Token chia sẻ với Alertmanager (NFR-05), so sánh hằng thời gian. Chạy trước khi xét payload."""
    token = bearer_token(request) or ""
    if not hmac.compare_digest(token.encode(), request.app.state.settings.webhook_token.encode()):
        raise ApiError(401, "invalid_webhook_token", "Token webhook không hợp lệ", headers={"WWW-Authenticate": "Bearer"})


@webhooks.post("/alertmanager", response_model=WebhookResult, dependencies=[Depends(require_webhook_token)])
def alertmanager_webhook(request: Request, payload: dict[str, Any] = Body(...),
                         db: Session = Depends(get_db)) -> WebhookResult:
    try:
        result = alert_ingest.ingest(db, payload, request.app.state.clock, request.app.state.alert_hooks)
    except ValidationError as e:
        details = [{"field": ".".join(str(p) for p in err["loc"]), "message": err["msg"], "type": err["type"]}
                   for err in e.errors()]
        raise ApiError(422, "validation_error", "Payload không đúng định dạng webhook Alertmanager v4", details) from None
    return WebhookResult(**{k: getattr(result, k) for k in WebhookResult.model_fields})


# ------------------------------------------------------------------ chuyển đổi ra schema
def _usernames(db: Session, ids: set[int | None]) -> dict[int, str]:
    ids = {i for i in ids if i}
    return dict(db.execute(select(m.User.id, m.User.username).where(m.User.id.in_(ids))).all()) if ids else {}


def _detail(db: Session, request: Request, inc: m.Incident) -> IncidentDetail:
    db.refresh(inc)
    summary = svc.summaries(db, [inc])[0]
    names = _usernames(db, {inc.acknowledged_by, inc.closed_by} | {e.user_id for e in inc.events})
    runbook = db.scalar(select(m.Runbook).where(m.Runbook.alertname == inc.alertname))
    host = db.scalar(select(m.Host).where(m.Host.name == inc.host)) if inc.host else None
    return IncidentDetail(
        **summary.model_dump(), acknowledged_by=names.get(inc.acknowledged_by), closed_by=names.get(inc.closed_by),
        false_positive_reason=inc.false_positive_reason, conclusion=inc.conclusion, can_close=svc.can_close(inc),
        episodes=[AlertEpisode.model_validate(e) for e in inc.episodes],
        events=[IncidentEvent(id=e.id, at=e.at, user=names.get(e.user_id), type=e.type, content=e.content,
                              data=e.data if e.type == "fault_run" else None)
                for e in inc.events],
        runbook=RunbookRef.model_validate(runbook, from_attributes=True) if runbook else None,
        grafana_url=grafana_url(request.app.state.settings.grafana_public_url, host.grafana_dashboard_uid,
                                host.prom_instance) if host else None,
    )


# ------------------------------------------------------------------ sự cố
@incidents.get("", response_model=Page[IncidentSummary])
def list_incidents(
    status: str | None = Query(None, description="Nhiều giá trị: open,acknowledged"),
    firing: bool | None = None, severity: str | None = None, host: str | None = None, service: str | None = None,
    alertname: str | None = None,
    false_positive: bool | None = None,
    test: bool | None = Query(None, description="true: chỉ sự cố thử nghiệm; false: ẩn sự cố thử nghiệm (BR-09)"),
    from_: datetime | None = Query(None, alias="from"), to: datetime | None = None,
    sort: str = Query("-opened_at", pattern="^(opened_at|-opened_at|severity)$"),
    p: PageParams = Depends(), _: m.User = Depends(require_operator), db: Session = Depends(get_db),
) -> dict:
    stmt = select(m.Incident)
    if status:
        wanted = {s.strip() for s in status.split(",") if s.strip()}
        if not wanted <= STATUSES:
            raise ApiError(422, "validation_error", "Dữ liệu không hợp lệ",
                           [{"field": "status", "message": f"Chỉ nhận {sorted(STATUSES)}", "type": "enum"}])
        stmt = stmt.where(m.Incident.status.in_(wanted))
    for column, value in ((m.Incident.firing, firing), (m.Incident.severity, severity), (m.Incident.host, host),
                          (m.Incident.service, service), (m.Incident.alertname, alertname),
                          (m.Incident.is_false_positive, false_positive)):
        if value is not None:
            stmt = stmt.where(column == value)
    if test is not None:
        stmt = stmt.where(m.Incident.fault_run_id.is_not(None) if test else m.Incident.fault_run_id.is_(None))
    if from_:
        stmt = stmt.where(m.Incident.opened_at >= from_)
    if to:
        stmt = stmt.where(m.Incident.opened_at < to)
    order = {"opened_at": (m.Incident.opened_at, m.Incident.id), "-opened_at": (m.Incident.opened_at.desc(),
             m.Incident.id.desc()), "severity": (SEVERITY_ORDER, m.Incident.opened_at.desc())}[sort]
    rows, total = p.apply(db, stmt.order_by(*order))
    return {"items": svc.summaries(db, rows), "total": total, "page": p.page, "page_size": p.page_size}


@incidents.get("/{incident_id}", response_model=IncidentDetail)
def get_incident(incident_id: int, request: Request, _: m.User = Depends(require_operator),
                 db: Session = Depends(get_db)) -> IncidentDetail:
    inc = db.get(m.Incident, incident_id)
    if inc is None:
        raise not_found("sự cố")
    return _detail(db, request, inc)


@incidents.post("/{incident_id}/acknowledge", response_model=IncidentDetail)
def acknowledge(incident_id: int, request: Request, user: m.User = Depends(require_operator),
                db: Session = Depends(get_db)) -> IncidentDetail:
    return _detail(db, request, svc.acknowledge(db, request, incident_id, user))


@incidents.post("/{incident_id}/notes", response_model=IncidentEvent, status_code=201)
def add_note(incident_id: int, body: NoteIn, request: Request, user: m.User = Depends(require_operator),
             db: Session = Depends(get_db)) -> IncidentEvent:
    e = svc.add_note(db, request, incident_id, user, body.content)
    return IncidentEvent(id=e.id, at=e.at, user=user.username, type=e.type, content=e.content)


@incidents.post("/{incident_id}/false-positive", response_model=IncidentDetail)
def false_positive(incident_id: int, body: FalsePositiveIn, request: Request, user: m.User = Depends(require_operator),
                   db: Session = Depends(get_db)) -> IncidentDetail:
    return _detail(db, request, svc.mark_false_positive(db, request, incident_id, user, body.reason))


@incidents.post("/{incident_id}/close", response_model=IncidentDetail)
def close(incident_id: int, body: CloseIn, request: Request, user: m.User = Depends(require_operator),
          db: Session = Depends(get_db)) -> IncidentDetail:
    return _detail(db, request, svc.close(db, request, incident_id, user, body.conclusion))


# ------------------------------------------------------------------ báo cáo tỉ lệ báo giả
@report.get("/false-positives", response_model=FalsePositiveReport, response_model_by_alias=True)
def false_positive_report(from_: datetime | None = Query(None, alias="from"), to: datetime | None = None,
                          _: m.User = Depends(require_operator), db: Session = Depends(get_db)) -> FalsePositiveReport:
    return svc.false_positive_report(db, from_, to)


# ------------------------------------------------------------------ lịch sử đợt cảnh báo
@alerts.get("", response_model=Page[AlertEpisode])
def list_alerts(status: str | None = Query(None, pattern="^(firing|resolved)$"), host: str | None = None,
                alertname: str | None = None, from_: datetime | None = Query(None, alias="from"),
                to: datetime | None = None, p: PageParams = Depends(), _: m.User = Depends(require_operator),
                db: Session = Depends(get_db)) -> dict:
    stmt = select(m.AlertEpisode).order_by(m.AlertEpisode.first_received_at.desc(), m.AlertEpisode.id.desc())
    for column, value in ((m.AlertEpisode.status, status), (m.AlertEpisode.host, host),
                          (m.AlertEpisode.alertname, alertname)):
        if value is not None:
            stmt = stmt.where(column == value)
    if from_:
        stmt = stmt.where(m.AlertEpisode.first_received_at >= from_)
    if to:
        stmt = stmt.where(m.AlertEpisode.first_received_at < to)
    rows, total = p.apply(db, stmt)
    return {"items": rows, "total": total, "page": p.page, "page_size": p.page_size}
