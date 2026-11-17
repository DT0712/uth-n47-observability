"""Đo BASELINE: thống kê các chỉ số khi hệ thống chạy bình thường để làm căn cứ chọn ngưỡng.

Hai cách dùng:
  # 1) Chạy trực tiếp N phút rồi thống kê (đảm bảo KHÔNG có kịch bản lỗi nào trong lúc đo)
  python scripts/baseline.py --minutes 60 --wait

  # 2) Thống kê dữ liệu đã có trong Prometheus cho N phút vừa qua (hoặc kết thúc tại --end)
  python scripts/baseline.py --minutes 120
  python scripts/baseline.py --minutes 60 --end 2026-11-20T10:00:00+07:00

Đầu ra trong results/baseline/<thời điểm>/:
  baseline.csv        thống kê theo từng series (n, min, mean, std, p50, p90, p95, p99, max)
  baseline.md         tóm tắt + ngưỡng hiện hành + các giá trị ỨNG VIÊN để nhóm thảo luận
  samples.csv         (với --raw) toàn bộ mẫu thô

Các giá trị "ứng viên" chỉ là điểm khởi đầu (p99 + 3σ, max × 1.2...). Ngưỡng cuối cùng phải do
nhóm quyết định, cân nhắc thêm dung lượng/SLO, và ghi vào prometheus/rules/thresholds.yml.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.common import (  # noqa: E402
    RESULTS_DIR,
    describe,
    fmt,
    iso,
    md_table,
    parse_iso,
    prom_query,
    prom_query_range,
    stamp,
)

# key, promql, đơn vị, tên ngưỡng tương ứng (lab:threshold:<tên>), chiều cảnh báo, giới hạn trên hợp lý
METRICS = [
    ("host_cpu_usage_percent", "lab:host_cpu_usage:percent", "%", "host_cpu_usage_percent", "above", 100),
    ("host_memory_usage_percent", "lab:host_memory_usage:percent", "%", "host_memory_usage_percent", "above", 100),
    ("filesystem_usage_percent", "lab:filesystem_usage:percent", "%", "filesystem_usage_percent", "above", 100),
    ("endpoint_probe_duration_seconds", 'probe_duration_seconds{job="blackbox-http"}', "s", "endpoint_probe_duration_seconds", "above", None),
    ("service_latency_p95_seconds", "lab:service_latency_p95:seconds", "s", "service_latency_p95_seconds", "above", None),
    ("service_error_ratio", "lab:service_error_ratio:ratio", "ratio", "service_error_ratio", "above", 1),
    ("service_request_rate_rps", "lab:service_request_rate:rps", "rps", "service_min_request_rate_rps", "below", None),
    # chỉ để tham khảo, chưa có cảnh báo:
    ("endpoint_probe_success", 'probe_success', "0/1", None, "info", 1),
    ("host_load1_per_core", 'node_load1{job="node"} / on(instance) count by (instance) (node_cpu_seconds_total{job="node",mode="idle"})', "", None, "info", None),
    ("host_network_rx_Bps", "lab:host_network_receive:bytes_per_second", "B/s", None, "info", None),
    ("host_network_tx_Bps", "lab:host_network_transmit:bytes_per_second", "B/s", None, "info", None),
    ("container_cpu_percent", "lab:container_cpu_usage:percent", "%", None, "info", None),
]

LABEL_KEYS = ("instance", "service", "mountpoint", "name", "job")


def series_label(metric: dict) -> str:
    parts = [f"{k}={metric[k]}" for k in LABEL_KEYS if k in metric]
    return ",".join(parts) or "(tổng)"


def candidates(st: dict, direction: str, cap) -> dict:
    if not st.get("n"):
        return {}
    if direction == "above":
        c = {
            "p99+3sd": st["p99"] + 3 * st["std"],
            "max*1.2": st["max"] * 1.2,
        }
    elif direction == "below":
        c = {"p01*0.5": st.get("p01", st["min"]) * 0.5, "min*0.5": st["min"] * 0.5}
    else:
        return {}
    if cap is not None:
        c = {k: min(v, cap) for k, v in c.items()}
    return c


def active_faults() -> list:
    try:
        return prom_query("lab_fault_active == 1")
    except Exception:
        return []


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--minutes", type=float, required=True, help="độ dài cửa sổ baseline (phút)")
    ap.add_argument("--wait", action="store_true", help="chờ N phút từ bây giờ rồi mới thống kê")
    ap.add_argument("--end", help="thời điểm kết thúc cửa sổ (ISO-8601), mặc định là bây giờ")
    ap.add_argument("--step", type=float, default=15, help="bước lấy mẫu (giây), mặc định 15 = scrape_interval")
    ap.add_argument("--raw", action="store_true", help="ghi thêm toàn bộ mẫu thô ra samples.csv")
    ap.add_argument("--label", default="", help="nhãn mô tả lần đo (vd. 'tai-thuong-5rps')")
    ap.add_argument("--out-dir", type=Path, default=RESULTS_DIR / "baseline")
    a = ap.parse_args()

    if a.wait:
        if active_faults():
            print("! CẢNH BÁO: đang có lỗi giả lập bật (lab_fault_active == 1). Gỡ bằng: python scripts/fault.py recover")
        start = time.time()
        end = start + a.minutes * 60
        print(f"Đo baseline từ {iso(start)} tới {iso(end)} — KHÔNG chạy kịch bản lỗi trong thời gian này.")
        try:
            while time.time() < end:
                left = int(end - time.time())
                print(f"\r  còn {left // 60:3d} phút {left % 60:02d} giây", end="", flush=True)
                time.sleep(min(10, max(0.1, end - time.time())))
        except KeyboardInterrupt:
            print("\n  dừng sớm — thống kê phần đã đo.")
            end = time.time()
        print()
    else:
        end = parse_iso(a.end) if a.end else time.time()
        if end is None:
            sys.exit("--end không hợp lệ")
        start = end - a.minutes * 60

    out = a.out_dir / (stamp() + (f"-{a.label}" if a.label else ""))
    out.mkdir(parents=True, exist_ok=True)

    thresholds = {}
    try:
        for s in prom_query('{__name__=~"lab:threshold:.*"}'):
            name = s["metric"]["__name__"].split(":", 2)[2]
            thresholds[name] = (float(s["value"][1]), s["metric"].get("threshold_status", ""))
    except Exception as e:
        sys.exit(f"Không truy vấn được Prometheus: {e}\nKiểm tra lab đang chạy (docker compose ps).")

    # Cảnh báo nếu trong cửa sổ có lỗi giả lập -> baseline bị nhiễm
    fault_samples = 0
    try:
        for s in prom_query_range("max(lab_fault_active)", start, end, a.step):
            fault_samples += sum(1 for _, v in s["values"] if float(v) > 0)
    except Exception:
        pass

    per_series_rows = []
    summary_rows = []
    raw_rows = []
    for key, expr, unit, thr_name, direction, cap in METRICS:
        series = prom_query_range(expr, start, end, a.step)
        all_vals = []
        for s in series:
            vals = [float(v) for _, v in s["values"]]
            all_vals.extend(vals)
            st = describe(vals)
            per_series_rows.append({"metric": key, "series": series_label(s["metric"]), "unit": unit,
                                    **{k: st.get(k) for k in ("n", "min", "mean", "std", "p50", "p90", "p95", "p99", "max")}})
            if a.raw:
                lab = series_label(s["metric"])
                raw_rows.extend((key, lab, iso(float(t)), v) for t, v in s["values"])
        st = describe(all_vals)
        if st.get("n"):
            st["p01"] = sorted(all_vals)[max(0, int(len(all_vals) * 0.01) - 1)]
        cur = thresholds.get(thr_name) if thr_name else None
        cand = candidates(st, direction, cap)
        summary_rows.append([
            key, unit, len(series), st.get("n", 0),
            fmt(st.get("min")), fmt(st.get("mean")), fmt(st.get("p95")), fmt(st.get("p99")), fmt(st.get("max")), fmt(st.get("std")),
            f"{cur[0]:g} ({cur[1]})" if cur else ("—" if not thr_name else "THIẾU"),
            "; ".join(f"{k}={fmt(v)}" for k, v in cand.items()),
        ])
        print(f"  {key:<34} series={len(series):<3} n={st.get('n', 0):<6} p99={fmt(st.get('p99'))}")

    cols = ["metric", "series", "unit", "n", "min", "mean", "std", "p50", "p90", "p95", "p99", "max"]
    with open(out / "baseline.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in per_series_rows:
            w.writerow({k: (fmt(v, 6) if isinstance(v, float) else v) for k, v in r.items()})
    if a.raw:
        with open(out / "samples.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["metric", "series", "time_utc", "value"])
            w.writerows(raw_rows)

    md = [
        "# Kết quả đo baseline",
        "",
        f"- Cửa sổ: **{iso(start)} → {iso(end)}** ({(end - start) / 60:.1f} phút), bước {a.step:g}s",
        f"- Nhãn: {a.label or '(không)'}",
        f"- Mẫu có lỗi giả lập đang bật trong cửa sổ: **{fault_samples}**"
        + ("  ⚠️ baseline bị nhiễm, nên đo lại" if fault_samples else " (sạch)"),
        "",
        "## Tổng hợp (gộp mọi series của cùng chỉ số)",
        "",
        md_table(["Chỉ số", "Đơn vị", "Series", "Mẫu", "Min", "TB", "p95", "p99", "Max", "σ", "Ngưỡng hiện hành", "Ứng viên ngưỡng"], summary_rows),
        "",
        "## Cách đọc & chọn ngưỡng",
        "",
        "- **Ứng viên** chỉ là gợi ý cơ học: `p99+3sd` (ít báo giả nếu phân phối ổn định) và `max*1.2` (đệm 20% trên đỉnh quan sát).",
        "  Với chỉ số loại *below* (lưu lượng tối thiểu) ứng viên là một nửa giá trị thấp.",
        "- Ngưỡng nên nằm **trên** dải dao động bình thường nhưng **dưới** mức gây ảnh hưởng thật (SLO/dung lượng).",
        "  Nếu ứng viên vượt mức ảnh hưởng thật, vấn đề là năng lực hệ thống chứ không phải ngưỡng.",
        "- Đĩa: nên dựa vào dung lượng còn lại tuyệt đối/tốc độ đầy hơn là phân phối % (giá trị % gần như hằng số).",
        "- Khi đã chốt: sửa `prometheus/rules/thresholds.yml` (đổi `threshold_status` thành `baselined`, ghi `basis`),",
        "  chạy `python scripts/reload.py`, lưu file này kèm báo cáo.",
        "",
        "## Chi tiết theo series",
        "",
        md_table(["Chỉ số", "Series", "n", "min", "mean", "p95", "p99", "max"],
                 [[r["metric"], r["series"], r["n"], fmt(r["min"]), fmt(r["mean"]), fmt(r["p95"]), fmt(r["p99"]), fmt(r["max"])]
                  for r in per_series_rows]),
        "",
    ]
    (out / "baseline.md").write_text("\n".join(md), encoding="utf-8")
    (out / "meta.json").write_text(json.dumps({"start": start, "end": end, "step": a.step, "label": a.label,
                                                "fault_samples": fault_samples, "thresholds": thresholds},
                                               ensure_ascii=False, indent=2), encoding="utf-8")
    if fault_samples:
        print(f"\n! Có {fault_samples} mẫu trong lúc lỗi giả lập đang bật — baseline không sạch.")
    print(f"\nĐã ghi kết quả vào {out}")


if __name__ == "__main__":
    main()
