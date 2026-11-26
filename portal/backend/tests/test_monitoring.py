"""Phần 6: tổng quan, metric, ngưỡng; client Prometheus (cache, timeout). Chỉ dùng Prometheus giả, không gọi mạng."""

from __future__ import annotations

import httpx
import pytest

from app.services.monitoring import step_for
from app.services.prometheus import PrometheusClient, PrometheusError, quote, selector
from tests.test_incidents import alert, payload, send


def _err(r) -> str:
    return r.json()["error"]["code"]


def _id(client, h, name):
    return next(x for x in client.get("/api/hosts", headers=h).json() if x["name"] == name)


# ------------------------------------------------------------------ tổng quan
def test_tong_quan_day_du(client, operator_h):
    send(client, payload(alert()))
    r = client.get("/api/overview", headers=operator_h)
    assert r.status_code == 200
    body = r.json()
    assert body["metrics_available"] is True
    web = next(h for h in body["hosts"] if h["name"] == "web")
    assert web["up"] is True and web["cpu_percent"] == 2.3 and web["memory_percent"] == 37.5
    assert web["disk_percent"] == 21.3  # chỉ phân vùng /, không lấy /mnt/labdisk
    assert web["network_rx_bps"] == 1580.0 and web["uptime_s"] == pytest.approx(6400.0)
    assert web["open_incidents"] == 1 and "var-instance=web" in web["grafana_url"]
    svc = {s["name"]: s for s in web["services"]}
    assert svc["nginx"]["up"] is True and svc["nginx"]["probe_ok"] is True and svc["nginx"]["open_incidents"] == 1
    assert body["open_incidents"] == {"total": 1, "critical": 1, "warning": 0, "firing": 1}
    assert body["latest_incidents"][0]["alertname"] == "NginxDown"
    assert body["faults_running"] == 0 and body["detection_mean_s"] is None


def test_tong_quan_khi_may_down_va_mat_du_lieu(client, operator_h, prom):
    prom.set("up", {"job": "node", "instance": "db"}, 0)
    prom.data = [d for d in prom.data if d[1].get("instance") != "monitor"]  # monitor mất hết dữ liệu
    hosts = {h["name"]: h for h in client.get("/api/overview", headers=operator_h).json()["hosts"]}
    assert hosts["db"]["up"] is False
    assert hosts["monitor"]["up"] is None and hosts["monitor"]["cpu_percent"] is None  # "Không rõ", không phải DOWN


def test_tong_quan_van_dung_khi_prometheus_chet(client, operator_h, prom):
    send(client, payload(alert()))
    prom.fail = True
    body = client.get("/api/overview", headers=operator_h).json()
    assert body["metrics_available"] is False
    assert all(h["cpu_percent"] is None and h["up"] is None for h in body["hosts"])
    assert body["open_incidents"]["total"] == 1  # sự cố vẫn lấy từ CSDL


def test_tong_quan_loc_theo_chip(client, operator_h):
    body = client.get("/api/overview?host=db", headers=operator_h).json()
    assert [h["name"] for h in body["hosts"]] == ["db"]
    body = client.get("/api/overview?service=demo-app", headers=operator_h).json()
    assert [h["name"] for h in body["hosts"]] == ["web"]
    assert [s["name"] for s in body["hosts"][0]["services"]] == ["demo-app"]


def test_thoi_gian_phat_hien_trung_binh_24h(client, operator_h, db, clock):
    from datetime import timedelta

    from app.db import models as m
    now = clock.now()
    uid = db.query(m.User).first().id
    for i, (sec, valid, age_h) in enumerate([(40.0, True, 1), (50.0, True, 2), (99.0, False, 1), (10.0, True, 30)]):
        db.add(m.FaultRun(scenario="cpu", target_host=f"h{i}", hold_s=240, root_alert="HostHighCpu", requested_by=uid,
                          requested_at=now, injected_at=now - timedelta(hours=age_h), status="completed", valid=valid,
                          root_detection_s=sec))
    db.add(m.FaultRun(scenario="cpu", target_host="web", hold_s=240, root_alert="HostHighCpu", requested_by=uid,
                      requested_at=now, status="running"))
    db.commit()
    body = client.get("/api/overview", headers=operator_h).json()
    assert body["detection_mean_s"] == 45.0  # bỏ lần không hợp lệ và lần cũ hơn 24 giờ
    assert body["faults_running"] == 1


