"""/api/runbooks — xem runbook (operator), nạp lại từ git (admin). UC10, UC15, FR-P11."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Path, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin, require_operator
from app.core.errors import not_found
from app.db import models as m
from app.schemas.incidents import RunbookRef
from app.services import audit
from app.services import runbooks as svc

router = APIRouter(prefix="/api/runbooks", tags=["runbooks"])


class Runbook(RunbookRef):
    body_md: str
    source_path: str


class ReloadResult(BaseModel):
    loaded: int
    updated: int
    removed: int
    errors: list[str]
    loaded_at: datetime


@router.get("", response_model=list[RunbookRef])
def list_runbooks(_: m.User = Depends(require_operator), db: Session = Depends(get_db)) -> list[m.Runbook]:
    return list(db.scalars(select(m.Runbook).order_by(m.Runbook.alertname)))


@router.post("/reload", response_model=ReloadResult)
def reload_runbooks(request: Request, actor: m.User = Depends(require_admin), db: Session = Depends(get_db)) -> ReloadResult:
    directory = svc.resolve_dir(request.app.state.settings.runbooks_dir)
    result = svc.load(db, directory, request.app.state.clock)
    audit.record(db, request, "runbooks_reload", actor, "runbook", None,
                 {"loaded": result.loaded, "updated": result.updated, "removed": result.removed,
                  "errors": len(result.errors)})
    db.commit()
    return ReloadResult(**result.__dict__, loaded_at=request.app.state.clock.now())


@router.get("/{alertname}", response_model=Runbook)
def get_runbook(alertname: str = Path(pattern=r"^[A-Za-z0-9_]+$"), _: m.User = Depends(require_operator),
                db: Session = Depends(get_db)) -> m.Runbook:
    row = db.scalar(select(m.Runbook).where(m.Runbook.alertname == alertname))
    if row is None:
        raise not_found(f"runbook của {alertname}")
    return row
