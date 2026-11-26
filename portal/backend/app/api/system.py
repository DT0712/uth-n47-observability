"""GET /api/health — kiểm tra sống, không cần đăng nhập (openapi: system)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_app_settings, get_clock, get_db
from app.core.clock import Clock
from app.core.config import Settings

router = APIRouter(tags=["system"])


class Health(BaseModel):
    status: Literal["ok", "degraded"]
    database: bool
    prometheus: bool
    version: str
    time: datetime


@router.get("/api/health", response_model=Health)
def health(request: Request, db: Session = Depends(get_db), clock: Clock = Depends(get_clock),
           settings: Settings = Depends(get_app_settings)) -> Health:
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    prom_ok = request.app.state.prometheus.ready()  # /-/ready, timeout 2 s, cache 15 s
    return Health(status="ok" if db_ok and prom_ok else "degraded", database=db_ok, prometheus=prom_ok,
                  version=settings.version, time=clock.now())
