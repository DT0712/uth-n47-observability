"""/api/faults/*, /api/reports/fault-runs — chạy kịch bản lỗi (chỉ admin), xem kết quả, xuất báo cáo (UC16–UC18)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin, require_operator
from app.core.errors import not_found
from app.db import models as m
from app.schemas.common import Page, PageParams
from app.schemas.faults import FaultRun, FaultRunCreate, FaultRunDetail, MatchedAlert
from app.services import audit, reports
from app.services.fault_catalog import catalog

faults = APIRouter(prefix="/api/faults", tags=["faults"])
report = APIRouter(prefix="/api/reports", tags=["faults"])


def _runner(request: Request):
    return request.app.state.fault_runner


def _out(db: Session, run: m.FaultRun) -> FaultRun:
    user = db.get(m.User, run.requested_by)
    return FaultRun(id=run.id, scenario=run.scenario, host=run.target_host, params=run.params, status=run.status,
                    valid=run.valid, invalid_reasons=run.invalid_reasons, root_alert=run.root_alert,
                    expected_alerts=run.expected_alerts, requested_by=user.username if user else None,
                    requested_at=run.requested_at, injected_at=run.injected_at, recovered_at=run.recovered_at,
                    stop_reason=run.stop_reason, first_detection_s=run.first_detection_s,
                    root_detection_s=run.root_detection_s, root_resolved_s=run.root_resolved_s, error=run.error)


@faults.get("/scenarios")
def scenarios(request: Request, _: m.User = Depends(require_operator)) -> list[dict]:
    return catalog(request.app.state.settings.fault_max_duration_s)


@faults.get("/preflight")
def preflight(request: Request, host: Literal["web", "db"], _: m.User = Depends(require_admin),
              db: Session = Depends(get_db)) -> dict:
    return _runner(request).preflight(db, host)


@faults.get("/runs", response_model=Page[FaultRun])
def list_runs(status: str | None = None, scenario: str | None = None, host: str | None = None, valid: bool | None = None,
              p: PageParams = Depends(), _: m.User = Depends(require_operator), db: Session = Depends(get_db)) -> dict:
    stmt = select(m.FaultRun).order_by(m.FaultRun.requested_at.desc(), m.FaultRun.id.desc())
    for column, value in ((m.FaultRun.status, status), (m.FaultRun.scenario, scenario), (m.FaultRun.target_host, host),
                          (m.FaultRun.valid, valid)):
        if value is not None:
            stmt = stmt.where(column == value)
    rows, total = p.apply(db, stmt)
    return {"items": [_out(db, r) for r in rows], "total": total, "page": p.page, "page_size": p.page_size}


@faults.post("/runs", response_model=FaultRun, status_code=202)
def create_run(body: FaultRunCreate, request: Request, user: m.User = Depends(require_admin),
               db: Session = Depends(get_db)) -> FaultRun:
    hold = min(body.hold_s, request.app.state.settings.fault_max_duration_s)
    before = db.scalar(select(func.max(m.FaultRun.id))) or 0
    try:
        run = _runner(request).start(db, user, body.scenario, body.host, dict(body.params), hold, body.stop_on_alert,
                                     body.linger_s, body.require_clean, body.note)
    finally:
        # Ghi nhật ký cả khi thất bại (ADR-0007: mọi lần chạy đều có audit)
        last = db.scalar(select(m.FaultRun).where(m.FaultRun.requested_by == user.id, m.FaultRun.id > before)
                         .order_by(m.FaultRun.id.desc()))
        audit.record(db, request, "fault_start", user, "fault_run", last.id if last else None,
                     {"scenario": body.scenario, "host": body.host, "params": dict(body.params), "hold_s": hold,
                      "status": last.status if last else "rejected"})
        db.commit()
    return _out(db, run)


@faults.get("/runs/{run_id}", response_model=FaultRunDetail)
def get_run(run_id: int, _: m.User = Depends(require_operator), db: Session = Depends(get_db)) -> FaultRunDetail:
    run = db.get(m.FaultRun, run_id)
    if run is None:
        raise not_found("lần chạy")
    matched = db.execute(select(m.FaultRunAlert, m.AlertEpisode).join(m.AlertEpisode).where(
        m.FaultRunAlert.fault_run_id == run.id).order_by(m.FaultRunAlert.delay_s)).all()
    return FaultRunDetail(
        **_out(db, run).model_dump(), hold_s=run.hold_s, note=run.note, vm_clock_offset_s=run.vm_clock_offset_s,
        eval_lag_s=run.eval_lag_s, config=run.config,
        alerts=[MatchedAlert(alert_episode_id=ep.id, alertname=ep.alertname, instance=ep.instance, role=a.role,
                             delay_s=a.delay_s, received_at=ep.first_received_at) for a, ep in matched])


@faults.post("/runs/{run_id}/stop", response_model=FaultRun)
def stop_run(run_id: int, request: Request, user: m.User = Depends(require_admin), db: Session = Depends(get_db)) -> FaultRun:
    run = _runner(request).stop(db, run_id)
    audit.record(db, request, "fault_stop", user, "fault_run", run.id, {"host": run.target_host})
    db.commit()
    return _out(db, run)


@report.get("/fault-runs")
def fault_run_report(request: Request, format: Literal["csv", "md"], from_: datetime | None = Query(None, alias="from"),  # noqa: A002
                     to: datetime | None = None, scenario: str | None = None, valid_only: bool = True,
                     _: m.User = Depends(require_admin), db: Session = Depends(get_db)) -> Response:
    data = reports.rows(db, from_, to, scenario, valid_only)
    now = request.app.state.clock.now()
    stamp = now.strftime("%Y%m%d-%H%M%S")
    if format == "csv":
        body, media = reports.to_csv(data), "text/csv; charset=utf-8"
    else:
        body, media = reports.to_markdown(data, now), "text/markdown; charset=utf-8"
    return Response(body, media_type=media,
                    headers={"Content-Disposition": f'attachment; filename="thoi-gian-phat-hien-{stamp}.{format}"'})
