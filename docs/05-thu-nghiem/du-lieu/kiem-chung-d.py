"""Kiểm chứng phương án D trên lab: so sánh cảnh báo hệ quả trong Prometheus trước (gd3-dot3) và sau (gd3-dot4).

  python docs/05-thu-nghiem/du-lieu/kiem-chung-d.py gd3-dot3 gd3-dot4

Với mỗi lần dừng dịch vụ, truy vấn Prometheus (TSDB còn giữ dữ liệu của đợt) trong khoảng [gây lỗi − 15 s, gỡ lỗi + 120 s]:
- ALERTS: cảnh báo hệ quả (EndpointDown, ServiceDown khi không phải cảnh báo gốc) có lên pending/firing không.
  Firing trong Prometheus nhưng bị inhibit thì không có thông báo, nhưng vẫn là cảnh báo sai trên UI Prometheus/Grafana.
- Biểu thức thô của luật cũ và luật D, bước 1 s: thời gian dài nhất đúng liên tục (`for: 30s` cần ≥ 30 s).
Đọc sự kiện từ data/events/faults.jsonl, nếu không có thì từ file <đợt>-su-kien.jsonl cạnh script.
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

PROM = "http://192.168.56.10:9090"
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]

OLD = {
    "EndpointDown": 'probe_success{job=~"blackbox-http|blackbox-tcp",host="%(h)s"} == 0',
    "ServiceDown": 'up{job="demo-app",host="%(h)s"} == 0',
}
NEW = {
    "EndpointDown": '(probe_success{job=~"blackbox-http|blackbox-tcp",host="%(h)s"} == 0)'
                    ' unless on(host) (nginx_up{job="nginx"} == 0 or pg_up{job="postgres"} == 0)'
                    ' unless on(host, service) (up{job="demo-app"} == 0)',
    "ServiceDown": '(up{job="demo-app",host="%(h)s"} == 0) unless on(host) (nginx_up{job="nginx"} == 0)',
}


def q_range(expr: str, start: float, end: float, step: float) -> list:
    qs = urllib.parse.urlencode({"query": expr, "start": start, "end": end, "step": step})
    with urllib.request.urlopen(f"{PROM}/api/v1/query_range?{qs}", timeout=30) as r:
        return json.load(r)["data"]["result"]


def longest_run(result: list, step: float) -> float:
    best = 0.0
    for s in result:
        ts = [float(t) for t, _ in s["values"]]
        run = 0
        for i, t in enumerate(ts):
            run = run + 1 if i and abs(t - ts[i - 1] - step) < 1e-6 else 1
            best = max(best, (run - 1) * step)
    return best


def events(suite: str) -> list:
    src = ROOT / "data" / "events" / "faults.jsonl"
    if not src.exists():
        src = HERE / f"{suite}-su-kien.jsonl"
    evs = [json.loads(l) for l in src.read_text(encoding="utf-8").splitlines() if l.strip()]
    last = {e["fault_id"]: e for e in evs}   # trạng thái cuối của mỗi lần
    return [e for e in last.values()
            if e.get("suite") == suite and e.get("case", "").startswith("dừng") and e.get("status") == "completed"]


def main() -> None:
    print("đợt | trường hợp | n | hệ quả firing trong Prometheus | hệ quả pending | dài nhất luật cũ (s) | dài nhất luật D (s)")
    for suite in sys.argv[1:]:
        by_case: dict = {}
        for e in events(suite):
            by_case.setdefault(e["case"], []).append(e)
        for case, evs in sorted(by_case.items()):
            fired = pend = 0
            old_max = new_max = 0.0
            for e in evs:
                h = e["target"]
                t0, t1 = e["injected_ts_receiver"] - 15, e["recovered_ts_receiver"] + 120
                cons = ["EndpointDown"] + ([] if e["root_alert"] == "ServiceDown" else ["ServiceDown"])
                states = set()
                for s in q_range('ALERTS{alertname=~"%s",host="%s"}' % ("|".join(cons), h), t0, t1, 15):
                    states.add(s["metric"]["alertstate"])
                fired += "firing" in states
                pend += bool(states)
                for name in cons:
                    old_max = max(old_max, longest_run(q_range(OLD[name] % {"h": h}, t0, t1, 1), 1))
                    new_max = max(new_max, longest_run(q_range(NEW[name] % {"h": h}, t0, t1, 1), 1))
            print(f"{suite} | {case} | {len(evs)} | {fired}/{len(evs)} | {pend}/{len(evs)} | {old_max:.0f} | {new_max:.0f}")


if __name__ == "__main__":
    main()
