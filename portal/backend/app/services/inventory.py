"""Danh mục host/service: link Grafana và dữ liệu mẫu của lab 3 VM.

Dữ liệu mẫu khớp monitor/prometheus/prometheus.yml (nhãn instance/job/service) và uid dashboard trong
monitor/grafana/dashboards/. Chỉ nạp khi bảng hosts còn trống, nên admin sửa/xóa xong khởi động lại không bị ghi đè.
"""

from __future__ import annotations

import logging
from urllib.parse import urlencode

from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.db import models as m

log = logging.getLogger(__name__)

SEED_HOSTS = [
    {"name": "monitor", "address": "192.168.56.10", "prom_instance": "monitor", "grafana_dashboard_uid": "lab-host",
     "description": "VM giám sát: Prometheus, Alertmanager, Grafana, Blackbox, alert-recorder, portal", "services": []},
    {"name": "web", "address": "192.168.56.11", "prom_instance": "web", "grafana_dashboard_uid": "lab-host",
     "description": "VM web: Nginx reverse proxy + demo app",
     "services": [
         {"name": "nginx", "kind": "web", "prom_labels": {"job": "nginx", "service": "nginx"},
          "probe_instance": "web:80", "grafana_dashboard_uid": "lab-nginx"},
         {"name": "demo-app", "kind": "app", "prom_labels": {"job": "demo-app", "service": "demo-app"},
          "probe_instance": "http://web/health", "grafana_dashboard_uid": "lab-service"},
     ]},
    {"name": "db", "address": "192.168.56.12", "prom_instance": "db", "grafana_dashboard_uid": "lab-host",
     "description": "VM CSDL: PostgreSQL của demo app",
     "services": [
         {"name": "postgresql", "kind": "database", "prom_labels": {"job": "postgres", "service": "postgresql"},
          "probe_instance": "db:5432", "grafana_dashboard_uid": "lab-postgres"},
     ]},
]


def seed_inventory(db: Session) -> int:
    """Nạp 3 VM mẫu nếu chưa có host nào. Trả về số host đã tạo."""
    try:
        if db.scalar(select(func.count()).select_from(m.Host)):
            return 0
    except (OperationalError, ProgrammingError):
        db.rollback()
        return 0
    for h in SEED_HOSTS:
        host = m.Host(**{k: v for k, v in h.items() if k != "services"}, enabled=True)
        host.services = [m.Service(**s, enabled=True) for s in h["services"]]
        db.add(host)
    db.commit()
    log.info("Đã nạp %d host mẫu", len(SEED_HOSTS))
    return len(SEED_HOSTS)


def grafana_url(base: str, uid: str | None, instance: str | None = None, service: str | None = None,
                time_range: str = "1h") -> str | None:
    """Link dashboard kèm biến và khoảng thời gian (FR-P05). Dashboard bỏ qua biến nó không dùng."""
    if not uid:
        return None
    params = {}
    if instance:
        params["var-instance"] = instance
    if service:
        params["var-service"] = service
    params.update({"from": f"now-{time_range}", "to": "now"})
    return f"{base.rstrip('/')}/d/{uid}?{urlencode(params)}"
