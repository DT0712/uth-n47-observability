"""Đo BASELINE: thống kê các chỉ số khi hệ thống chạy bình thường để làm căn cứ chọn ngưỡng.

  # 1) Đo trực tiếp N phút rồi thống kê (KHÔNG chạy kịch bản lỗi trong lúc đo)
  python tools/baseline.py --minutes 1440 --wait --label baseline-24h

  # 2) Xem tiến độ, giờ dự kiến xong và tình trạng lab của lần đo đang chạy (mở cửa sổ khác)
  python tools/baseline.py --status

  # 3) Thống kê lại cửa sổ của lần đo gần nhất (vd. tiến trình --wait bị tắt giữa chừng hoặc sau khi xong)
  python tools/baseline.py --from-state

  # 4) Thống kê dữ liệu đã có trong Prometheus cho N phút vừa qua (hoặc kết thúc tại --end)
  python tools/baseline.py --minutes 120
  python tools/baseline.py --minutes 60 --end 2026-11-20T10:00:00+07:00

--wait ghi trạng thái vào data/baseline/state.json và mỗi 10 phút một dòng sức khỏe lab vào data/baseline/health.jsonl.
Dữ liệu nằm trong Prometheus (retention 15 ngày), nên nếu tiến trình chết vẫn thống kê lại được bằng --from-state.

Đầu ra trong results/baseline/<thời điểm>[-nhãn]/:
  baseline.md   chất lượng dữ liệu, cảnh báo đã bắn, bảng theo từng máy ảo và từng chỉ số, ngưỡng gợi ý
  baseline.csv  thống kê theo từng series (n, min, mean, std, p50, p90, p95, p99, max)
  meta.json     cửa sổ, ngưỡng hiện hành, chất lượng dữ liệu
  samples.csv   (với --raw) toàn bộ mẫu thô

Ngưỡng gợi ý chỉ là điểm khởi đầu theo quy tắc ghi trong baseline.md. Ngưỡng cuối cùng do nhóm quyết định và ghi vào
monitor/prometheus/rules/thresholds.yml (ADR-0004).
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.common import (  # noqa: E402
    DATA_DIR,
    RESULTS_DIR,
    append_jsonl,
    describe,
    fmt,
    iso,
    md_table,
    parse_iso,
    prom_query,
    prom_query_range,
    rule_eval_lag,
    stamp,
)

STATE = DATA_DIR / "baseline" / "state.json"
HEALTH = DATA_DIR / "baseline" / "health.jsonl"
HEALTH_EVERY_S = 600
SCRAPE_S = 15

# key, promql, đơn vị, tên ngưỡng (lab:threshold:<tên>), loại, giới hạn trên hợp lý
#   capacity: ngưỡng theo sức chứa (CPU, RAM, đĩa, kết nối) — baseline chỉ để kiểm tra ngưỡng không báo giả
#   slo:      ngưỡng theo chất lượng dịch vụ — baseline cho mức bình thường, gợi ý = đệm trên mức đó
#   traffic:  ngưỡng dưới (lưu lượng tối thiểu)
#   info:     chỉ tham khảo, chưa có cảnh báo
METRICS = [
    ("host_cpu_usage_percent", "lab:host_cpu_usage:percent", "%", "host_cpu_usage_percent", "capacity", 100),
    ("host_memory_usage_percent", "lab:host_memory_usage:percent", "%", "host_memory_usage_percent", "capacity", 100),
    ("filesystem_usage_percent", "lab:filesystem_usage:percent", "%", "filesystem_usage_percent", "capacity", 100),
    ("postgres_connections_usage_percent", "lab:postgres_connections_usage:percent", "%", "postgres_connections_usage_percent", "capacity", 100),
    ("endpoint_probe_duration_seconds", 'probe_duration_seconds{job="blackbox-http"}', "s", "endpoint_probe_duration_seconds", "slo", None),
    ("service_latency_p95_seconds", "lab:service_latency_p95:seconds", "s", "service_latency_p95_seconds", "slo", None),
    ("service_error_ratio", "lab:service_error_ratio:ratio", "ratio", "service_error_ratio", "slo", 1),
    ("service_request_rate_rps", "lab:service_request_rate:rps", "rps", "service_min_request_rate_rps", "traffic", None),
    ("endpoint_probe_success", 'probe_success', "0/1", None, "info", 1),
    ("host_load1_per_core", 'node_load1{job="node"} / on(instance) count by (instance) (node_cpu_seconds_total{job="node",mode="idle"})', "", None, "info", None),
    ("host_network_rx_Bps", "lab:host_network_receive:bytes_per_second", "B/s", None, "info", None),
    ("host_network_tx_Bps", "lab:host_network_transmit:bytes_per_second", "B/s", None, "info", None),
    ("nginx_active_connections", 'nginx_connections_active{job="nginx"}', "", None, "info", None),
]

LABEL_KEYS = ("instance", "service", "mountpoint", "name", "job")
VMS = ("monitor", "web", "db")


def series_label(metric: dict) -> str:
    parts = [f"{k}={metric[k]}" for k in LABEL_KEYS if k in metric]
    return ",".join(parts) or "(tổng)"


def series_vm(metric: dict) -> str:
    return metric.get("host") or (metric["instance"] if metric.get("instance") in VMS else "—")


def local(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def round_up(v: float) -> float:
    """Làm tròn lên 2 chữ số có nghĩa (vd. 0.0234 -> 0.024, 47.2 -> 48)."""
    if v <= 0:
        return 0.0
    e = math.floor(math.log10(v)) - 1
    return math.ceil(v / 10 ** e - 1e-9) * 10 ** e


def mechanical(st: dict, kind: str, cap) -> float | None:
    """Giá trị cơ học: trên = max(p99 + 3σ, max × 1,2); dưới = min × 0,5."""
    if not st.get("n"):
        return None
    if kind in ("capacity", "slo"):
        v = max(st["p99"] + 3 * st["std"], st["max"] * 1.2)
    elif kind == "traffic":
        v = st["min"] * 0.5
    else:
        return None
    return min(v, cap) if cap is not None else v


def propose(st: dict, m: float | None, kind: str, current: float | None) -> tuple:
    """(ngưỡng gợi ý, lý do). m = giá trị cơ học của chỉ số (lấy theo series khắt khe nhất)."""
    if m is None:
        return None, ""
    if kind == "capacity":
        if current is not None and m <= current:
            return current, "giữ: bình thường không chạm (max×1,2 / p99+3σ ≤ ngưỡng hiện hành)"
        return round_up(m), "NÂNG: mức bình thường đã gần/vượt ngưỡng hiện hành"
    if kind == "slo":
        if st["max"] == 0:
            return current, "giữ: không có lỗi nào trong baseline, chọn theo SLO"
        return round_up(m), "đệm trên mức bình thường; đối chiếu SLO trước khi chốt"
    if kind == "traffic":
        return (round(m, 3) if m else current), "một nửa lưu lượng thấp nhất"
    return None, ""


# ----------------------------------------------------------------------------- chất lượng dữ liệu
def data_quality(start: float, end: float) -> dict:
    """Độ phủ mẫu node của từng VM, khoảng trống dài nhất, số vòng đánh giá luật bị lỡ."""
    w = f"{max(SCRAPE_S, int(end - start))}s"
    expected = (end - start) / SCRAPE_S
    vms = {}
    for s in prom_query(f'up{{job="node"}}[{w}]', at=end):
        ts = [float(t) for t, _ in s["values"]]
        vals = [float(v) for _, v in s["values"]]
        edges = [start] + ts + [end]
        gap = max(b - a for a, b in zip(edges, edges[1:]))
        vms[s["metric"]["instance"]] = {
            "coverage": len(ts) / expected if expected else 0, "down": sum(1 for v in vals if v == 0), "max_gap_s": gap}
    missed = prom_query(f"sum(increase(prometheus_rule_group_iterations_missed_total[{w}]))", at=end)
    return {"vms": vms, "rule_missed": float(missed[0]["value"][1]) if missed else None}


def alerts_fired(start: float, end: float) -> list:
    """[(alertname, instance, số đợt, tổng thời gian firing s)] trong cửa sổ, từ chuỗi ALERTS."""
    w = f"{max(SCRAPE_S, int(end - start))}s"
    out = []
    for s in prom_query(f'ALERTS{{alertstate="firing",alertname!="LabTestAlert"}}[{w}]', at=end):
        ts = [float(t) for t, _ in s["values"]]
        episodes = 1 + sum(1 for a, b in zip(ts, ts[1:]) if b - a > 60)
        out.append((s["metric"]["alertname"], s["metric"].get("instance", ""), episodes, len(ts) * SCRAPE_S))
    return sorted(out)


def fault_samples(start: float, end: float, step: float) -> int:
    n = 0
    try:
        for s in prom_query_range("max(lab_fault_active)", start, end, step):
            n += sum(1 for _, v in s["values"] if float(v) > 0)
    except Exception:
        pass
    return n


# ----------------------------------------------------------------------------- thống kê
def analyze(start: float, end: float, step: float, label: str, out_dir: Path, raw: bool) -> Path:
    out = out_dir / (stamp() + (f"-{label}" if label else ""))
    out.mkdir(parents=True, exist_ok=True)

    thresholds = {}
    try:
        for s in prom_query('{__name__=~"lab:threshold:.*"}'):
            name = s["metric"]["__name__"].split(":", 2)[2]
            thresholds[name] = (float(s["value"][1]), s["metric"].get("threshold_status", ""))
    except Exception as e:
        sys.exit(f"Không truy vấn được Prometheus: {e}\nKiểm tra lab đang chạy: python tools/check_lab.py")

    faults = fault_samples(start, end, step)
    quality = data_quality(start, end)
    fired = alerts_fired(start, end)

    per_series, summary, per_vm, raw_rows = [], [], [], []
    for key, expr, unit, thr_name, kind, cap in METRICS:
        series = prom_query_range(expr, start, end, step)
        cur = thresholds.get(thr_name) if thr_name else None
        all_vals, mechs = [], []
        for s in series:
            vals = [float(v) for _, v in s["values"]]
            all_vals.extend(vals)
            st = describe(vals)
            lab = series_label(s["metric"])
            per_series.append({"metric": key, "series": lab, "unit": unit,
                               **{k: st.get(k) for k in ("n", "min", "mean", "std", "p50", "p90", "p95", "p99", "max")}})
            if mechanical(st, kind, cap) is not None:
                mechs.append(mechanical(st, kind, cap))
            if kind != "info":
                per_vm.append([series_vm(s["metric"]), key, lab, unit, fmt(st.get("mean")), fmt(st.get("p99")),
                               fmt(st.get("max")), fmt(mechanical(st, kind, cap))])
            if raw:
                raw_rows.extend((key, lab, iso(float(t)), v) for t, v in s["values"])
        st = describe(all_vals)
        mech = (min(mechs) if kind == "traffic" else max(mechs)) if mechs else None
        prop, why = propose(st, mech, kind, cur[0] if cur else None)
        summary.append([
            key, unit, len(series), st.get("n", 0), fmt(st.get("mean")), fmt(st.get("p99")), fmt(st.get("max")),
            fmt(st.get("std")), f"{cur[0]:g} ({cur[1]})" if cur else ("—" if not thr_name else "THIẾU"),
            fmt(mech), "" if prop is None else f"**{prop:g}**", why,
        ])
        print(f"  {key:<36} series={len(series):<3} n={st.get('n', 0):<6} max={fmt(st.get('max'))}")

    cols = ["metric", "series", "unit", "n", "min", "mean", "std", "p50", "p90", "p95", "p99", "max"]
    with open(out / "baseline.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in per_series:
            w.writerow({k: (fmt(v, 6) if isinstance(v, float) else v) for k, v in r.items()})
    if raw:
        with open(out / "samples.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["metric", "series", "time_utc", "value"])
            w.writerows(raw_rows)

    q_rows = [[vm, f"{v['coverage'] * 100:.2f} %", v["down"], f"{v['max_gap_s']:.0f}"]
              for vm, v in sorted(quality["vms"].items())]
    worst_gap = max((v["max_gap_s"] for v in quality["vms"].values()), default=float("inf"))
    clean = not faults and worst_gap <= 60 and not quality["rule_missed"]
    per_vm.sort(key=lambda r: (VMS.index(r[0]) if r[0] in VMS else 9, r[1], r[2]))
    md = [
        "# Kết quả đo baseline",
        "",
        f"- Cửa sổ: **{local(start)} → {local(end)}** giờ máy ({(end - start) / 3600:.2f} giờ; UTC {iso(start)} → {iso(end)}),"
        f" bước {step:g} s",
        f"- Nhãn: {label or '(không)'}",
        f"- Mẫu có lỗi giả lập đang bật: **{faults}**",
        f"- Vòng đánh giá luật bị lỡ (Windows ngủ/đứng): **{fmt(quality['rule_missed'])}**",
        f"- Khoảng trống dữ liệu dài nhất: **{worst_gap:.0f} s** (bình thường ≈ {SCRAPE_S} s)",
        f"- Kết luận: **{'dữ liệu sạch, dùng được' if clean else 'CÓ VẤN ĐỀ, xem bảng dưới trước khi dùng'}**",
        "",
        "## Chất lượng dữ liệu (theo mẫu `up{job=\"node\"}`)",
        "",
        md_table(["Máy ảo", "Độ phủ mẫu", "Mẫu down", "Khoảng trống dài nhất (s)"], q_rows),
        "",
        "## Cảnh báo đã bắn trong cửa sổ (ngưỡng hiện hành)",
        "",
        md_table(["Cảnh báo", "Instance", "Số đợt", "Tổng thời gian firing (s)"], fired) if fired else "Không có.",
        "",
        "Mỗi cảnh báo ở đây là một **báo giả** với ngưỡng hiện hành (không có lỗi giả lập nào).",
        "",
        "## Theo từng máy ảo",
        "",
        md_table(["Máy ảo", "Chỉ số", "Series", "Đơn vị", "TB", "p99", "Max", "Cơ học"], per_vm),
        "",
        "## Theo từng chỉ số (gộp mọi series) và ngưỡng gợi ý",
        "",
        md_table(["Chỉ số", "Đơn vị", "Series", "Mẫu", "TB", "p99", "Max", "σ", "Ngưỡng hiện hành", "Cơ học",
                  "Ngưỡng gợi ý", "Lý do"], summary),
        "",
        "## Quy tắc gợi ý",
        "",
        "- **Cơ học** = max(p99 + 3σ, max × 1,2) của từng series với ngưỡng trên; min × 0,5 với lưu lượng tối thiểu. Ở bảng",
        "  theo chỉ số lấy series khắt khe nhất (vì mỗi chỉ số chỉ có một ngưỡng chung). Đây là mức thấp nhất mà baseline này",
        "  không báo giả.",
        "- **Sức chứa** (CPU, RAM, đĩa, kết nối PostgreSQL): giữ ngưỡng hiện hành nếu cơ học không vượt nó, ngược lại nâng lên",
        "  cơ học. Không hạ ngưỡng xuống sát mức bình thường: ngưỡng sức chứa báo khi sắp hết tài nguyên, không phải khi khác thường.",
        "  Đĩa gần như không đổi trong 24 giờ, nên phân phối % không nói được tốc độ đầy.",
        "- **Chất lượng dịch vụ** (thời gian probe, p95 latency, tỉ lệ lỗi): cơ học làm tròn lên. Nhóm đối chiếu với SLO; nếu SLO",
        "  thấp hơn mức bình thường thì vấn đề là năng lực hệ thống, không phải ngưỡng.",
        "- Khi đã chốt: sửa `monitor/prometheus/rules/thresholds.yml` (`threshold_status: baselined`, ghi `basis`), chạy",
        "  `python tools/reload.py`, ghi lý do vào `docs/05-thu-nghiem/`.",
        "",
    ]
    (out / "baseline.md").write_text("\n".join(md), encoding="utf-8")
    (out / "meta.json").write_text(json.dumps({"start": start, "end": end, "step": step, "label": label,
                                                "fault_samples": faults, "quality": quality, "alerts_fired": fired,
                                                "clean": clean, "thresholds": thresholds},
                                               ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nChất lượng: {'sạch' if clean else 'CÓ VẤN ĐỀ'} (lỗi giả lập {faults} mẫu, khoảng trống dài nhất {worst_gap:.0f} s,"
          f" vòng luật bị lỡ {fmt(quality['rule_missed'])}); cảnh báo đã bắn: {len(fired)}")
    print(f"Đã ghi kết quả vào {out}")
    return out


# ----------------------------------------------------------------------------- đo trực tiếp, tiến độ
def read_state() -> dict:
    if not STATE.exists():
        sys.exit("Chưa có lần đo nào (data/baseline/state.json). Bắt đầu: python tools/baseline.py --minutes 1440 --wait")
    return json.loads(STATE.read_text(encoding="utf-8"))


def write_state(st: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")


def health() -> dict:
    """Ảnh chụp tình trạng lab, kiểu dữ liệu đơn giản để ghi jsonl."""
    h = {"ts": time.time(), "at": iso(time.time())}
    try:
        h["rule_eval_lag_s"] = rule_eval_lag()
        h["targets_down"] = [f"{r['metric']['job']}/{r['metric'].get('instance', '')}" for r in prom_query("up == 0")]
        h["faults_active"] = [r["metric"].get("instance", "") for r in prom_query("lab_fault_active == 1")]
        h["alerts_firing"] = [f"{r['metric']['alertname']}({r['metric'].get('instance', '')})"
                              for r in prom_query('ALERTS{alertstate="firing",alertname!="LabTestAlert"}')]
    except Exception as e:
        h["error"] = f"không truy vấn được Prometheus: {e}"
    try:
        from fault import host_free_mb
        h["host_free_mb"] = host_free_mb()
    except Exception:
        pass
    return h


def pid_alive(pid: int) -> bool:
    if os.name == "nt":
        import ctypes

        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        code = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(handle)
        return code.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def cmd_wait(a: argparse.Namespace) -> None:
    try:
        from fault import keep_awake
    except Exception:
        def keep_awake(on: bool) -> None:
            pass
    if prom_query("lab_fault_active == 1"):
        sys.exit("Đang có lỗi giả lập bật (lab_fault_active == 1). Gỡ bằng: python tools/fault.py recover")
    lag = rule_eval_lag()
    if lag is None or abs(lag) > 1:
        sys.exit(f"Prometheus đánh giá luật trễ {lag}s — khởi động lại Prometheus trước (SC-04).")
    start = time.time()
    end = start + a.minutes * 60
    st = {"label": a.label, "minutes": a.minutes, "step": a.step, "start": start, "end": end, "start_at": iso(start),
          "end_at": iso(end), "pid": os.getpid(), "status": "running", "result": None}
    write_state(st)
    keep_awake(True)
    print(f"Đo baseline {local(start)} → {local(end)} (giờ máy). KHÔNG chạy kịch bản lỗi, không tắt/ngủ máy.", flush=True)
    print("Xem tiến độ: python tools/baseline.py --status", flush=True)
    next_health = 0.0
    try:
        while time.time() < end:
            if time.time() >= next_health:
                h = health()
                append_jsonl(HEALTH, {"label": a.label, **h})
                left = end - time.time()
                print(f"[{datetime.now():%H:%M}] còn {int(left // 3600)} giờ {int(left % 3600 // 60):02d} phút;"
                      f" trễ luật {h.get('rule_eval_lag_s')}s; target down {len(h.get('targets_down', []))};"
                      f" cảnh báo firing {h.get('alerts_firing', [])}; RAM trống {h.get('host_free_mb')} MB", flush=True)
                next_health = time.time() + HEALTH_EVERY_S
            time.sleep(min(30, max(0.1, end - time.time())))
    except KeyboardInterrupt:
        print("\nDừng sớm — thống kê phần đã đo.", flush=True)
        end = time.time()
        st["end"], st["end_at"] = end, iso(end)
    finally:
        keep_awake(False)
    st["status"] = "analyzing"
    write_state(st)
    out = analyze(start, end, a.step, a.label, a.out_dir, a.raw)
    st["status"], st["result"] = "done", str(out)
    write_state(st)


def cmd_status() -> None:
    st = read_state()
    now = time.time()
    total = st["end"] - st["start"]
    done = min(now, st["end"]) - st["start"]
    alive = pid_alive(st["pid"])
    print(f"Lần đo: {st['label'] or '(không nhãn)'} — trạng thái: {st['status']}"
          f"{'' if st['status'] != 'running' else (' (tiến trình đang chạy)' if alive else ' — TIẾN TRÌNH ĐÃ DỪNG')}")
    print(f"  Bắt đầu:  {local(st['start'])}")
    print(f"  Dự kiến xong: {local(st['end'])} (giờ máy), thêm vài phút để thống kê")
    print(f"  Tiến độ:  {done / total * 100:.1f} % — đã đo {done / 3600:.2f} giờ, còn {max(0, st['end'] - now) / 3600:.2f} giờ")
    if st["status"] == "done":
        print(f"  Kết quả:  {st['result']}{os.sep}baseline.md")
        return
    if st["status"] == "running" and not alive:
        print("  ! Tiến trình đo không còn chạy. Dữ liệu vẫn trong Prometheus: thống kê phần đã có bằng"
              " python tools/baseline.py --from-state")
    h = health()
    print(f"  Lab bây giờ: trễ luật {h.get('rule_eval_lag_s')} s; target down {h.get('targets_down')};"
          f" lỗi giả lập {h.get('faults_active')}; cảnh báo firing {h.get('alerts_firing')}; RAM trống Windows"
          f" {h.get('host_free_mb')} MB{'; ' + h['error'] if 'error' in h else ''}")
    try:
        q = data_quality(st["start"], min(now, st["end"]))
        print("  Dữ liệu tới giờ: " + "; ".join(f"{vm} phủ {v['coverage'] * 100:.1f} %, trống dài nhất {v['max_gap_s']:.0f} s"
                                               for vm, v in sorted(q["vms"].items()))
              + f"; vòng luật bị lỡ {fmt(q['rule_missed'])}")
    except Exception as e:
        print(f"  Không kiểm tra được dữ liệu: {e}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--minutes", type=float, help="độ dài cửa sổ baseline (phút); 24 giờ = 1440")
    ap.add_argument("--wait", action="store_true", help="đo từ bây giờ trong N phút rồi thống kê")
    ap.add_argument("--status", action="store_true", help="xem tiến độ lần đo gần nhất")
    ap.add_argument("--from-state", action="store_true", help="thống kê cửa sổ của lần đo gần nhất (tới giờ nếu chưa hết)")
    ap.add_argument("--end", help="thời điểm kết thúc cửa sổ (ISO-8601), mặc định là bây giờ")
    ap.add_argument("--step", type=float, default=15, help="bước lấy mẫu (giây), mặc định 15 = scrape_interval")
    ap.add_argument("--raw", action="store_true", help="ghi thêm toàn bộ mẫu thô ra samples.csv")
    ap.add_argument("--label", default="", help="nhãn mô tả lần đo (vd. 'baseline-24h')")
    ap.add_argument("--out-dir", type=Path, default=RESULTS_DIR / "baseline")
    a = ap.parse_args()

    if a.status:
        return cmd_status()
    if a.from_state:
        st = read_state()
        end = min(time.time(), st["end"])
        return None if analyze(st["start"], end, st.get("step", a.step), st["label"], a.out_dir, a.raw) else None
    if a.minutes is None:
        ap.error("cần --minutes (hoặc --status / --from-state)")
    if a.wait:
        return cmd_wait(a)
    end = parse_iso(a.end) if a.end else time.time()
    if end is None:
        sys.exit("--end không hợp lệ")
    analyze(end - a.minutes * 60, end, a.step, a.label, a.out_dir, a.raw)


if __name__ == "__main__":
    main()
