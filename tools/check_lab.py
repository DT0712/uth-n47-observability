"""Kiểm tra nhanh lab đã chạy đúng chưa.

  python tools/check_lab.py                # kiểm tra một lần
  python tools/check_lab.py --wait 180     # thử lại tới 180 giây (dùng ngay sau vagrant up)
  python tools/check_lab.py --test-alert   # thêm: gửi cảnh báo thử qua Alertmanager tới alert-recorder

Kiểm tra:
  1. Mọi target trong Prometheus đều UP, có đủ 3 VM
  2. Đủ chuỗi ngưỡng lab:threshold:* (so với thresholds.yml), luật cảnh báo đã load, không rule lỗi
  3. Alertmanager, alert-recorder sống
  4. Grafana sống, datasource Prometheus có dữ liệu, có đủ 5 dashboard và dashboard có dữ liệu
  5. (--test-alert) Alertmanager chuyển cảnh báo tới alert-recorder
Thoát với mã 1 nếu có mục thất bại.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.common import AM_URL, ENV, GRAFANA_URL, PROM_URL, ROOT, WEBHOOK_URL, http  # noqa: E402

EXPECTED_DASHBOARDS = {"lab-overview", "lab-host", "lab-service", "lab-nginx", "lab-postgres"}
EXPECTED_HOSTS = {"monitor", "web", "db"}
THRESHOLDS_FILE = ROOT / "monitor" / "prometheus" / "rules" / "thresholds.yml"
# Truy vấn đại diện cho từng dashboard: có kết quả = dashboard có dữ liệu để vẽ.
DASHBOARD_PROBES = {
    "lab-overview": "up",
    "lab-host": "lab:host_cpu_usage:percent",
    "lab-service": 'lab:service_request_rate:rps',
    "lab-nginx": 'nginx_up{job="nginx"}',
    "lab-postgres": 'pg_up{job="postgres"}',
}


def expected_thresholds() -> int:
    return len(re.findall(r"^\s*-\s*record:\s*lab:threshold:", THRESHOLDS_FILE.read_text(encoding="utf-8"), re.M))


def check_once(verbose: bool) -> list:
    problems = []

    # 1. targets
    try:
        res = http("GET", f"{PROM_URL}/api/v1/targets?state=active")["data"]["activeTargets"]
        if verbose:
            print(f"Prometheus targets ({len(res)}):")
        for t in sorted(res, key=lambda t: (t["labels"]["job"], t["labels"].get("instance", ""))):
            line = f"  {t['health'].upper():<7} {t['labels']['job']:<18} {t['labels'].get('instance', '')}"
            if t["health"] != "up":
                line += f"  <- {t.get('lastError', '')}"
                problems.append(f"target {t['labels']['job']}/{t['labels'].get('instance')} {t['health']}")
            if verbose:
                print(line)
        if not res:
            problems.append("Prometheus chưa có target nào")
        hosts = {t["labels"].get("instance") for t in res if t["labels"]["job"] == "node"}
        if EXPECTED_HOSTS - hosts:
            problems.append(f"thiếu Node Exporter của VM {sorted(EXPECTED_HOSTS - hosts)}")
    except Exception as e:
        problems.append(f"Prometheus không truy cập được ({PROM_URL}): {e}")
        return problems

    # 2. ngưỡng + rules
    try:
        q = urllib.parse.quote('{__name__=~"lab:threshold:.*"}')
        thr = http("GET", f"{PROM_URL}/api/v1/query?query={q}")["data"]["result"]
        groups = http("GET", f"{PROM_URL}/api/v1/rules")["data"]["groups"]
        n_alerts = sum(1 for g in groups for r in g["rules"] if r["type"] == "alerting")
        bad = [r["name"] for g in groups for r in g["rules"] if r.get("health") not in (None, "ok", "unknown")]
        want = expected_thresholds()
        if verbose:
            print(f"Ngưỡng nạp: {len(thr)}/{want} | luật cảnh báo: {n_alerts} | nhóm rule: {len(groups)}")
        if len(thr) < want:
            problems.append(f"chỉ có {len(thr)}/{want} chuỗi lab:threshold:*")
        if bad:
            problems.append(f"rule lỗi: {bad}")
    except Exception as e:
        problems.append(f"không đọc được rules: {e}")

    # 3. Alertmanager + webhook
    for name, url in (("Alertmanager", f"{AM_URL}/-/ready"), ("alert-recorder", f"{WEBHOOK_URL}/health")):
        try:
            http("GET", url, timeout=5)
            if verbose:
                print(f"{name}: OK")
        except Exception as e:
            problems.append(f"{name} lỗi: {e}")

    # 4. Grafana
    auth = (ENV["GRAFANA_ADMIN_USER"], ENV["GRAFANA_ADMIN_PASSWORD"])
    try:
        h = http("GET", f"{GRAFANA_URL}/api/health", timeout=5)
        q = urllib.parse.quote("up")
        r = http("GET", f"{GRAFANA_URL}/api/datasources/proxy/uid/prometheus/api/v1/query?query={q}", auth=auth)
        n = len(r["data"]["result"])
        dashes = http("GET", f"{GRAFANA_URL}/api/search?type=dash-db", auth=auth)
        uids = {d["uid"] for d in dashes}
        if verbose:
            print(f"Grafana {h.get('version')}: database={h.get('database')}, truy vấn qua datasource trả {n} series, "
                  f"dashboard: {sorted(uids & EXPECTED_DASHBOARDS)}")
        if n == 0:
            problems.append("Grafana truy vấn Prometheus không có dữ liệu")
        missing = EXPECTED_DASHBOARDS - uids
        if missing:
            problems.append(f"thiếu dashboard {sorted(missing)}")
        empty = []
        for uid, expr in DASHBOARD_PROBES.items():
            q = urllib.parse.quote(expr)
            r = http("GET", f"{GRAFANA_URL}/api/datasources/proxy/uid/prometheus/api/v1/query?query={q}", auth=auth)
            if not r["data"]["result"]:
                empty.append(uid)
        if verbose:
            print(f"Dashboard có dữ liệu: {len(DASHBOARD_PROBES) - len(empty)}/{len(DASHBOARD_PROBES)}")
        if empty:
            problems.append(f"dashboard chưa có dữ liệu: {empty}")
    except Exception as e:
        problems.append(f"Grafana lỗi ({GRAFANA_URL}): {e}")

    return problems


def test_alert(timeout: float = 60) -> bool:
    """Gửi một cảnh báo giả thẳng vào Alertmanager rồi chờ nó xuất hiện ở alert-recorder."""
    marker = f"check-{int(time.time())}"
    now = datetime.now(timezone.utc)
    alert = [{
        "labels": {"alertname": "LabTestAlert", "severity": "info", "instance": "check_lab", "test_id": marker},
        "annotations": {"summary": "Cảnh báo thử của tools/check_lab.py --test-alert"},
        "startsAt": now.isoformat(),
        "endsAt": (now + timedelta(minutes=2)).isoformat(),
    }]
    print(f"Gửi cảnh báo thử LabTestAlert (test_id={marker}) tới Alertmanager ...", flush=True)
    http("POST", f"{AM_URL}/api/v2/alerts", alert)
    deadline = time.time() + timeout
    while time.time() < deadline:
        items = http("GET", f"{WEBHOOK_URL}/alerts?limit=200")["alerts"]
        hit = [a for a in items if a.get("labels", {}).get("test_id") == marker]
        if hit:
            print(f"  alert-recorder đã nhận lúc {hit[0]['received_at']} "
                  f"(ghi vào data/alerts/alerts.jsonl) — đường Alertmanager → alert-recorder OK")
            return True
        time.sleep(2)
    print(f"  alert-recorder KHÔNG nhận được cảnh báo thử sau {timeout:.0f}s")
    return False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wait", type=int, default=0, help="thử lại tới N giây")
    ap.add_argument("--test-alert", action="store_true", help="gửi cảnh báo thử qua Alertmanager tới alert-recorder")
    a = ap.parse_args()
    deadline = time.time() + a.wait
    while True:
        last = time.time() >= deadline
        problems = check_once(verbose=last)
        if not problems:
            if not last:
                check_once(verbose=True)
            if a.test_alert and not test_alert():
                print("\nCÓ VẤN ĐỀ: cảnh báo thử không tới alert-recorder")
                sys.exit(1)
            print("\nTẤT CẢ OK ✓")
            return
        if last:
            print("\nCÓ VẤN ĐỀ:")
            for p in problems:
                print(f"  - {p}")
            sys.exit(1)
        print(f"  chưa sẵn sàng ({len(problems)} vấn đề), thử lại ...", flush=True)
        time.sleep(10)


if __name__ == "__main__":
    main()
