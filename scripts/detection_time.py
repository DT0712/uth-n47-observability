"""Tính THỜI GIAN PHÁT HIỆN cho các kịch bản lỗi.

  thời gian phát hiện = thời điểm webhook-receiver nhận cảnh báo (firing) - thời điểm gây lỗi

Đầu vào:
  data/events/faults.jsonl   (do scripts/fault.py ghi)
  data/alerts/alerts.jsonl   (do webhook-receiver ghi)
Đầu ra:
  results/detection/detection-<thời điểm>.csv
  results/detection/detection-<thời điểm>.md

Ví dụ:
  python scripts/detection_time.py
  python scripts/detection_time.py --last 5
  python scripts/detection_time.py --since 2026-11-20T08:00:00 --scenario cpu
"""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.common import (  # noqa: E402
    ALERT_LOG,
    EVENT_LOG,
    RESULTS_DIR,
    fmt,
    iso,
    labels_match,
    md_table,
    parse_iso,
    read_jsonl,
    stamp,
)

COLUMNS = [
    "fault_id", "scenario", "target", "params", "injected_at", "clock_ref",
    "detected", "first_alert", "detection_s", "prom_fired_s", "per_alert_s",
    "recovered_at", "resolved_s", "other_alerts",
]


def ref_times(ev: dict) -> tuple:
    """Trả về (mốc gây lỗi, mốc khôi phục, nguồn đồng hồ) theo đồng hồ của receiver nếu có."""
    if ev.get("injected_ts_receiver") is not None:
        return ev["injected_ts_receiver"], ev.get("recovered_ts_receiver"), "receiver"
    return ev["injected_ts"], ev.get("recovered_ts"), "local"


def analyse(events: list, alerts: list, window: float, tolerance: float) -> list:
    events = sorted(events, key=lambda e: e["injected_ts"])
    firing = [a for a in alerts if a.get("status") == "firing"]
    resolved = [a for a in alerts if a.get("status") == "resolved"]
    rows = []
    for idx, ev in enumerate(events):
        t0, t_rec, clock = ref_times(ev)
        # cửa sổ tìm kiếm: từ lúc gây lỗi tới lúc kịch bản kế tiếp bắt đầu (hoặc t0 + window)
        t_end = t0 + window
        if idx + 1 < len(events):
            t_end = min(t_end, ref_times(events[idx + 1])[0])
        expected = ev.get("expected_alerts", [])
        match = ev.get("match_labels", {})

        in_window = [a for a in firing if t0 - tolerance <= a.get("received_ts", 0) <= t_end]
        hits = [a for a in in_window if a.get("alertname") in expected and labels_match(a.get("labels", {}), match)]
        hits.sort(key=lambda a: a["received_ts"])

        per_alert = {}
        for a in hits:
            per_alert.setdefault(a["alertname"], a)
        first = hits[0] if hits else None

        prom_fired = None
        resolved_s = None
        if first:
            fired_at = parse_iso(first.get("startsAt"))
            if fired_at is not None:
                prom_fired = fired_at - t0
            if t_rec is not None:
                for r in sorted(resolved, key=lambda r: r.get("received_ts", 0)):
                    if r.get("fingerprint") == first.get("fingerprint") and r.get("received_ts", 0) >= t_rec:
                        resolved_s = r["received_ts"] - t_rec
                        break

        hit_ids = {id(a) for a in hits}
        others = sorted({a["alertname"] for a in in_window if id(a) not in hit_ids and a.get("alertname") not in expected})

        rows.append({
            "fault_id": ev["fault_id"],
            "scenario": ev["scenario"],
            "target": ev.get("target", ""),
            "params": ";".join(f"{k}={v}" for k, v in (ev.get("params") or {}).items()),
            "injected_at": ev.get("injected_at", iso(ev["injected_ts"])),
            "clock_ref": clock,
            "detected": "yes" if first else "no",
            "first_alert": first["alertname"] if first else "",
            "detection_s": round(first["received_ts"] - t0, 1) if first else None,
            "prom_fired_s": round(prom_fired, 1) if prom_fired is not None else None,
            "per_alert_s": ";".join(f"{k}={v['received_ts'] - t0:.1f}" for k, v in per_alert.items()),
            "recovered_at": ev.get("recovered_at", ""),
            "resolved_s": round(resolved_s, 1) if resolved_s is not None else None,
            "other_alerts": ";".join(others),
        })
    return rows


