"""Phần 3: host/service (CRUD) và dữ liệu mẫu 3 VM."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest


def _err(r) -> str:
    return r.json()["error"]["code"]


def _host(client, h, name):
    return next(x for x in client.get("/api/hosts", headers=h).json() if x["name"] == name)


NEW_HOST = {"name": "cache", "address": "192.168.56.13", "prom_instance": "cache", "grafana_dashboard_uid": "lab-host"}


# ------------------------------------------------------------------ dữ liệu mẫu
def test_du_lieu_mau_3_vm_khop_prometheus(client, operator_h):
    rows = client.get("/api/hosts", headers=operator_h).json()
    assert [h["name"] for h in rows] == ["db", "monitor", "web"]
    web = _host(client, operator_h, "web")
    assert web["address"] == "192.168.56.11" and web["prom_instance"] == "web"
    assert {s["name"]: s["prom_labels"] for s in web["services"]} == {
        "demo-app": {"job": "demo-app", "service": "demo-app"}, "nginx": {"job": "nginx", "service": "nginx"}}
    db = _host(client, operator_h, "db")
    assert db["services"][0]["probe_instance"] == "db:5432"


def test_du_lieu_mau_khong_nap_lai(app, client, db):
    from app.db import models as m
    from app.services.inventory import seed_inventory
    assert seed_inventory(db) == 0
    assert db.query(m.Host).count() == 3


def test_link_grafana_kem_bien_va_khoang_thoi_gian(client, operator_h):
    web = _host(client, operator_h, "web")
    u = urlparse(web["grafana_url"])
    assert u.netloc == "localhost:3000" and u.path == "/d/lab-host"
    assert parse_qs(u.query) == {"var-instance": ["web"], "from": ["now-1h"], "to": ["now"]}
    app_svc = next(s for s in web["services"] if s["name"] == "demo-app")
    assert parse_qs(urlparse(app_svc["grafana_url"]).query)["var-service"] == ["demo-app"]


# ------------------------------------------------------------------ host
def test_tao_sua_xoa_host(client, admin_h, operator_h):
    r = client.post("/api/hosts", headers=admin_h, json=NEW_HOST)
    assert r.status_code == 201 and r.json()["services"] == [] and r.json()["enabled"] is True
    hid = r.json()["id"]
    assert client.get(f"/api/hosts/{hid}", headers=operator_h).json()["name"] == "cache"
    r = client.patch(f"/api/hosts/{hid}", headers=admin_h, json={**NEW_HOST, "enabled": False, "description": "tạm tắt"})
    assert r.status_code == 200 and r.json()["enabled"] is False
    assert client.delete(f"/api/hosts/{hid}", headers=admin_h).status_code == 204
    assert _err(client.get(f"/api/hosts/{hid}", headers=operator_h)) == "not_found"


def test_trung_ten_host(client, admin_h):
    r = client.post("/api/hosts", headers=admin_h, json={**NEW_HOST, "name": "web"})
    assert r.status_code == 409 and _err(r) == "duplicate"
    db_id = _host(client, admin_h, "db")["id"]
    r = client.patch(f"/api/hosts/{db_id}", headers=admin_h, json={**NEW_HOST, "name": "web"})
    assert r.status_code == 409


@pytest.mark.parametrize("bad", [
    {"name": "Web 1"},                          # chữ hoa, khoảng trắng
    {"prom_instance": 'web"} or vector(1) #'},  # thử chèn PromQL qua nhãn
    {"grafana_dashboard_uid": "../etc"},
])
def test_host_du_lieu_sai(client, admin_h, bad):
    r = client.post("/api/hosts", headers=admin_h, json={**NEW_HOST, **bad})
    assert r.status_code == 422 and _err(r) == "validation_error"


def test_xoa_host_xoa_kem_service(client, admin_h, db):
    from app.db import models as m
    web_id = _host(client, admin_h, "web")["id"]
    assert client.delete(f"/api/hosts/{web_id}", headers=admin_h).status_code == 204
    db.expire_all()
    assert db.query(m.Service).filter_by(host_id=web_id).count() == 0
    log = client.get("/api/audit?action=delete", headers=admin_h).json()["items"][0]
    assert log["detail"] == {"name": "web", "services": ["demo-app", "nginx"]}


# ------------------------------------------------------------------ service
def test_tao_sua_xoa_service(client, admin_h, operator_h):
    db_id = _host(client, admin_h, "db")["id"]
    body = {"host_id": db_id, "name": "redis", "kind": "database", "prom_labels": {"job": "redis"},
            "probe_instance": "db:6379"}
    r = client.post("/api/services", headers=admin_h, json=body)
    assert r.status_code == 201 and r.json()["grafana_url"] is None
    sid = r.json()["id"]
    assert client.get(f"/api/services/{sid}", headers=operator_h).json()["name"] == "redis"
    assert "redis" in [s["name"] for s in _host(client, operator_h, "db")["services"]]
    r = client.patch(f"/api/services/{sid}", headers=admin_h, json={**body, "enabled": False})
    assert r.status_code == 200 and r.json()["enabled"] is False
    assert client.delete(f"/api/services/{sid}", headers=admin_h).status_code == 204
    assert client.get(f"/api/services/{sid}", headers=operator_h).status_code == 404


def test_chuyen_service_sang_host_khac(client, admin_h):
    web = _host(client, admin_h, "web")
    db_id = _host(client, admin_h, "db")["id"]
    nginx = next(s for s in web["services"] if s["name"] == "nginx")
    body = {k: nginx[k] for k in ("name", "kind", "prom_labels", "probe_instance", "grafana_dashboard_uid")}
    r = client.patch(f"/api/services/{nginx['id']}", headers=admin_h, json={**body, "host_id": db_id})
    assert r.status_code == 200 and r.json()["host_id"] == db_id
    assert "var-instance=db" in r.json()["grafana_url"]


def test_service_trung_ten_tren_cung_host_va_host_khong_ton_tai(client, admin_h):
    web_id = _host(client, admin_h, "web")["id"]
    body = {"host_id": web_id, "name": "nginx", "kind": "web", "prom_labels": {"job": "nginx"}}
    r = client.post("/api/services", headers=admin_h, json=body)
    assert r.status_code == 409 and _err(r) == "duplicate"
    r = client.post("/api/services", headers=admin_h, json={**body, "host_id": 999})
    assert r.status_code == 422 and r.json()["error"]["details"][0]["field"] == "host_id"


@pytest.mark.parametrize("labels", [
    {},                                  # không có nhãn
    {"job": 'nginx"}'},                  # chèn dấu ngoặc
    {"1job": "nginx"},                   # tên nhãn sai
    {f"k{i}": "v" for i in range(9)},    # quá 8 nhãn
])
def test_nhan_prometheus_an_toan(client, admin_h, labels):
    web_id = _host(client, admin_h, "web")["id"]
    r = client.post("/api/services", headers=admin_h,
                    json={"host_id": web_id, "name": "x", "kind": "other", "prom_labels": labels})
    assert r.status_code == 422


# ------------------------------------------------------------------ phân quyền, nhật ký
@pytest.mark.parametrize("method,path", [
    ("post", "/api/hosts"), ("patch", "/api/hosts/1"), ("delete", "/api/hosts/1"),
    ("post", "/api/services"), ("patch", "/api/services/1"), ("delete", "/api/services/1"),
])
def test_operator_chi_xem(client, operator_h, method, path):
    kw = {"json": NEW_HOST} if method in ("post", "patch") else {}
    assert getattr(client, method)(path, headers=operator_h, **kw).status_code == 403


def test_nhat_ky_ghi_thay_doi(client, admin_h):
    db_id = _host(client, admin_h, "db")["id"]
    db = _host(client, admin_h, "db")
    body = {k: db[k] for k in ("name", "address", "prom_instance", "grafana_dashboard_uid", "description", "enabled")}
    client.patch(f"/api/hosts/{db_id}", headers=admin_h, json={**body, "address": "10.0.0.12"})
    entry = client.get("/api/audit?action=update", headers=admin_h).json()["items"][0]
    assert entry["object_type"] == "host" and entry["detail"] == {"address": ["192.168.56.12", "10.0.0.12"]}
