"""Schema webhook Alertmanager, sự cố, đợt cảnh báo (openapi: AlertmanagerWebhook, Incident*, AlertEpisode)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Severity = Literal["critical", "warning", "info"]
IncidentStatus = Literal["open", "acknowledged", "closed"]


# ------------------------------------------------------------------ webhook (định dạng v4 của Alertmanager 0.27)
class AMAlert(BaseModel):
    model_config = ConfigDict(extra="ignore")
    status: Literal["firing", "resolved"]
    labels: dict[str, str]
    annotations: dict[str, str] = {}
    startsAt: str = Field(min_length=10, max_length=64)  # chuỗi: Alertmanager gửi tới nano giây
    endsAt: str | None = None  # "0001-01-01T00:00:00Z" khi chưa kết thúc
    generatorURL: str | None = None
    fingerprint: str = Field(min_length=1, max_length=64)


class AlertmanagerWebhook(BaseModel):
    model_config = ConfigDict(extra="ignore")
    version: Literal["4"]
    groupKey: str | None = None
    status: Literal["firing", "resolved"]
    receiver: str | None = None
    alerts: list[AMAlert] = Field(max_length=1000)


class WebhookResult(BaseModel):
    receipt_id: int | None
    duplicate: bool
    episodes_created: int = 0
    episodes_updated: int = 0
    incidents_created: int = 0
    errors: int = 0


# ------------------------------------------------------------------ đợt cảnh báo, sự cố
class AlertEpisode(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    fingerprint: str
    alertname: str
    instance: str
    host: str | None
    service: str | None
    severity: str
    status: Literal["firing", "resolved"]
    starts_at: datetime
    ends_at: datetime | None
    first_received_at: datetime
    resolved_received_at: datetime | None
    labels: dict[str, str]
    annotations: dict[str, str]
    incident_id: int | None


class IncidentEvent(BaseModel):
    id: int
    at: datetime
    user: str | None
    type: str
    content: str | None


class RunbookRef(BaseModel):
    alertname: str
    title: str
    severity: str | None
    category: str | None
    status: str
    loaded_at: datetime


class IncidentSummary(BaseModel):
    id: int
    alertname: str
    instance: str
    host: str | None
    service: str | None
    severity: str
    status: IncidentStatus
    firing: bool
    is_false_positive: bool
    episode_count: int
    summary: str | None
    opened_at: datetime
    acknowledged_at: datetime | None
    closed_at: datetime | None


class IncidentDetail(IncidentSummary):
    acknowledged_by: str | None
    closed_by: str | None
    false_positive_reason: str | None
    conclusion: str | None
    can_close: bool
    episodes: list[AlertEpisode]
    events: list[IncidentEvent]
    runbook: RunbookRef | None
    grafana_url: str | None


# ------------------------------------------------------------------ thao tác
class NoteIn(BaseModel):
    content: str = Field(min_length=1, max_length=5000)


class FalsePositiveIn(BaseModel):
    reason: str = Field(min_length=5, max_length=2000)


class CloseIn(BaseModel):
    conclusion: str = Field(min_length=5, max_length=5000)
