"""Schema host/service (openapi: HostInput, Host, ServiceInput, Service)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel

LABEL_NAME = r"^[a-zA-Z_][a-zA-Z0-9_]{0,63}$"
LABEL_VALUE = r"^[A-Za-z0-9_.:/-]{1,128}$"
ServiceKind = Literal["web", "app", "database", "other"]


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
        """Chỉ nhận cặp nhãn=giá trị an toàn; backend tự dựng PromQL từ đây, không nhận PromQL tùy ý."""
        import re

        if not v:
            raise ValueError("Cần ít nhất một nhãn, vd. {\"job\": \"nginx\"}")
        for key, value in v.items():
            if not re.fullmatch(LABEL_NAME, key):
                raise ValueError(f"Tên nhãn không hợp lệ: {key!r}")
            if not isinstance(value, str) or not re.fullmatch(LABEL_VALUE, value):
                raise ValueError(f"Giá trị nhãn không hợp lệ: {key}={value!r}")
        return v


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
