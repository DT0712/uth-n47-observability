"""Tính THỜI GIAN PHÁT HIỆN cho các kịch bản lỗi.

  phát hiện đầu tiên = thời điểm alert-recorder nhận cảnh báo ĐẦU TIÊN thuộc lỗi đó − thời điểm gây lỗi
  cảnh báo gốc       = thời điểm nhận cảnh báo chỉ đúng nguyên nhân (root_alert) − thời điểm gây lỗi

Đầu vào:
  data/events/faults.jsonl   (do tools/fault.py ghi)
  data/alerts/alerts.jsonl   (do alert-recorder ghi)
Đầu ra:
  results/detection/detection-<thời điểm>.csv   mỗi lần đo một dòng
  results/detection/detection-<thời điểm>.md    tổng hợp + chi tiết

Lần đo KHÔNG HỢP LỆ bị loại khỏi thống kê và liệt kê riêng kèm lý do: bị ngắt giữa chừng, script chết, VM/Windows ngủ.
Lần hợp lệ nhưng không có cảnh báo nào mới tính là "không phát hiện".

Ví dụ:
  python tools/detection_time.py
  python tools/detection_time.py --suite gd3-dot1
  python tools/detection_time.py --since 2026-11-20T08:00:00 --scenario cpu
"""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.common import (  # noqa: E402
    ALERT_LOG,
    EVENT_LOG,
    RESULTS_DIR,
    fmt,
    iso,
    labels_match,
    load_events,
    md_table,
    parse_iso,
    read_jsonl,
    stamp,
)

COLUMNS = [
    "fault_id", "suite", "round", "case", "scenario", "target", "params", "injected_at", "valid", "invalid_reason",
    "detected", "first_alert", "first_s", "root_alert", "root_s", "root_prom_fired_s", "extra_before_root",
    "extra_after_root", "recover_noise", "recovered_at", "root_resolved_s", "unrelated_alerts", "vm_clock_offset_s", "eval_lag_s",
    "root_notify_delay_s", "host_free_mb",
]


EVAL_LAG_LIMIT_S = 1.0     # giống tools/fault.py
NOTIFY_DELAY_LIMIT_S = 6.0  # group_wait 5 s + 1 s: dùng cho sự kiện cũ chưa ghi eval_lag_s


def invalid_reason(ev: dict, notify_delay: float | None = None) -> str:
    """Vì sao lần đo này không dùng để thống kê được; chuỗi rỗng nếu hợp lệ."""
    lag = ev.get("eval_lag_s")
    if lag is not None and abs(lag) > EVAL_LAG_LIMIT_S:
        return f"Prometheus đánh giá luật trễ {lag:.1f}s (SC-04)"
    if lag is None and notify_delay is not None and notify_delay > NOTIFY_DELAY_LIMIT_S:
        return f"cảnh báo gốc tới sau startsAt {notify_delay:.1f}s, Prometheus đánh giá luật trễ (SC-04)"
    status = ev.get("status")
    if status is None:   # sự kiện ghi trước khi có trường status
        reason = ev.get("stop_reason")
        if reason is None:
            return "script chết trước khi gỡ lỗi"
        status = "completed" if reason.startswith(("hết thời gian giữ", "đã nhận cảnh báo gốc")) else "aborted"
    if status == "running":
        return "script chết trước khi gỡ lỗi"
    if status == "aborted":
        return ev.get("stop_reason") or "bị ngắt"
    if ev.get("data_gap"):
        return "mất dữ liệu giám sát trong lúc đo (VM/Windows ngủ?)"
    return ""


def ref_times(ev: dict) -> tuple:
    """(mốc gây lỗi, mốc gỡ lỗi) theo đồng hồ monitor."""
    if ev.get("injected_ts_receiver") is not None:
        return ev["injected_ts_receiver"], ev.get("recovered_ts_receiver")
    return ev["injected_ts"], ev.get("recovered_ts")


def distinct(alerts: list) -> list:
    """Giữ lần nhận đầu tiên của mỗi cảnh báo (Alertmanager có thể gửi lại cả nhóm)."""
    seen, out = set(), []
    for a in sorted(alerts, key=lambda a: a.get("received_ts", 0)):
        key = (a.get("alertname"), a.get("fingerprint"))
        if key not in seen:
            seen.add(key)
            out.append(a)
    return out


def names(alerts: list, t0: float) -> str:
    def label(a):
        inst = a.get("labels", {}).get("instance", "")
        return f"{a['alertname']}[{inst}]={a['received_ts'] - t0:.1f}"
    return ";".join(label(a) for a in alerts)