def summary(rows: list) -> list:
    out = []
    for sc in sorted({r["scenario"] for r in rows}):
        rs = [r for r in rows if r["scenario"] == sc]
        d = [r["detection_s"] for r in rs if r["detection_s"] is not None]
        out.append([
            sc, len(rs), len(d), f"{100 * len(d) / len(rs):.0f}%",
            fmt(min(d), 1) if d else "", fmt(statistics.mean(d), 1) if d else "",
            fmt(statistics.median(d), 1) if d else "", fmt(max(d), 1) if d else "",
            fmt(statistics.stdev(d), 1) if len(d) > 1 else "",
        ])
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--events", type=Path, default=EVENT_LOG)
    ap.add_argument("--alerts", type=Path, default=ALERT_LOG)
    ap.add_argument("--out-dir", type=Path, default=RESULTS_DIR / "detection")
    ap.add_argument("--since", help="chỉ xét sự kiện từ thời điểm này (ISO-8601, giờ UTC nếu không ghi múi giờ)")
    ap.add_argument("--scenario", action="append", help="lọc theo kịch bản (lặp lại được)")
    ap.add_argument("--last", type=int, default=0, help="chỉ xét N sự kiện gần nhất")
    ap.add_argument("--window", type=float, default=900, help="cửa sổ tối đa chờ cảnh báo sau khi gây lỗi (giây)")
    ap.add_argument("--tolerance", type=float, default=2, help="chấp nhận cảnh báo đến sớm hơn mốc gây lỗi tối đa N giây")
    a = ap.parse_args()

    events = read_jsonl(a.events)
    alerts = read_jsonl(a.alerts)
    if not events:
        sys.exit(f"Chưa có sự kiện nào trong {a.events}. Chạy scripts/fault.py trước.")
    if a.since:
        since = parse_iso(a.since)
        events = [e for e in events if e["injected_ts"] >= since]
    if a.scenario:
        events = [e for e in events if e["scenario"] in a.scenario]
    events.sort(key=lambda e: e["injected_ts"])
    if a.last:
        events = events[-a.last:]
    if not events:
        sys.exit("Không còn sự kiện nào sau khi lọc.")

    # phân tích trên toàn bộ sự kiện (để cửa sổ dừng đúng ở sự kiện kế tiếp), rồi mới lọc
    all_rows = analyse(read_jsonl(a.events), alerts, a.window, a.tolerance)
    keep = {e["fault_id"] for e in events}
    rows = [r for r in all_rows if r["fault_id"] in keep]

    a.out_dir.mkdir(parents=True, exist_ok=True)
    base = a.out_dir / f"detection-{stamp()}"
    with open(base.with_suffix(".csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)

    sum_rows = summary(rows)
    md = [
        "# Kết quả đo thời gian phát hiện",
        "",
        f"- Tạo lúc: {iso(__import__('time').time())}",
        f"- Số sự kiện: {len(rows)} — nguồn: `{a.events.name}`, `{a.alerts.name}`",
        "- `detection_s` = thời điểm webhook nhận cảnh báo **firing** đầu tiên khớp kỳ vọng − thời điểm gây lỗi.",
        "- `prom_fired_s` = `startsAt` mà Prometheus gắn cho cảnh báo − thời điểm gây lỗi (tham khảo).",
        "- `resolved_s` = thời điểm nhận **resolved** − thời điểm khôi phục.",
        "- `other_alerts` = cảnh báo KHÁC xuất hiện trong cùng cửa sổ (ứng viên báo giả / hệ quả phụ, cần xem xét).",
        "- `clock_ref=receiver`: mốc gây lỗi đã quy đổi sang đồng hồ của webhook-receiver.",
        "",
        "## Tổng hợp theo kịch bản",
        "",
        md_table(["Kịch bản", "Số lần", "Phát hiện", "Tỉ lệ", "Min (s)", "TB (s)", "Trung vị (s)", "Max (s)", "Độ lệch chuẩn (s)"], sum_rows),
        "",
        "## Chi tiết",
        "",
        md_table(
            ["fault_id", "Kịch bản", "Đích", "Gây lỗi (UTC)", "Cảnh báo đầu", "detection_s", "prom_fired_s", "Từng cảnh báo", "resolved_s", "Cảnh báo khác"],
            [[r["fault_id"], r["scenario"], r["target"], r["injected_at"], r["first_alert"] or "**KHÔNG PHÁT HIỆN**",
              fmt(r["detection_s"], 1), fmt(r["prom_fired_s"], 1), r["per_alert_s"], fmt(r["resolved_s"], 1), r["other_alerts"]]
             for r in rows],
        ),
        "",
    ]
    base.with_suffix(".md").write_text("\n".join(md), encoding="utf-8")

    print("Tổng hợp theo kịch bản:\n")
    print(md_table(["Kịch bản", "Số lần", "Phát hiện", "Tỉ lệ", "Min (s)", "TB (s)", "Trung vị (s)", "Max (s)", "Độ lệch chuẩn (s)"], sum_rows))
    print(f"\nĐã ghi: {base.with_suffix('.csv')}\n        {base.with_suffix('.md')}")


if __name__ == "__main__":
    main()