# ------------------------------------------------------------------ chuỗi thời gian
def test_chuoi_tong_quan(client, operator_h):
    body = client.get("/api/overview/series?range=1h", headers=operator_h).json()
    assert body["metrics_available"] is True and body["step_s"] == 15
    assert [s["label"] for s in body["cpu"]["series"]] == ["db", "monitor", "web"]
    assert body["cpu"]["series"][0]["threshold"] == 85 and len(body["cpu"]["series"][0]["points"]) == 241
    assert body["requests"]["series"][0]["label"] == "demo-app"
    assert {s["metric"] for s in body["latency"]["series"]} == {"latency_p95", "probe_duration"}
    assert {x["name"]: x["value_s"] for x in body["latency_now"]} == {"demo-app p95": 0.047,
                                                                     "probe http://web/health": 0.004}
    assert len(body["uptime"]) == 3 and all(u["ratio"] == 1 for u in body["uptime"])
    assert client.get("/api/overview/series?range=7d", headers=operator_h).status_code == 422
    assert client.get("/api/overview/series?range=24h", headers=operator_h).json()["step_s"] == 90


def test_chuoi_tong_quan_khi_prometheus_chet(client, operator_h, prom):
    prom.fail = True
    body = client.get("/api/overview/series", headers=operator_h).json()
    assert body["metrics_available"] is False and body["cpu"]["series"] == []


def test_metric_host(client, operator_h):
    web = _id(client, operator_h, "web")
    r = client.get(f"/api/hosts/{web['id']}/metrics?range=6h&metrics=cpu,disk", headers=operator_h)
    body = r.json()
    assert r.status_code == 200 and body["step_s"] == 30  # 6 giờ / 1.000 điểm, làm tròn lên bội 15 s
    assert [(s["metric"], s["label"]) for s in body["series"]] == [
        ("cpu", ""), ("disk", "mountpoint=/"), ("disk", "mountpoint=/mnt/labdisk")]
    assert body["series"][1]["threshold"] == 90 and body["series"][1]["unit"] == "%"
    assert max(len(s["points"]) for s in body["series"]) <= 1001


def test_metric_host_khoang_tuy_chon_va_loi(client, operator_h):
    web = _id(client, operator_h, "web")["id"]
    ok = client.get(f"/api/hosts/{web}/metrics?start=2026-11-25T07:00:00Z&end=2026-11-26T07:00:00Z", headers=operator_h)
    assert ok.status_code == 200 and ok.json()["step_s"] == 90
    for q in ("start=2026-11-25T07:00:00Z", "start=2026-11-26T07:00:00Z&end=2026-11-25T07:00:00Z",
              "start=2026-10-01T00:00:00Z&end=2026-11-26T00:00:00Z", "metrics=cpu,gpu", "range=2h"):
        assert client.get(f"/api/hosts/{web}/metrics?{q}", headers=operator_h).status_code == 422, q
    assert _err(client.get("/api/hosts/999/metrics", headers=operator_h)) == "not_found"


def test_metric_service_theo_loai(client, operator_h):
    web = _id(client, operator_h, "web")
    db_host = _id(client, operator_h, "db")
    app = next(s for s in web["services"] if s["name"] == "demo-app")
    names = [s["metric"] for s in client.get(f"/api/services/{app['id']}/metrics", headers=operator_h).json()["series"]]
    assert names == ["up", "probe_success", "probe_duration", "request_rate", "latency_p95", "error_ratio"]
    pg = db_host["services"][0]
    series = client.get(f"/api/services/{pg['id']}/metrics", headers=operator_h).json()["series"]
    assert [s["metric"] for s in series] == ["up", "probe_success", "connections_usage"]