def analyse(events: list, alerts: list, window: float, tolerance: float) -> list:
    events = sorted(events, key=lambda e: ref_times(e)[0])
    alerts = [a for a in alerts if a.get("alertname") != "LabTestAlert"]
    firing = [a for a in alerts if a.get("status") == "firing"]
    resolved = sorted((a for a in alerts if a.get("status") == "resolved"), key=lambda a: a.get("received_ts", 0))
    rows = []
    for idx, ev in enumerate(events):
        t0, t_rec = ref_times(ev)
        # từ lúc gây lỗi tới khi sự kiện kế tiếp (kể cả sự kiện không hợp lệ) bắt đầu, tối đa `window`
        t_end = t0 + window
        if idx + 1 < len(events):
            t_end = min(t_end, ref_times(events[idx + 1])[0] - tolerance)
        expected = ev.get("expected_alerts", [])
        root_name = ev.get("root_alert") or (expected[0] if expected else "")
        match = ev.get("match_labels", {})

        in_window = distinct([a for a in firing if t0 - tolerance <= a.get("received_ts", 0) <= t_end])
        mine = [a for a in in_window if a.get("alertname") in expected and labels_match(a.get("labels", {}), match)]
        unrelated = [a for a in in_window if a not in mine]
        # Cảnh báo tới SAU khi đã gỡ lỗi không phải là phát hiện: đó là nhiễu lúc khôi phục.
        during = [a for a in mine if t_rec is None or a["received_ts"] <= t_rec]
        noise = [a for a in mine if a not in during]
        root = next((a for a in during if a["alertname"] == root_name), None)
        first = during[0] if during else None
        before = [a for a in during if root and a["alertname"] != root_name and a["received_ts"] <= root["received_ts"]]
        after = [a for a in during if root and a["alertname"] != root_name and a["received_ts"] > root["received_ts"]]

        fired_at = parse_iso(root.get("startsAt")) if root else None
        resolved_s = None
        if root and t_rec is not None:
            for r in resolved:
                if r.get("fingerprint") == root.get("fingerprint") and r["received_ts"] >= t_rec:
                    resolved_s = r["received_ts"] - t_rec
                    break
        delay = round(root["received_ts"] - fired_at, 2) if root and fired_at is not None else None
        reason = invalid_reason(ev, delay)
        rows.append({
            "fault_id": ev["fault_id"], "suite": ev.get("suite") or "", "round": ev.get("round") or "",
            "case": ev.get("case") or f"{ev['scenario']} {ev.get('target', '')}",
            "scenario": ev["scenario"], "target": ev.get("target", ""),
            "params": ";".join(f"{k}={v}" for k, v in (ev.get("params") or {}).items()),
            "injected_at": ev.get("injected_at", iso(t0)),
            "valid": "no" if reason else "yes", "invalid_reason": reason,
            "detected": "yes" if first else "no",
            "first_alert": first["alertname"] if first else "",
            "first_s": round(first["received_ts"] - t0, 1) if first else None,
            "root_alert": root_name, "root_s": round(root["received_ts"] - t0, 1) if root else None,
            "root_prom_fired_s": round(fired_at - t0, 1) if fired_at is not None else None,
            "extra_before_root": names(before, t0), "extra_after_root": names(after, t0), "recover_noise": names(noise, t0),
            "recovered_at": ev.get("recovered_at") or "",
            "root_resolved_s": round(resolved_s, 1) if resolved_s is not None else None,
            "unrelated_alerts": names(unrelated, t0),
            "vm_clock_offset_s": ev.get("vm_clock_offset_s"), "eval_lag_s": ev.get("eval_lag_s"),
            "root_notify_delay_s": delay, "host_free_mb": ev.get("host_free_mb"),
        })
    return rows


def stats(values: list) -> list:
    if not values:
        return [""] * 5
    return [fmt(min(values), 1), fmt(statistics.mean(values), 1), fmt(statistics.median(values), 1), fmt(max(values), 1),
            fmt(statistics.stdev(values), 1) if len(values) > 1 else ""]


def n_items(s: str) -> int:
    return len([x for x in s.split(";") if x])


SUMMARY_HEAD = ["Trường hợp", "Lần hợp lệ", "Phát hiện", "Đúng gốc", "Min", "TB", "Trung vị", "Max", "Độ lệch chuẩn"]


def summary(rows: list, key: str) -> list:
    out = []
    for case in sorted({r["case"] for r in rows}):
        rs = [r for r in rows if r["case"] == case]
        out.append([case, len(rs), sum(r["first_s"] is not None for r in rs), sum(r["root_s"] is not None for r in rs),
                    *stats([r[key] for r in rs if r[key] is not None])])
    return out


