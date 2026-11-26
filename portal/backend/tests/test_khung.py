"""Phần 1: khung dự án, định dạng lỗi, migration, ràng buộc CSDL theo quy tắc nghiệp vụ."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError, StatementError

from app.db import models as m
from app.db.base import Base
from app.db.migrate import downgrade, upgrade

T0 = datetime(2026, 11, 26, 7, 0, 0, tzinfo=timezone.utc)


# ------------------------------------------------------------------ API khung
def test_health(client, clock):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["database"] is True
    assert body["time"].startswith("2026-11-26T07:00:00")


def test_loi_404_dung_dinh_dang(client):
    r = client.get("/api/khong-co")
    assert r.status_code == 404
    assert r.json() == {"error": {"code": "not_found", "message": "Không tìm thấy"}}


def test_metrics_cua_portal(client):
    client.get("/api/health")
    r = client.get("/metrics")
    assert r.status_code == 200
    assert 'portal_http_requests_total{method="GET",status="200"}' in r.text


def test_openapi_tu_sinh(client):
    assert client.get("/api/openapi.json").json()["info"]["title"] == "Obslab Portal API"


# ------------------------------------------------------------------ migration
def test_migration_khop_models_va_ha_cap_duoc(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'm.db'}")
    upgrade(engine)
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == [], f"models.py khác migration, cần alembic revision --autogenerate: {diff}"
    assert set(inspect(engine).get_table_names()) >= {t for t in Base.metadata.tables}
    downgrade(engine)
    assert inspect(engine).get_table_names() == ["alembic_version"]


# ------------------------------------------------------------------ ràng buộc nghiệp vụ
def _user(db) -> m.User:
    u = m.User(username="op", password_hash="x", role="operator", is_active=True, created_at=T0)
    db.add(u)
    db.commit()
    return u


def _incident(**kw) -> m.Incident:
    base = dict(alertname="NginxDown", instance="web", severity="critical", status="open", firing=True, opened_at=T0)
    base.update(kw)
    return m.Incident(**base)


def test_br08_mot_su_co_chua_dong_moi_khoa(db):
    db.add(_incident())
    db.commit()
    db.add(_incident())
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    # Sự cố đã đóng thì cho tạo sự cố mới cùng khóa
    first = db.query(m.Incident).one()
    first.firing, first.status, first.closed_at = False, "closed", T0 + timedelta(minutes=5)
    db.commit()
    db.add(_incident())
    db.commit()
    assert db.query(m.Incident).count() == 2


def test_br01_khong_dong_khi_con_firing_tru_bao_gia(db):
    inc = _incident()
    db.add(inc)
    db.commit()
    inc.status = "closed"
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    inc = db.query(m.Incident).one()
    inc.is_false_positive, inc.false_positive_reason, inc.status = True, "Ngưỡng quá thấp", "closed"
    db.commit()


def test_br04_bao_gia_phai_co_ly_do(db):
    db.add(_incident(is_false_positive=True, false_positive_reason=""))
    with pytest.raises(IntegrityError):
        db.commit()


def test_br03_dot_canh_bao_duy_nhat_theo_fingerprint_va_starts_at(db):
    kw = dict(fingerprint="abc", starts_at=T0, status="firing", alertname="NginxDown", first_received_at=T0,
              last_received_at=T0)
    db.add(m.AlertEpisode(**kw))
    db.commit()
    db.add(m.AlertEpisode(**kw))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.add(m.AlertEpisode(**{**kw, "starts_at": T0 + timedelta(minutes=10)}))  # kích hoạt lại = đợt mới
    db.commit()


def test_br06_moi_vm_mot_lan_chay_dang_hoat_dong(db):
    u = _user(db)
    kw = dict(scenario="cpu", target_host="web", hold_s=240, root_alert="HostHighCpu", requested_by=u.id,
              requested_at=T0, status="running")
    db.add(m.FaultRun(**kw))
    db.commit()
    db.add(m.FaultRun(**kw))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.add(m.FaultRun(**{**kw, "target_host": "db"}))  # VM khác thì được
    db.commit()
    run = db.query(m.FaultRun).filter_by(target_host="web").one()
    run.status = "completed"
    db.commit()
    db.add(m.FaultRun(**kw))  # lần trước đã xong thì chạy tiếp được
    db.commit()


def test_gia_tri_liet_ke_bi_kiem(db):
    db.add(m.User(username="x", password_hash="x", role="root", created_at=T0))
    with pytest.raises(IntegrityError):
        db.commit()


def test_thoi_gian_luon_utc_co_mui_gio(db):
    ict = timezone(timedelta(hours=7))
    db.add(_incident(opened_at=datetime(2026, 11, 26, 14, 0, 0, 123000, tzinfo=ict)))
    db.commit()
    db.expire_all()
    got = db.query(m.Incident).one().opened_at
    assert got == datetime(2026, 11, 26, 7, 0, 0, 123000, tzinfo=timezone.utc)
    assert got.tzinfo is not None


def test_tu_choi_thoi_gian_khong_mui_gio(db):
    db.add(_incident(opened_at=datetime(2026, 11, 26, 7, 0, 0)))
    with pytest.raises(StatementError):
        db.commit()
