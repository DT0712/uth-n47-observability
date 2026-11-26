"""GET /api/health — kiểm tra sống, không cần đăng nhập (openapi: system)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends
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
    prometheus: bool | None  # None: chưa kiểm (client Prometheus có ở phần 6 của GĐ5)
    version: str
    time: datetime


@router.get("/api/health", response_model=Health)
def health(db: Session = Depends(get_db), clock: Clock = Depends(get_clock),
           settings: Settings = Depends(get_app_settings)) -> Health:
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    return Health(status="ok" if db_ok else "degraded", database=db_ok, prometheus=None,
                  version=settings.version, time=clock.now())
