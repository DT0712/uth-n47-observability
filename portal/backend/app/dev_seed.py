"""Nạp dữ liệu MẪU cho backend chạy trên Windows (SQLite) để xem thử giao diện. KHÔNG dùng cho lab thật.

  python -m app.dev_seed            # sau python -m app.db.migrate

Tạo: tài khoản operator op1 / op1-pass-123; vài sự cố qua đúng luồng webhook (firing, resolved, đã xác nhận, đã đóng);
một lần chạy kịch bản lỗi đã hoàn tất (để có thời gian phát hiện TB). Không tạo số liệu metric: không có Prometheus thì
giao diện hiện "Không đọc được Prometheus".
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from app.core.clock import Clock
from app.core.config import Settings
from app.core.security import hash_password
from app.db import models as m
from app.db.base import Database
from app.services.alert_ingest import ingest
from app.services.inventory import seed_inventory
from app.services.users import ensure_bootstrap_admin


class _At(Clock):
    def __init__(self, t):
        self.t = t

    def now(self):
        return self.t


def _alert(name, instance, host, severity, status, starts, fp, service="", summary=""):
    return {"status": status, "fingerprint": fp, "startsAt": starts.isoformat().replace("+00:00", "Z"),
            "endsAt": "0001-01-01T00:00:00Z" if status == "firing" else (starts + timedelta(minutes=3)).isoformat(),
            "labels": {"alertname": name, "instance": instance, "host": host, "severity": severity, "service": service},
            "annotations": {"summary": summary or f"{name} trên {instance}"}}


def _send(db, at, *alerts):
    ingest(db, {"version": "4", "status": alerts[0]["status"], "groupKey": "dev-seed", "receiver": "portal",
                "alerts": list(alerts)}, _At(at))


def main() -> None:
    settings = Settings()
    database = Database(settings.database_url)
    now = Clock().now()
    with database.SessionLocal() as db:
        if db.scalar(select(m.Incident.id).limit(1)):
            print("CSDL đã có sự cố, bỏ qua (xóa portal-dev.db rồi migrate lại nếu muốn nạp từ đầu).")
            return
        admin = ensure_bootstrap_admin(db, settings, Clock()) or db.scalar(select(m.User).where(m.User.role == "admin"))
        seed_inventory(db)
        if not db.scalar(select(m.User.id).where(m.User.username == "op1")):
            db.add(m.User(username="op1", password_hash=hash_password("op1-pass-123", settings.bcrypt_rounds),
                          role="operator", is_active=True, created_at=now))
            db.commit()

        t = lambda minutes: now - timedelta(minutes=minutes)  # noqa: E731
        # Đang firing
        _send(db, t(12), _alert("NginxDown", "web", "web", "critical", "firing", t(12.1), "dev-nginx", "nginx",
                                "Nginx trên VM web không phản hồi"))
        _send(db, t(40), _alert("EndpointSlow", "http://web/health", "web", "warning", "firing", t(40.1), "dev-slow",
                                "demo-app", "Endpoint http://web/health chậm: 2.4s"))
        # Đã resolved, chưa đóng
        _send(db, t(95), _alert("HostHighCpu", "db", "db", "warning", "firing", t(95.1), "dev-cpu", summary="CPU VM db cao: 97.2%"))
        _send(db, t(90), _alert("HostHighCpu", "db", "db", "warning", "resolved", t(95.1), "dev-cpu"))
        # Đã xác nhận
        _send(db, t(30), _alert("ServiceHighLatency", "web", "web", "warning", "firing", t(30.1), "dev-lat", "demo-app",
                                "p95 latency của demo-app cao: 3.1s"))
        inc = db.scalar(select(m.Incident).where(m.Incident.alertname == "ServiceHighLatency"))
        inc.status, inc.acknowledged_at, inc.acknowledged_by = "acknowledged", t(28), admin.id
        db.add(m.IncidentEvent(incident_id=inc.id, at=t(28), user_id=admin.id, type="acknowledged"))
        # Đã đóng (giờ trước)
        _send(db, t(300), _alert("PostgresDown", "db", "db", "critical", "firing", t(300.1), "dev-pg", "postgresql",
                                 "PostgreSQL trên VM db dừng"))
        _send(db, t(296), _alert("PostgresDown", "db", "db", "critical", "resolved", t(300.1), "dev-pg", "postgresql"))
        pg = db.scalar(select(m.Incident).where(m.Incident.alertname == "PostgresDown"))
        pg.status, pg.closed_at, pg.closed_by, pg.conclusion = "closed", t(290), admin.id, "Kịch bản dừng PostgreSQL (mẫu)"
        # Một lần chạy kịch bản lỗi đã hoàn tất
        db.add(m.FaultRun(scenario="service-stop", target_host="web", params={"service": "nginx"}, hold_s=240,
                          root_alert="NginxDown", expected_alerts=["NginxDown", "ServiceDown", "EndpointDown"],
                          status="completed", valid=True, requested_by=admin.id, requested_at=t(61),
                          injected_at=t(60), recovered_at=t(59), stop_reason="root_alert_received",
                          first_detection_s=43.2, root_detection_s=43.2, root_resolved_s=57.4))
        db.commit()
    print("Đã nạp dữ liệu mẫu: 5 sự cố, 1 lần chạy kịch bản. Tài khoản: admin (PORTAL_BOOTSTRAP_ADMIN_PASSWORD), op1 / op1-pass-123")


if __name__ == "__main__":
    main()