def test_metric_tra_503_khi_prometheus_chet(client, operator_h, prom):
    prom.fail = True
    web = _id(client, operator_h, "web")
    r = client.get(f"/api/hosts/{web['id']}/metrics", headers=operator_h)
    assert r.status_code == 503 and _err(r) == "prometheus_unavailable"
    assert client.get("/api/thresholds", headers=operator_h).status_code == 503


# ------------------------------------------------------------------ ngưỡng
def test_nguong_hien_hanh(client, operator_h):
    rows = client.get("/api/thresholds", headers=operator_h).json()
    cpu = next(r for r in rows if r["name"] == "host_cpu_usage_percent")
    assert cpu == {"name": "host_cpu_usage_percent", "value": 85.0, "status": "provisional", "basis": "chua do baseline"}


# ------------------------------------------------------------------ an toàn, health
def test_chi_gui_bieu_thuc_trong_danh_muc(client, operator_h, prom):
    client.get("/api/overview?host=web", headers=operator_h)
    client.get("/api/overview/series", headers=operator_h)
    exprs = {e for kind, e in prom.calls if kind != "ready"}
    assert exprs and all(("lab:" in e or e.startswith(("up{", "probe_", "time() - node_boot", "avg_over_time(up{",
                                                       "{__name__"))) for e in exprs), exprs


def test_chen_promql_qua_tham_so_khong_duoc(client, operator_h, prom):
    r = client.get('/api/overview?host=web"} or vector(1) #', headers=operator_h)
    assert r.status_code == 200 and r.json()["hosts"] == []  # chỉ dùng để lọc danh mục, không đưa vào PromQL
    assert not any("vector(1)" in e for _, e in prom.calls)


def test_health_bao_trang_thai_prometheus(client, prom):
    assert client.get("/api/health").json()["prometheus"] is True
    prom.is_ready = False
    body = client.get("/api/health").json()
    assert body["prometheus"] is False and body["status"] == "degraded"


def test_can_dang_nhap(client):
    for path in ("/api/overview", "/api/overview/series", "/api/hosts/1/metrics", "/api/thresholds"):
        assert client.get(path).status_code == 401


# ------------------------------------------------------------------ client Prometheus thật (HTTP giả)
def _client(handler) -> PrometheusClient:
    return PrometheusClient("http://prom:9090", transport=httpx.MockTransport(handler))


def test_client_cache_15s():
    hits = []

    def handler(req: httpx.Request) -> httpx.Response:
        hits.append(str(req.url))
        return httpx.Response(200, json={"status": "success", "data": {"result": [{"metric": {}, "value": [0, "1"]}]}})

    c = _client(handler)
    for _ in range(5):
        c.query('up{job="node"}')
    c.query_range("x", 1000, 4600, 15)
    c.query_range("x", 1003, 4605, 15)  # làm tròn theo bước -> trúng cache
    assert len(hits) == 2 and c.requests == 2


def test_client_loi_va_timeout():
    def bad(req):
        return httpx.Response(400, json={"status": "error", "error": "parse error"})

    def timeout(req):
        raise httpx.ReadTimeout("chậm", request=req)

    with pytest.raises(PrometheusError, match="400"):
        _client(bad).query("x")
    with pytest.raises(PrometheusError, match="Không truy vấn được"):
        _client(timeout).query("x")
    assert _client(timeout).ready() is False


def test_dung_promql_an_toan():
    assert quote('a"b\\c') == '"a\\"b\\\\c"'
    assert selector("up", {"job": "nginx"}) == 'up{job="nginx"}'
    assert selector("probe_success", None, {"instance": ["http://web/health", "db:5432"]}) == \
        'probe_success{instance=~"http://web/health|db:5432"}'
    assert selector("m", {"bad key": "x"}) == "m"  # tên nhãn lạ bị bỏ
    assert step_for(3600) == 15 and step_for(86400) == 90 and step_for(7 * 86400) == 615
