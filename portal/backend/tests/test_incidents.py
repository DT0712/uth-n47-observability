"""Phần 4: webhook Alertmanager, vòng đời sự cố, lịch sử cảnh báo."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

WH = {"Authorization": "Bearer test-webhook-token"}
REAL_DATA = Path(__file__).resolve().parents[3] / "docs" / "05-thu-nghiem" / "du-lieu" / "gd3-dot4-canh-bao.jsonl"


def _err(r) -> str:
    return r.json()["error"]["code"]


def alert(status="firing", name="NginxDown", instance="web", fp="fp-nginx", starts="2026-11-26T06:56:18.123456789Z",
          severity="critical", host="web", service="nginx", summary="Nginx trên VM web không phản hồi"):
    return {"status": status, "fingerprint": fp, "startsAt": starts,
            "endsAt": "0001-01-01T00:00:00Z" if status == "firing" else "2026-11-26T07:01:03.000Z",
            "labels": {"alertname": name, "instance": instance, "severity": severity, "host": host, "service": service},
            "annotations": {"summary": summary, "runbook": f"runbooks/{name}.md"}}


def payload(*alerts, status=None):
    return {"version": "4", "groupKey": "{}:{alertname=\"x\"}", "receiver": "portal",
            "status": status or alerts[0]["status"], "alerts": list(alerts)}


def send(client, body):
    r = client.post("/api/webhooks/alertmanager", headers=WH, json=body)
    assert r.status_code == 200, r.text
    return r.json()


def only_incident(client, h) -> dict:
    items = client.get("/api/incidents", headers=h).json()["items"]
    assert len(items) == 1
    return client.get(f"/api/incidents/{items[0]['id']}", headers=h).json()


# ------------------------------------------------------------------ webhook
def test_webhook_can_token(client):
    body = payload(alert())
    assert _err(client.post("/api/webhooks/alertmanager", json=body)) == "invalid_webhook_token"
    r = client.post("/api/webhooks/alertmanager", json=body, headers={"Authorization": "Bearer sai"})
    assert r.status_code == 401
    # Token người dùng (JWT) cũng không dùng được cho webhook
    login = client.post("/api/auth/login", json={"username": "admin", "password": "admin-pass-123"}).json()
    r = client.post("/api/webhooks/alertmanager", json=body, headers={"Authorization": f"Bearer {login['access_token']}"})
    assert r.status_code == 401


def test_webhook_payload_sai(client):
    r = client.post("/api/webhooks/alertmanager", headers=WH, json={"version": "3", "status": "firing", "alerts": []})
    assert r.status_code == 422 and _err(r) == "validation_error"
    r = client.post("/api/webhooks/alertmanager", headers={**WH, "Content-Type": "application/json"}, content=b"{khong-json")
    assert r.status_code == 422


def test_firing_tao_dot_va_su_co(client, clock, operator_h):
    res = send(client, payload(alert()))
    assert res == {"receipt_id": 1, "duplicate": False, "episodes_created": 1, "episodes_updated": 0,
                   "incidents_created": 1, "errors": 0}
    inc = only_incident(client, operator_h)
    assert inc["alertname"] == "NginxDown" and inc["instance"] == "web" and inc["status"] == "open"
    assert inc["firing"] is True and inc["severity"] == "critical" and inc["can_close"] is False
    assert inc["summary"] == "Nginx trên VM web không phản hồi"
    ep = inc["episodes"][0]
    assert ep["starts_at"].startswith("2026-11-26T06:56:18.123456")  # nano giây cắt còn micro giây
    assert ep["first_received_at"].startswith("2026-11-26T07:00:00")  # T1 = đồng hồ backend (FakeClock)
    assert [e["type"] for e in inc["events"]] == ["opened", "episode_firing"]
    assert "var-instance=web" in inc["grafana_url"]


def test_gui_lai_y_het_la_trung(client, operator_h):
    body = payload(alert())
    send(client, body)
    assert send(client, body) == {"receipt_id": None, "duplicate": True, "episodes_created": 0, "episodes_updated": 0,
                                  "incidents_created": 0, "errors": 0}
    assert only_incident(client, operator_h)["episode_count"] == 1


def test_repeat_interval_chi_cap_nhat(client, clock, operator_h, db):
    from app.db import models as m
    send(client, payload(alert()))
    clock.advance(3600)  # Alertmanager gửi lại sau repeat_interval, payload khác (groupKey...) nhưng cùng đợt
    body = payload(alert())
    body["groupKey"] = "khac"
    res = send(client, body)
    assert res["episodes_created"] == 0 and res["episodes_updated"] == 1
    ep = db.query(m.AlertEpisode).one()
    assert ep.first_received_at.hour == 7 and ep.last_received_at.hour == 8


def test_resolved_dong_dot_va_cho_phep_dong_su_co(client, clock, operator_h):
    send(client, payload(alert()))
    clock.advance(90)
    send(client, payload(alert(status="resolved")))
    inc = only_incident(client, operator_h)
    assert inc["firing"] is False and inc["can_close"] is True
    ep = inc["episodes"][0]
    assert ep["status"] == "resolved" and ep["ends_at"].startswith("2026-11-26T07:01:03")
    assert ep["resolved_received_at"].startswith("2026-11-26T07:01:30")
    assert inc["events"][-1]["type"] == "episode_resolved"


def test_br08_kich_hoat_lai_gop_vao_su_co_dang_mo(client, clock, operator_h):
    send(client, payload(alert()))
    send(client, payload(alert(status="resolved")))
    clock.advance(600)
    res = send(client, payload(alert(starts="2026-11-26T07:10:00Z")))  # cùng fingerprint, startsAt mới = đợt mới (BR-03)
    assert res["episodes_created"] == 1 and res["incidents_created"] == 0
    inc = only_incident(client, operator_h)
    assert inc["episode_count"] == 2 and inc["firing"] is True and inc["status"] == "open"


def test_su_co_da_dong_khong_mo_lai(client, clock, operator_h):
    send(client, payload(alert()))
    send(client, payload(alert(status="resolved")))
    inc_id = only_incident(client, operator_h)["id"]
    client.post(f"/api/incidents/{inc_id}/close", headers=operator_h, json={"conclusion": "Đã khởi động lại Nginx"})
    clock.advance(600)
    assert send(client, payload(alert(starts="2026-11-26T07:10:00Z")))["incidents_created"] == 1
    rows = client.get("/api/incidents?sort=opened_at", headers=operator_h).json()["items"]
    assert [r["status"] for r in rows] == ["closed", "open"]


def test_khoa_su_co_la_alertname_va_instance(client, operator_h):
    send(client, payload(alert(), alert(name="EndpointDown", instance="web:80", fp="fp-ep"),
                         alert(name="NginxDown", instance="web2", fp="fp-2", host="web2")))
    assert client.get("/api/incidents", headers=operator_h).json()["total"] == 3


def test_muc_do_su_co_la_cao_nhat(client, operator_h):
    send(client, payload(alert(severity="warning")))
    send(client, payload(alert(severity="critical", starts="2026-11-26T07:10:00Z")))
    assert only_incident(client, operator_h)["severity"] == "critical"


def test_resolved_khi_chua_thay_firing(client, operator_h):
    send(client, payload(alert(status="resolved")))
    inc = only_incident(client, operator_h)
    assert inc["firing"] is False and inc["episodes"][0]["status"] == "resolved"
    assert "chưa ghi nhận firing" in inc["events"][-1]["content"]


def test_mot_alert_loi_khong_lam_hong_ca_payload(client, operator_h):
    res = send(client, payload(alert(starts="khong-phai-ngay"), alert(fp="fp-ok", name="PostgresDown", instance="db")))
    assert res["errors"] == 1 and res["episodes_created"] == 1
    assert only_incident(client, operator_h)["alertname"] == "PostgresDown"


def test_hook_firing_moi_duoc_goi(app, client):
    seen = []
    app.state.alert_hooks.append(lambda db, ep: seen.append((ep.alertname, ep.host)))
    send(client, payload(alert()))
    send(client, payload(alert()))  # trùng: không gọi lại
    assert seen == [("NginxDown", "web")]


# ------------------------------------------------------------------ xử lý sự cố
def _new(client, h, **kw) -> int:
    send(client, payload(alert(**kw)))
    return client.get("/api/incidents", headers=h).json()["items"][0]["id"]


def test_quy_trinh_day_du(client, clock, operator_h):
    inc_id = _new(client, operator_h)
    r = client.post(f"/api/incidents/{inc_id}/acknowledge", headers=operator_h)
    assert r.status_code == 200 and r.json()["status"] == "acknowledged" and r.json()["acknowledged_by"] == "op1"
    assert _err(client.post(f"/api/incidents/{inc_id}/acknowledge", headers=operator_h)) == "incident_not_open"
    clock.advance(30)
    r = client.post(f"/api/incidents/{inc_id}/notes", headers=operator_h, json={"content": "systemctl status nginx: inactive"})
    assert r.status_code == 201 and r.json()["user"] == "op1" and r.json()["type"] == "note"
    r = client.post(f"/api/incidents/{inc_id}/close", headers=operator_h, json={"conclusion": "Đóng thử"})
    assert r.status_code == 409 and _err(r) == "incident_still_firing"  # BR-01
    send(client, payload(alert(status="resolved")))
    r = client.post(f"/api/incidents/{inc_id}/close", headers=operator_h, json={"conclusion": "Nginx bị dừng, đã bật lại"})
    body = r.json()
    assert r.status_code == 200 and body["status"] == "closed" and body["closed_by"] == "op1" and body["can_close"] is False
    assert [e["type"] for e in body["events"]] == ["opened", "episode_firing", "acknowledged", "note",
                                                   "episode_resolved", "closed"]
    for path, js in (("notes", {"content": "x"}), ("false-positive", {"reason": "muộn rồi"}), ("close", {"conclusion": "lần 2"})):
        assert _err(client.post(f"/api/incidents/{inc_id}/{path}", headers=operator_h, json=js)) == "incident_closed"


def test_bao_gia_cho_phep_dong_khi_con_firing(client, operator_h, admin_h):
    inc_id = _new(client, operator_h, name="HostHighCpu", instance="web", fp="fp-cpu", severity="warning")
    assert client.post(f"/api/incidents/{inc_id}/false-positive", headers=operator_h, json={"reason": "x"}).status_code == 422
    r = client.post(f"/api/incidents/{inc_id}/false-positive", headers=operator_h,
                    json={"reason": "apt update chạy định kỳ, CPU cao 2 phút là bình thường"})
    assert r.json()["is_false_positive"] is True and r.json()["can_close"] is True and r.json()["firing"] is True
    assert client.post(f"/api/incidents/{inc_id}/close", headers=operator_h,
                       json={"conclusion": "Báo giả, đề xuất tăng for lên 5m"}).status_code == 200
    log = client.get("/api/audit?action=false_positive", headers=admin_h).json()["items"][0]
    assert log["object_type"] == "incident" and log["user"] == "op1"


def test_su_co_khong_ton_tai(client, operator_h):
    assert _err(client.get("/api/incidents/999", headers=operator_h)) == "not_found"
    assert _err(client.post("/api/incidents/999/acknowledge", headers=operator_h)) == "not_found"


def test_can_dang_nhap(client):
    assert client.get("/api/incidents").status_code == 401
    assert client.get("/api/alerts").status_code == 401


# ------------------------------------------------------------------ lọc, phân trang, lịch sử
def test_loc_va_sap_xep(client, clock, operator_h):
    send(client, payload(alert(name="HostHighCpu", instance="web", fp="a", severity="warning")))
    clock.advance(60)
    send(client, payload(alert(name="PostgresDown", instance="db", fp="b", host="db", service="postgresql")))
    clock.advance(60)
    send(client, payload(alert(name="HostHighMemory", instance="db", fp="c", host="db", severity="warning")))
    send(client, payload(alert(name="HostHighMemory", instance="db", fp="c", host="db", severity="warning", status="resolved")))

    def names(q):
        return [i["alertname"] for i in client.get(f"/api/incidents?{q}", headers=operator_h).json()["items"]]

    assert names("") == ["HostHighMemory", "PostgresDown", "HostHighCpu"]
    assert names("sort=opened_at") == ["HostHighCpu", "PostgresDown", "HostHighMemory"]
    assert names("sort=severity")[0] == "PostgresDown"
    assert names("host=db") == ["HostHighMemory", "PostgresDown"]
    assert names("firing=false") == ["HostHighMemory"]
    assert names("severity=critical") == ["PostgresDown"]
    assert names("status=open,acknowledged") == names("")
    assert names("from=2026-11-26T07:00:30Z&to=2026-11-26T07:01:30Z") == ["PostgresDown"]
    page = client.get("/api/incidents?page=2&page_size=2", headers=operator_h).json()
    assert page["total"] == 3 and [i["alertname"] for i in page["items"]] == ["HostHighCpu"]
    assert client.get("/api/incidents?status=dang-xu-ly", headers=operator_h).status_code == 422


def test_lich_su_dot_canh_bao(client, clock, operator_h):
    send(client, payload(alert()))
    clock.advance(60)
    send(client, payload(alert(name="PostgresDown", instance="db", fp="b", host="db")))
    send(client, payload(alert(status="resolved")))
    r = client.get("/api/alerts", headers=operator_h).json()
    assert r["total"] == 2 and r["items"][0]["alertname"] == "PostgresDown"
    assert [i["alertname"] for i in client.get("/api/alerts?status=firing", headers=operator_h).json()["items"]] == ["PostgresDown"]
    assert client.get("/api/alerts?host=web", headers=operator_h).json()["total"] == 1


# ------------------------------------------------------------------ phát lại dữ liệu thật
@pytest.mark.skipif(not REAL_DATA.exists(), reason="thiếu dữ liệu gd3-dot4")
def test_phat_lai_canh_bao_that_gd3_dot4(client, clock, operator_h):
    """Phát lại 32 cảnh báo alert-recorder đã nhận trong đợt gd3-dot4 (15 lần dừng dịch vụ), đúng thứ tự và thời điểm."""
    rows = [json.loads(line) for line in REAL_DATA.read_text(encoding="utf-8").splitlines() if line.strip()]
    for row in rows:
        clock._t = datetime.fromisoformat(row["received_at"]).astimezone(timezone.utc)
        a = {k: row[k] for k in ("status", "labels", "annotations", "startsAt", "endsAt", "fingerprint")}
        send(client, {"version": "4", "groupKey": row["groupKey"], "status": row["status"], "receiver": "portal",
                      "alerts": [a]})
    episodes = {(r["fingerprint"], r["startsAt"]) for r in rows}
    keys = {(r["labels"]["alertname"], r["labels"]["instance"]) for r in rows}
    incidents = client.get("/api/incidents?page_size=200", headers=operator_h).json()
    assert client.get("/api/alerts?page_size=200", headers=operator_h).json()["total"] == len(episodes)
    assert incidents["total"] == len(keys)  # không đóng sự cố nào -> mỗi khóa đúng một sự cố (BR-08)
    by_name = {i["alertname"]: i for i in incidents["items"]}
    assert by_name["NginxDown"]["episode_count"] == 5 and by_name["PostgresDown"]["episode_count"] == 5
    assert all(not i["firing"] for i in incidents["items"])  # mọi đợt đều đã resolved
