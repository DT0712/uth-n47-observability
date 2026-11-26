"""Schema kịch bản lỗi (openapi: FaultScenario, Preflight, FaultRunCreate, FaultRun, FaultRunDetail)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Scenario = Literal["cpu", "memory", "disk", "service-stop", "latency", "errors"]


class FaultRunCreate(BaseModel):
    scenario: Scenario
    host: Literal["web", "db"]
    params: dict[str, int | str] = Field(default_factory=dict, max_length=4)
    hold_s: int = Field(240, ge=30, le=840)
    stop_on_alert: bool = True
    linger_s: int = Field(30, ge=0, le=120)
    require_clean: bool = False
    note: str | None = Field(None, max_length=500)


class FaultRun(BaseModel):
    id: int
    scenario: str
    host: str
    params: dict[str, Any]
    status: str
    valid: bool
    invalid_reasons: list[str]
    root_alert: str
    expected_alerts: list[str]
    requested_by: str | None
    requested_at: datetime
    injected_at: datetime | None
    recovered_at: datetime | None
    stop_reason: str | None
    first_detection_s: float | None
    root_detection_s: float | None
    root_resolved_s: float | None
    error: str | None


class MatchedAlert(BaseModel):
    alert_episode_id: int
    alertname: str
    instance: str
    role: Literal["root", "expected", "extra", "unrelated"]
    delay_s: float
    received_at: datetime


class FaultRunDetail(FaultRun):
    hold_s: int
    note: str | None
    vm_clock_offset_s: float | None
    eval_lag_s: float | None
    config: dict[str, Any] | None
    alerts: list[MatchedAlert]
