"""Phần 5: nạp runbook từ runbooks/*.md, xem theo alertname, gắn vào sự cố."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services import runbooks as svc

REPO_RUNBOOKS = Path(__file__).resolve().parents[3] / "runbooks"
ALERTS_YML = Path(__file__).resolve().parents[3] / "monitor" / "prometheus" / "rules" / "alerts.yml"

RB = """---
alertname: {name}
title: {title}
severity: warning
category: host
status: {status}
---

# {name}

## Ý nghĩa
Nội dung thử.
"""


def _err(r) -> str:
    return r.json()["error"]["code"]


def test_nap_luc_khoi_dong_du_13_runbook_cua_repo(client, operator_h):
    rows = client.get("/api/runbooks", headers=operator_h).json()
    files = sorted(p.stem for p in REPO_RUNBOOKS.glob("*.md") if p.name != "README.md")
    assert [r["alertname"] for r in rows] == files and len(files) == 13
    assert "body_md" not in rows[0]  # danh sách không kèm nội dung


def test_moi_canh_bao_trong_luat_deu_co_runbook(client, operator_h):
    import yaml
    rules = yaml.safe_load(ALERTS_YML.read_text(encoding="utf-8"))
    names = {r["alert"] for g in rules["groups"] for r in g["rules"] if "alert" in r}
    have = {r["alertname"] for r in client.get("/api/runbooks", headers=operator_h).json()}
    assert names <= have, f"Cảnh báo thiếu runbook: {names - have}"


def test_xem_mot_runbook(client, operator_h):
    r = client.get("/api/runbooks/NginxDown", headers=operator_h).json()
    assert r["title"] and r["severity"] == "critical" and r["status"] == "draft"
    assert r["source_path"] == "runbooks/NginxDown.md"
    assert r["body_md"].startswith("# NginxDown") and "---" not in r["body_md"].splitlines()[0]
    assert _err(client.get("/api/runbooks/KhongCo", headers=operator_h)) == "not_found"
    assert client.get("/api/runbooks/..%2Fetc", headers=operator_h).status_code in (404, 422)


def test_su_co_hien_runbook_theo_alertname(client, operator_h):
    from tests.test_incidents import alert, payload, send
    send(client, payload(alert()))
    inc_id = client.get("/api/incidents", headers=operator_h).json()["items"][0]["id"]
    rb = client.get(f"/api/incidents/{inc_id}", headers=operator_h).json()["runbook"]
    assert rb["alertname"] == "NginxDown" and rb["title"]


def test_nap_lai_phat_hien_them_sua_xoa_va_loi(app, client, admin_h, operator_h, tmp_path):
    app.state.settings.runbooks_dir = str(tmp_path)
    (tmp_path / "README.md").write_text("bỏ qua", encoding="utf-8")
    (tmp_path / "HostHighCpu.md").write_text(RB.format(name="HostHighCpu", title="CPU cao", status="reviewed"), encoding="utf-8")
    (tmp_path / "SaiTen.md").write_text(RB.format(name="KhacTen", title="x", status="draft"), encoding="utf-8")
    (tmp_path / "KhongFrontMatter.md").write_text("# chỉ có nội dung", encoding="utf-8")
    r = client.post("/api/runbooks/reload", headers=admin_h).json()
    assert r["loaded"] == 1 and r["updated"] == 1 and r["removed"] == 12  # 13 của repo, giữ lại HostHighCpu
    assert len(r["errors"]) == 2 and any("khác tên file" in e for e in r["errors"])
    assert client.get("/api/runbooks/HostHighCpu", headers=operator_h).json()["status"] == "reviewed"
    # Nạp lại không đổi gì
    r = client.post("/api/runbooks/reload", headers=admin_h).json()
    assert r["updated"] == 0 and r["removed"] == 0
    # Sửa file -> cập nhật
    (tmp_path / "HostHighCpu.md").write_text(RB.format(name="HostHighCpu", title="CPU cao (sửa)", status="weird"),
                                            encoding="utf-8")
    assert client.post("/api/runbooks/reload", headers=admin_h).json()["updated"] == 1
    got = client.get("/api/runbooks/HostHighCpu", headers=operator_h).json()
    assert got["title"] == "CPU cao (sửa)" and got["status"] == "draft"  # trạng thái lạ quy về draft
    entry = client.get("/api/audit?action=runbooks_reload", headers=admin_h).json()["items"][0]
    assert entry["user"] == "admin" and entry["detail"]["updated"] == 1


def test_operator_khong_nap_lai_duoc(client, operator_h):
    assert client.post("/api/runbooks/reload", headers=operator_h).status_code == 403


@pytest.mark.parametrize("text,msg", [
    ("---\n- a\n- b\n---\nx", "không phải dạng"),
    ("---\nalertname: 'a b'\n---\nx", "alertname không hợp lệ"),
])
def test_parse_loi(tmp_path, text, msg):
    p = tmp_path / "X.md"
    p.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match=msg):
        svc.parse(p)


def test_thu_muc_khong_ton_tai_dung_runbook_cua_repo():
    assert svc.resolve_dir("/khong/co/thu/muc") == REPO_RUNBOOKS