def noise_summary(rows: list) -> list:
    out = []
    for case in sorted({r["case"] for r in rows}):
        rs = [r for r in rows if r["case"] == case]
        out.append([case, len(rs),
                    sum(bool(r["extra_before_root"]) for r in rs), sum(bool(r["extra_after_root"]) for r in rs),
                    sum(n_items(r["extra_before_root"]) + n_items(r["extra_after_root"]) for r in rs),
                    sum(n_items(r["recover_noise"]) for r in rs), sum(n_items(r["unrelated_alerts"]) for r in rs)])
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--events", type=Path, default=EVENT_LOG)
    ap.add_argument("--alerts", type=Path, default=ALERT_LOG)
    ap.add_argument("--out-dir", type=Path, default=RESULTS_DIR / "detection")
    ap.add_argument("--suite", help="chỉ xét một đợt đo (fault.py suite --id ...)")
    ap.add_argument("--since", help="chỉ xét sự kiện từ thời điểm này (ISO-8601, giờ UTC nếu không ghi múi giờ)")
    ap.add_argument("--scenario", action="append", help="lọc theo kịch bản (lặp lại được)")
    ap.add_argument("--last", type=int, default=0, help="chỉ xét N sự kiện gần nhất")
    ap.add_argument("--window", type=float, default=900, help="cửa sổ tối đa chờ cảnh báo sau khi gây lỗi (giây)")
    ap.add_argument("--tolerance", type=float, default=2, help="chấp nhận cảnh báo đến sớm hơn mốc gây lỗi tối đa N giây")
    a = ap.parse_args()

    all_events = load_events(a.events)
    if not all_events:
        sys.exit(f"Chưa có sự kiện nào trong {a.events}. Chạy tools/fault.py trước.")
    events = sorted(all_events, key=lambda e: ref_times(e)[0])
    if a.suite:
        events = [e for e in events if e.get("suite") == a.suite]
    if a.since:
        since = parse_iso(a.since)
        events = [e for e in events if ref_times(e)[0] >= since]
    if a.scenario:
        events = [e for e in events if e["scenario"] in a.scenario]
    if a.last:
        events = events[-a.last:]
    if not events:
        sys.exit("Không còn sự kiện nào sau khi lọc.")

    # phân tích trên toàn bộ sự kiện (để cửa sổ dừng đúng ở sự kiện kế tiếp), rồi mới lọc
    keep = {e["fault_id"] for e in events}
    rows = [r for r in analyse(all_events, read_jsonl(a.alerts), a.window, a.tolerance) if r["fault_id"] in keep]
    valid = [r for r in rows if r["valid"] == "yes"]
    invalid = [r for r in rows if r["valid"] == "no"]

    a.out_dir.mkdir(parents=True, exist_ok=True)
    base = a.out_dir / f"detection-{stamp()}"
    with open(base.with_suffix(".csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)

    noise_head = ["Trường hợp", "Lần hợp lệ", "Lần có cảnh báo hệ quả TRƯỚC gốc", "Lần có SAU gốc",
                  "Tổng thông báo hệ quả", "Thông báo nhiễu lúc khôi phục", "Cảnh báo ngoài kịch bản"]
    md = [
        "# Kết quả đo thời gian phát hiện", "",
        f"- Tạo lúc: {iso(time.time())}" + (f" — đợt đo `{a.suite}`" if a.suite else ""),
        f"- Số lần: {len(rows)}, hợp lệ {len(valid)}, loại {len(invalid)}. Đơn vị: giây.",
        "- Mốc 0 là giờ VM ngay sau khi thao tác gây lỗi hoàn tất, đã hiệu chỉnh theo đồng hồ monitor.", "",
        "## Phát hiện đầu tiên (bất kỳ cảnh báo nào của lỗi)", "", md_table(SUMMARY_HEAD, summary(valid, "first_s")), "",
        "## Cảnh báo gốc (chỉ đúng nguyên nhân)", "", md_table(SUMMARY_HEAD, summary(valid, "root_s")), "",
        "## Từ lúc gỡ lỗi tới khi nhận resolved của cảnh báo gốc", "", md_table(SUMMARY_HEAD, summary(valid, "root_resolved_s")), "",
        "## Thông báo thừa", "", md_table(noise_head, noise_summary(valid)), "",
        "## Lần bị loại", "",
        md_table(["fault_id", "Trường hợp", "Lý do"], [[r["fault_id"], r["case"], r["invalid_reason"]] for r in invalid])
        if invalid else "Không có.", "",
        "## Chi tiết các lần hợp lệ", "",
        md_table(["fault_id", "Trường hợp", "Gây lỗi (UTC)", "Đầu tiên", "first_s", "Gốc", "root_s", "Hệ quả trước gốc", "Hệ quả sau gốc",
                  "Nhiễu khôi phục", "resolved_s"],
                 [[r["fault_id"], r["case"], r["injected_at"][:19], r["first_alert"] or "**KHÔNG PHÁT HIỆN**", fmt(r["first_s"], 1),
                   r["root_alert"], fmt(r["root_s"], 1), r["extra_before_root"], r["extra_after_root"], r["recover_noise"],
                   fmt(r["root_resolved_s"], 1)] for r in valid]), "",
    ]
    base.with_suffix(".md").write_text("\n".join(md), encoding="utf-8", newline="\n")

    print(f"{len(rows)} lần: hợp lệ {len(valid)}, loại {len(invalid)}\n\nPhát hiện đầu tiên (giây):")
    print(md_table(SUMMARY_HEAD, summary(valid, "first_s")))
    print("\nCảnh báo gốc (giây):")
    print(md_table(SUMMARY_HEAD, summary(valid, "root_s")))
    print("\nThông báo thừa:")
    print(md_table(noise_head, noise_summary(valid)))
    for r in invalid:
        print(f"Loại: {r['fault_id']} — {r['invalid_reason']}")
    print(f"\nĐã ghi: {base.with_suffix('.csv')}\n        {base.with_suffix('.md')}")


if __name__ == "__main__":
    main()
