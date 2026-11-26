"""Schema host/service (openapi: HostInput, HostUpdate, Host, ServiceInput, ServiceUpdate, Service)."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.common import ORMModel

LABEL_NAME = r"^[a-zA-Z_][a-zA-Z0-9_]{0,63}$"
LABEL_VALUE = r"^[A-Za-z0-9_.:/-]{1,128}$"
ServiceKind = Literal["web", "app", "database", "other"]


def validate_labels(v: dict[str, str]) -> dict[str, str]:
    """Chỉ nhận cặp nhãn=giá trị an toàn; backend tự dựng PromQL từ đây, không nhận PromQL tùy ý."""
    if not v:
        raise ValueError("Cần ít nhất một nhãn, vd. {\"job\": \"nginx\"}")
    for key, value in v.items():
        if not re.fullmatch(LABEL_NAME, key):
            raise ValueError(f"Tên nhãn không hợp lệ: {key!r}")
        if not isinstance(value, str) or not re.fullmatch(LABEL_VALUE, value):
            raise ValueError(f"Giá trị nhãn không hợp lệ: {key}={value!r}")
    return v


class HostInput(BaseModel):
    name: str = Field(pattern=r"^[a-z0-9-]{1,32}$")
    address: str | None = Field(None, max_length=64)
    prom_instance: str = Field(pattern=LABEL_VALUE, description="Nhãn instance của node exporter")
    grafana_dashboard_uid: str | None = Field(None, pattern=r"^[A-Za-z0-9_-]{1,64}$")
    description: str | None = Field(None, max_length=2000)
    enabled: bool = True


class ServiceInput(BaseModel):
    host_id: int
    name: str = Field(pattern=r"^[a-z0-9-]{1,32}$")
    kind: ServiceKind
    prom_labels: dict[str, str] = Field(max_length=8)
    probe_instance: str | None = Field(None, pattern=LABEL_VALUE)
    grafana_dashboard_uid: str | None = Field(None, pattern=r"^[A-Za-z0-9_-]{1,64}$")
    enabled: bool = True

    @field_validator("prom_labels")
    @classmethod
    def _labels(cls, v: dict[str, str]) -> dict[str, str]:
        return validate_labels(v)


class _PartialUpdate(BaseModel):
    """PATCH = sửa một phần: chỉ gửi trường cần đổi. Trường bắt buộc không được gửi null; trường tùy chọn gửi null để xóa."""

    _not_null: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _check(self):
        if not self.model_fields_set:
            raise ValueError("Cần ít nhất một trường để sửa")
        nulls = [f for f in self._not_null if f in self.model_fields_set and getattr(self, f) is None]
        if nulls:
            raise ValueError(f"Không được để trống: {', '.join(nulls)}")
        return self

    def changes(self) -> dict:
        return self.model_dump(exclude_unset=True)


class HostUpdate(_PartialUpdate):
    _not_null = ("name", "prom_instance", "enabled")
    name: str | None = Field(None, pattern=r"^[a-z0-9-]{1,32}$")
    address: str | None = Field(None, max_length=64)
    prom_instance: str | None = Field(None, pattern=LABEL_VALUE)
    grafana_dashboard_uid: str | None = Field(None, pattern=r"^[A-Za-z0-9_-]{1,64}$")
    description: str | None = Field(None, max_length=2000)
    enabled: bool | None = None


class ServiceUpdate(_PartialUpdate):
    _not_null = ("host_id", "name", "kind", "prom_labels", "enabled")
    host_id: int | None = None
    name: str | None = Field(None, pattern=r"^[a-z0-9-]{1,32}$")
    kind: ServiceKind | None = None
    prom_labels: dict[str, str] | None = Field(None, max_length=8)
    probe_instance: str | None = Field(None, pattern=LABEL_VALUE)
    grafana_dashboard_uid: str | None = Field(None, pattern=r"^[A-Za-z0-9_-]{1,64}$")
    enabled: bool | None = None

    @field_validator("prom_labels")
    @classmethod
    def _labels(cls, v: dict[str, str] | None) -> dict[str, str] | None:
        return None if v is None else validate_labels(v)


class Service(ORMModel):
    id: int
    host_id: int
    name: str
    kind: ServiceKind
    prom_labels: dict[str, str]
    probe_instance: str | None
    grafana_dashboard_uid: str | None
    enabled: bool
    grafana_url: str | None = None


class Host(ORMModel):
    id: int
    name: str
    address: str | None
    prom_instance: str
    grafana_dashboard_uid: str | None
    description: str | None
    enabled: bool
    grafana_url: str | None = None
    services: list[Service] = []
