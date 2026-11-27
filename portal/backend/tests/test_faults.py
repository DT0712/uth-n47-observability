"""Phần 7: kịch bản lỗi, thời gian phát hiện, báo cáo. Dùng SSH giả và bộ kiểm điều kiện giả, không đụng VM."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from tests.test_incidents import alert, payload, send

ROOT = Path(__file__).resolve().parents[3]


def _err(r) -> str:
    return r.json()["error"]["code"]


def am_alert(name, host="web", instance=None, fp=None, status="firing", starts=None, clock=None, **labels):
    """Cảnh báo Alertmanager; startsAt mặc định = lúc Prometheus bắn, 5 s trước khi portal nhận (group_wait)."""
    from datetime import timedelta
    starts = starts or (clock.now() - timedelta(seconds=5)).isoformat().replace("+00:00", "Z")
    a = alert(status=status, name=name, instance=instance or host, fp=fp or f"fp-{name}-{host}", starts=starts, host=host,
              service=labels.pop("service", None) or "", severity=labels.pop("severity", "critical"))
    a["labels"].update(labels)
    return a


def start(client, h, **body):
    data = {"scenario": "cpu", "host": "web", "hold_s": 240, **body}
    return client.post("/api/faults/runs", headers=h, json=data)


def tick(app, clock, seconds):
    clock.advance(seconds)
    app.state.fault_runner.tick()


# ------------------------------------------------------------------ danh mục, kiểm điều kiện
def test_danh_muc_kich_ban(client, operator_h):
    rows = {r["scenario"]: r for r in client.get("/api/faults/scenarios", headers=operator_h).json()}
    assert set(rows) == {"cpu", "memory", "disk", "service-stop", "latency", "errors"}
    assert rows["memory"]["params"][0] | {} == {"name": "percent", "type": "integer", "min": 50, "max": 97, "default": 95,
                                                "choices": []}
    assert rows["latency"]["hosts"] == ["web"] and rows["latency"]["expected_alerts"] == ["EndpointSlow"]
    assert rows["cpu"]["max_hold_s"] == 840


def test_kiem_dieu_kien_do(client, admin_h, checks):
    assert client.get("/api/faults/preflight?host=web", headers=admin_h).json()["clean"] is True
    checks.lag, checks.alerts = 10.44, ["HostHighCpu(db, firing)"]
    body = client.get("/api/faults/preflight?host=web", headers=admin_h).json()
    assert body["clean"] is False and body["eval_lag_s"] == 10.44
    assert any("SC-04" in r for r in body["reasons"]) and any("HostHighCpu" in r for r in body["reasons"])


def test_chi_admin_chay_va_kiem_tra(client, operator_h):
    assert start(client, operator_h).status_code == 403
    assert client.get("/api/faults/preflight?host=web", headers=operator_h).status_code == 403
    assert client.get("/api/faults/runs", headers=operator_h).status_code == 200  # xem lịch sử thì được


@pytest.mark.parametrize("body,field", [
    ({"scenario": "latency", "host": "db"}, "host"),
    ({"scenario": "memory", "params": {"percent": 99}}, "params.percent"),
    ({"scenario": "memory", "params": {"percent": "95"}}, "params.percent"),
    ({"scenario": "cpu", "params": {"percent": 90}}, "params"),
    ({"scenario": "service-stop", "params": {"service": "nginx"}, "host": "db"}, "host"),
    ({"scenario": "service-stop", "params": {"service": "redis"}}, "params.service"),
    ({"scenario": "cpu", "hold_s": 900}, "hold_s"),
])
def test_tham_so_sai_bi_tu_choi_truoc_khi_goi_vm(client, admin_h, ssh, body, field):
    r = start(client, admin_h, **body)
    assert r.status_code == 422 and field in r.json()["error"]["details"][0]["field"]
    assert ssh.calls == []


# ------------------------------------------------------------------ một lần chạy đầy đủ
def test_vong_doi_day_du_va_thoi_gian_phat_hien(app, client, admin_h, ssh, clock):
    ssh.vm_offset = 0.25                   # đồng hồ VM nhanh hơn monitor 0,25 s
    app.state.fault_runner.checks.offset = 0.25
    r = start(client, admin_h, scenario="service-stop", params={"service": "nginx"})
    assert r.status_code == 202
    run = r.json()
    assert run["status"] == "running" and run["valid"] is True and run["root_alert"] == "NginxDown"
    assert run["expected_alerts"] == ["NginxDown", "ServiceDown", "EndpointDown"]
    assert ssh.calls[-1] == ("web", "service-stop start duration=300 service=nginx")
    assert run["injected_at"] in ("2026-11-26T07:00:00Z", "2026-11-26T07:00:00.000Z")  # T0 đã trừ độ lệch đồng hồ VM
    rid = run["id"]

    tick(app, clock, 20)                   # chưa có gì
    assert client.get(f"/api/faults/runs/{rid}", headers=admin_h).json()["status"] == "running"
    clock.advance(19.4)                    # 39,4 s: portal nhận NginxDown
    root_starts = "2026-11-26T07:00:34.400Z"  # Prometheus bắn 5 s trước đó (group_wait)
    send(client, payload(am_alert("NginxDown", service="nginx", starts=root_starts, clock=clock)))
    clock.advance(3)
    send(client, payload(am_alert("HostHighCpu", host="db", clock=clock, severity="warning")))  # không liên quan
    tick(app, clock, 10)                   # linger 30 s chưa hết
    assert client.get(f"/api/faults/runs/{rid}", headers=admin_h).json()["status"] == "running"
    tick(app, clock, 20)                   # đã quá 30 s sau cảnh báo gốc -> gỡ lỗi
    detail = client.get(f"/api/faults/runs/{rid}", headers=admin_h).json()
    assert detail["status"] == "recovering" and detail["stop_reason"] == "root_alert_received"
    assert ssh.calls[-1] == ("web", "service-stop stop") and "web" not in ssh.active

    clock.advance(25)                      # cảnh báo hệ quả tới SAU khi gỡ: nhiễu lúc khôi phục
    send(client, payload(am_alert("EndpointDown", instance="web:80", service="nginx", clock=clock)))
    clock.advance(30)
    send(client, payload(am_alert("NginxDown", service="nginx", status="resolved", starts=root_starts, clock=clock)))
    tick(app, clock, 2)
    done = client.get(f"/api/faults/runs/{rid}", headers=admin_h).json()
    assert done["status"] == "completed" and done["valid"] is True
    assert done["root_detection_s"] == pytest.approx(39.4) and done["first_detection_s"] == pytest.approx(39.4)
    roles = {a["alertname"]: a["role"] for a in done["alerts"]}
    assert roles == {"NginxDown": "root", "HostHighCpu": "unrelated", "EndpointDown": "extra"}
    assert done["root_resolved_s"] == pytest.approx(55.0)  # gỡ lúc 72,4 s, resolved tới lúc 127,4 s
    assert done["config"]["for_s"] == 30 and done["config"]["group_wait_s"] == 5


def test_khong_phat_hien_thi_go_khi_het_thoi_gian_giu(app, client, admin_h, ssh, clock):
    rid = start(client, admin_h, hold_s=60).json()["id"]
    tick(app, clock, 59)
    assert "web" in ssh.active
    tick(app, clock, 1)
    tick(app, clock, 1)
    run = client.get(f"/api/faults/runs/{rid}", headers=admin_h).json()
    assert run["status"] == "completed" and run["stop_reason"] == "not_detected" and run["root_detection_s"] is None
    assert "web" not in ssh.active


def test_admin_dung_som(app, client, admin_h, ssh, clock):
    rid = start(client, admin_h).json()["id"]
    r = client.post(f"/api/faults/runs/{rid}/stop", headers=admin_h)
    assert r.status_code == 200 and r.json()["status"] == "recovering" and r.json()["stop_reason"] == "admin_stopped"
    assert _err(client.post(f"/api/faults/runs/{rid}/stop", headers=admin_h)) == "fault_not_running"
    actions = [i["action"] for i in client.get("/api/audit", headers=admin_h).json()["items"]]
    assert "fault_start" in actions and "fault_stop" in actions


def test_dieu_kien_khong_dat_thi_danh_dau_khong_hop_le(client, admin_h, checks):
    checks.problem = "đồng hồ web lệch monitor tới 1.12s"
    run = start(client, admin_h).json()
    assert run["valid"] is False and "1.12s" in run["invalid_reasons"][0]


def test_require_clean_tu_choi_khi_dieu_kien_khong_dat(client, admin_h, checks, ssh):
    checks.alerts = ["NginxDown(web, firing)"]
    r = start(client, admin_h, require_clean=True)
    assert r.status_code == 409 and _err(r) == "fault_preflight_failed" and ssh.calls == []


def test_canh_bao_goc_toi_cham_la_khong_hop_le(app, client, admin_h, clock):
    rid = start(client, admin_h).json()["id"]
    clock.advance(80)
    stale = (clock.now().timestamp() - 15.4)  # Prometheus bắn 15,4 s trước khi portal nhận (SC-04)
    send(client, payload(am_alert("HostHighCpu", clock=clock, severity="warning",
                                  starts=datetime.fromtimestamp(stale, tz=timezone.utc).isoformat().replace("+00:00", "Z"))))
    tick(app, clock, 31)
    tick(app, clock, 200)
    run = client.get(f"/api/faults/runs/{rid}", headers=admin_h).json()
    assert run["status"] == "completed" and run["valid"] is False and "SC-04" in run["invalid_reasons"][-1]


def test_disk_chi_khop_dung_mountpoint(app, client, admin_h, clock):
    rid = start(client, admin_h, scenario="disk", params={"percent": 95}).json()["id"]
    clock.advance(70)
    send(client, payload(am_alert("HostDiskAlmostFull", fp="root-fs", mountpoint="/", clock=clock)))
    clock.advance(5)
    send(client, payload(am_alert("HostDiskAlmostFull", fp="labdisk", mountpoint="/mnt/labdisk", clock=clock)))
    roles = sorted((a["role"], a["delay_s"]) for a in client.get(f"/api/faults/runs/{rid}", headers=admin_h).json()["alerts"])
    assert roles == [("root", 75.0), ("unrelated", 70.0)]


# ------------------------------------------------------------------ BR-06 và lỗi VM
def test_br06_moi_vm_mot_lan_chay(client, admin_h, ssh):
    assert start(client, admin_h).status_code == 202
    r = start(client, admin_h, scenario="memory")
    assert r.status_code == 409 and _err(r) == "fault_host_busy"
    assert start(client, admin_h, host="db").status_code == 202  # VM khác thì được
    assert len([c for c in ssh.calls if "start" in c[1]]) == 2


def test_vm_tu_choi(client, admin_h, ssh):
    ssh.fail_next = ("demo-app đang không chạy, không thể thử dừng", 1)
    r = start(client, admin_h, scenario="service-stop", params={"service": "demo-app"})
    assert r.status_code == 409 and _err(r) == "fault_vm_refused"
    run = client.get("/api/faults/runs", headers=admin_h).json()["items"][0]
    assert run["status"] == "failed" and "không chạy" in run["error"]
    assert start(client, admin_h).status_code == 202  # lần hỏng không giữ chỗ VM


def test_vm_khong_ket_noi_duoc_thi_go_cho_chac(client, admin_h, ssh):
    ssh.fail_next = ("web: quá 15 s không phản hồi", None)
    r = start(client, admin_h)
    assert r.status_code == 503 and _err(r) == "vm_unreachable"
    assert ssh.calls[-1] == ("web", "cpu stop")
    log = client.get("/api/audit?action=fault_start", headers=admin_h).json()["items"][0]
    assert log["detail"]["status"] == "failed"


# ------------------------------------------------------------------ khởi động lại backend (luồng 6)
def test_khoi_dong_lai_go_lan_chay_do(app, client, admin_h, ssh, clock):
    web = start(client, admin_h).json()["id"]
    db_run = start(client, admin_h, host="db").json()["id"]
    ssh.active.pop("db")                   # VM db đã tự gỡ khi hết duration
    app.state.fault_runner.recover_on_startup()
    a = client.get(f"/api/faults/runs/{web}", headers=admin_h).json()
    b = client.get(f"/api/faults/runs/{db_run}", headers=admin_h).json()
    assert a["status"] == "completed" and a["valid"] is False and "web" not in ssh.active
    assert b["status"] == "cancelled" and b["valid"] is False
    assert all("khởi động lại" in r["invalid_reasons"][-1] for r in (a, b))


def test_go_loi_that_bai_thi_thu_lai(app, client, admin_h, ssh, clock):
    rid = start(client, admin_h, hold_s=30).json()["id"]
    ssh.fail_next = ("web: quá 15 s không phản hồi", None)
    tick(app, clock, 31)
    assert client.get(f"/api/faults/runs/{rid}", headers=admin_h).json()["status"] == "running"
    tick(app, clock, 2)
    assert client.get(f"/api/faults/runs/{rid}", headers=admin_h).json()["status"] in ("recovering", "completed")


# ------------------------------------------------------------------ sự cố thử nghiệm (BR-09)
def _incident(client, h, alertname, host="web"):
    items = client.get(f"/api/incidents?alertname={alertname}&host={host}", headers=h).json()["items"]
    assert len(items) == 1
    return client.get(f"/api/incidents/{items[0]['id']}", headers=h).json()


def test_su_co_do_kich_ban_loi_gan_nhan_thu_nghiem(app, client, admin_h, operator_h, clock):
    rid = start(client, admin_h, scenario="service-stop", params={"service": "nginx"}).json()["id"]
    clock.advance(39.4)
    root_starts = (clock.now().timestamp() - 5)
    root_starts = datetime.fromtimestamp(root_starts, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    send(client, payload(am_alert("NginxDown", service="nginx", starts=root_starts, clock=clock)))
    clock.advance(3)
    send(client, payload(am_alert("HostHighCpu", host="db", clock=clock, severity="warning")))  # không liên quan
    tick(app, clock, 31)                   # gỡ lỗi (root + linger 30 s)
    clock.advance(25)                      # nhiễu lúc khôi phục: vẫn do kịch bản lỗi gây ra
    send(client, payload(am_alert("EndpointDown", instance="web:80", service="nginx", clock=clock)))

    nginx = _incident(client, operator_h, "NginxDown")
    assert nginx["fault_run_id"] == rid and nginx["is_false_positive"] is False and nginx["status"] == "open"
    ev = [e for e in nginx["events"] if e["type"] == "fault_run"]
    assert len(ev) == 1 and ev[0]["user"] is None
    assert ev[0]["content"] == f"Do kịch bản lỗi #{rid} (dừng nginx) gây ra lúc 2026-11-26T07:00:00Z"
    assert ev[0]["data"]["fault_run_id"] == rid and ev[0]["data"]["role"] == "root" and ev[0]["data"]["case"] == "dừng nginx"
    assert ev[0]["data"]["injected_at"] == "2026-11-26T07:00:00Z"
    assert all(e["data"] is None for e in nginx["events"] if e["type"] != "fault_run")
    assert _incident(client, operator_h, "EndpointDown")["fault_run_id"] == rid
    cpu = _incident(client, operator_h, "HostHighCpu", host="db")
    assert cpu["fault_run_id"] is None and not any(e["type"] == "fault_run" for e in cpu["events"])

    # Đợt mới của cùng sự cố trong cùng lần chạy: không thêm dòng thời gian thứ hai
    send(client, payload(am_alert("NginxDown", service="nginx", status="resolved", starts=root_starts, clock=clock)))
    clock.advance(2)
    send(client, payload(am_alert("NginxDown", service="nginx", clock=clock)))
    nginx = _incident(client, operator_h, "NginxDown")
    assert nginx["episode_count"] == 2 and len([e for e in nginx["events"] if e["type"] == "fault_run"]) == 1

    # Bộ lọc ẩn/hiện sự cố thử nghiệm
    names = lambda q: sorted(i["alertname"] for i in client.get(f"/api/incidents{q}", headers=operator_h).json()["items"])  # noqa: E731
    assert names("?test=true") == ["EndpointDown", "NginxDown"]
    assert names("?test=false") == ["HostHighCpu"]
    assert len(names("")) == 3


def test_canh_bao_truoc_khi_gay_loi_khong_la_thu_nghiem(app, client, admin_h, operator_h, clock):
    send(client, payload(am_alert("NginxDown", service="nginx", clock=clock)))  # sự cố thật, chưa chạy kịch bản
    start(client, admin_h, scenario="service-stop", params={"service": "nginx"})
    assert _incident(client, operator_h, "NginxDown")["fault_run_id"] is None


def test_ti_le_bao_gia_khong_tinh_su_co_thu_nghiem(app, client, admin_h, operator_h, clock):
    # 3 sự cố thật trên db (1 báo giả), 1 sự cố thử nghiệm trên web (bị đánh dấu báo giả nhầm: vẫn không tính)
    for i, name in enumerate(("HostHighCpu", "HostHighMemory", "PostgresDown")):
        send(client, payload(am_alert(name, host="db", instance=f"db-{i}", clock=clock, severity="warning")))
    _complete(app, client, admin_h, clock, 112.0)
    ids = {i["alertname"] + ("*" if i["fault_run_id"] else ""): i["id"]
           for i in client.get("/api/incidents", headers=operator_h).json()["items"]}
    assert set(ids) == {"HostHighCpu", "HostHighMemory", "PostgresDown", "HostHighCpu*"}
    for key in ("HostHighCpu", "HostHighCpu*"):
        r = client.post(f"/api/incidents/{ids[key]}/false-positive", headers=operator_h, json={"reason": "Tải nền ngắn hợp lệ"})
        assert r.status_code == 200

    r = client.get("/api/reports/false-positives", headers=operator_h)
    assert r.status_code == 200
    body = r.json()
    assert body | {"by_alertname": None} == {"from": None, "to": None, "incidents": 4, "test_excluded": 1, "total": 3,
                                            "false_positive": 1, "rate": pytest.approx(1 / 3), "by_alertname": None}
    assert body["by_alertname"][0] == {"alertname": "HostHighCpu", "total": 1, "false_positive": 1, "rate": 1.0}
    assert {g["alertname"] for g in body["by_alertname"]} == {"HostHighCpu", "HostHighMemory", "PostgresDown"}

    later = client.get("/api/reports/false-positives?from=2030-01-01T00:00:00Z", headers=operator_h).json()
    assert later["incidents"] == 0 and later["rate"] is None and later["by_alertname"] == []
    assert client.get("/api/reports/false-positives").status_code == 401


# ------------------------------------------------------------------ báo cáo
def _complete(app, client, h, clock, root_after: float, **body) -> int:
    rid = start(client, h, **body).json()["id"]
    clock.advance(root_after)
    run = client.get(f"/api/faults/runs/{rid}", headers=h).json()
    send(client, payload(am_alert(run["root_alert"], host=run["host"], fp=f"fp-{rid}", clock=clock,
                                  service=(body.get("params") or {}).get("service", ""))))
    tick(app, clock, 31)
    send(client, payload(am_alert(run["root_alert"], host=run["host"], fp=f"fp-{rid}", status="resolved", clock=clock,
                                  starts=None)))
    tick(app, clock, 200)
    return rid


def test_bao_cao_csv_va_markdown(app, client, admin_h, clock):
    _complete(app, client, admin_h, clock, 112.0)
    _complete(app, client, admin_h, clock, 115.8)
    _complete(app, client, admin_h, clock, 39.4, scenario="service-stop", params={"service": "nginx"})
    r = client.get("/api/reports/fault-runs?format=csv", headers=admin_h)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(r.text.lstrip("﻿"))))
    assert [(x["case"], x["root_s"]) for x in rows] == [("cpu web", "112.0"), ("cpu web", "115.8"), ("dừng nginx", "39.4")]
    md = client.get("/api/reports/fault-runs?format=md", headers=admin_h).text
    assert "| cpu web | HostHighCpu | 2 | 2 | 112,0 | 113,9 | 113,9 | 115,8 |" in md
    assert "group_wait 5 s" in md
    assert client.get("/api/reports/fault-runs?format=pdf", headers=admin_h).status_code == 422


# ------------------------------------------------------------------ khớp cấu hình lab
def test_danh_muc_khop_cau_hinh_lab():
    from app.services.fault_catalog import ALERT_FOR_S, LAB_CONFIG
    prom = yaml.safe_load((ROOT / "monitor/prometheus/prometheus.yml").read_text(encoding="utf-8"))
    am = yaml.safe_load((ROOT / "monitor/alertmanager/alertmanager.yml").read_text(encoding="utf-8"))
    rules = yaml.safe_load((ROOT / "monitor/prometheus/rules/alerts.yml").read_text(encoding="utf-8"))
    sec = lambda s: int(s[:-1]) * {"s": 1, "m": 60}[s[-1]]  # noqa: E731
    assert sec(prom["global"]["scrape_interval"]) == LAB_CONFIG["scrape_interval_s"]
    assert sec(prom["global"]["evaluation_interval"]) == LAB_CONFIG["evaluation_interval_s"]
    assert sec(am["route"]["group_wait"]) == LAB_CONFIG["group_wait_s"]
    fors = {r["alert"]: sec(r["for"]) for g in rules["groups"] for r in g["rules"] if "alert" in r and "for" in r}
    assert {k: fors[k] for k in ALERT_FOR_S} == ALERT_FOR_S


def test_danh_muc_khop_obslab_fault():
    """Giới hạn tham số của portal không rộng hơn giới hạn trên VM (faults/obslab-fault)."""
    script = (ROOT / "faults/obslab-fault").read_text(encoding="utf-8")
    for needle in ('int_param latency_ms "$v" 100 7000', 'int_param error_rate "$v" 1 100',
                   'echo 97 || echo 99'):
        assert needle in script


# ------------------------------------------------------------------ chế độ xem thử: giả lập, không đụng VM
def test_che_do_xem_thu_gia_lap_ca_vong_doi(settings, clock, tmp_path):
    import time as _time

    from fastapi.testclient import TestClient

    from app.db.migrate import upgrade
    from app.main import create_app
    from tests.conftest import login
    settings.fake_prometheus = True
    # CSDL file, không dùng SQLite trong bộ nhớ: luồng giả lập gửi cảnh báo song song với request của test, mà bản trong
    # bộ nhớ chỉ có MỘT kết nối dùng chung (StaticPool) nên commit của luồng này cắt savepoint của luồng kia.
    if settings.database_url.startswith("sqlite"):
        settings.database_url = f"sqlite:///{(tmp_path / 'sim.db').as_posix()}"
    app = create_app(settings, clock)  # không truyền SSH giả: app tự dùng SimulatedFaultSSH
    upgrade(app.state.db.engine)
    sim = app.state.fault_runner.ssh
    sim.speed = 1000.0                 # thời gian phát hiện 39 s -> 0,04 s
    with TestClient(app) as c:
        h = login(c, "admin", "admin-pass-123")
        assert all(s["simulated"] for s in c.get("/api/faults/scenarios", headers=h).json())
        rid = c.post("/api/faults/runs", headers=h, json={"scenario": "service-stop", "host": "web",
                                                          "params": {"service": "nginx"}}).json()["id"]
        for _ in range(100):
            _time.sleep(0.02)
            if c.get(f"/api/faults/runs/{rid}", headers=h).json()["alerts"]:
                break
        detail = c.get(f"/api/faults/runs/{rid}", headers=h).json()
        assert [a["alertname"] for a in detail["alerts"]] == ["NginxDown"] and detail["alerts"][0]["role"] == "root"
        inc = c.get("/api/incidents?alertname=NginxDown", headers=h).json()["items"][0]
        assert inc["firing"] is True


def test_che_do_that_khong_bao_gia_lap(client, admin_h):
    assert not any(s["simulated"] for s in client.get("/api/faults/scenarios", headers=admin_h).json())
