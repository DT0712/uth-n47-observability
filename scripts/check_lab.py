"""Kiểm tra nhanh lab đã chạy đúng chưa.

  python scripts/check_lab.py            # kiểm tra một lần
  python scripts/check_lab.py --wait 180 # thử lại tới 180 giây (dùng ngay sau docker compose up -d)

Kiểm tra:
  1. Mọi target trong Prometheus đều UP
  2. Chuỗi ngưỡng lab:threshold:* đã được nạp và các luật cảnh báo đã load
  3. Alertmanager, webhook-receiver sống
  4. Grafana sống, datasource Prometheus truy vấn được, có đủ 3 dashboard
Thoát với mã 1 nếu có mục thất bại.
"""

from __future__ import annotations

import argparse
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.common import AM_URL, ENV, GRAFANA_URL, PROM_URL, WEBHOOK_URL, http  # noqa: E402

EXPECTED_DASHBOARDS = {"lab-overview", "lab-host", "lab-service"}


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
        if verbose:
            print(f"Ngưỡng nạp: {len(thr)} | luật cảnh báo: {n_alerts} | nhóm rule: {len(groups)}")
        if len(thr) < 7:
            problems.append(f"chỉ có {len(thr)}/7 chuỗi lab:threshold:*")
        if bad:
            problems.append(f"rule lỗi: {bad}")
    except Exception as e:
        problems.append(f"không đọc được rules: {e}")

    # 3. Alertmanager + webhook
    for name, url in (("Alertmanager", f"{AM_URL}/-/ready"), ("webhook-receiver", f"{WEBHOOK_URL}/health")):
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
    except Exception as e:
        problems.append(f"Grafana lỗi ({GRAFANA_URL}): {e}")

    return problems


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wait", type=int, default=0, help="thử lại tới N giây")
    a = ap.parse_args()
    deadline = time.time() + a.wait
    while True:
        last = time.time() >= deadline
        problems = check_once(verbose=last)
        if not problems:
            if not last:
                check_once(verbose=True)
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
