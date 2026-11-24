"""Gây lỗi mô phỏng trên VM web, db qua SSH bị giới hạn (ADR-0007) và ghi sự kiện để đo thời gian phát hiện.

  python tools/fault.py list                                  kịch bản được phép trên từng VM
  python tools/fault.py status                                VM nào đang có lỗi
  python tools/fault.py recover [--vm web]                    gỡ mọi lỗi (chạy lại nhiều lần vẫn an toàn)
  python tools/fault.py run cpu --vm web                      gây lỗi, giữ --duration giây rồi gỡ
  python tools/fault.py run service-stop --service nginx      VM tự suy ra từ dịch vụ
  python tools/fault.py run disk --vm db --stop-on-alert      gỡ sớm khi cảnh báo mong đợi đã tới
  python tools/fault.py run latency --repeat 5                lặp lại, chờ lab sạch giữa các lần
  python tools/fault.py run errors --dry-run                  chỉ in lệnh sẽ gửi

Mỗi lần chạy ghi vào data/events/faults.jsonl: một dòng lúc gây lỗi, một dòng (cùng fault_id) lúc gỡ; dòng sau thay
dòng trước. Trước khi gây lỗi, script kiểm tra: không VM nào đang có lỗi, không cảnh báo nào pending/firing, đồng hồ
VM ổn định. Trong lúc chạy, Windows được giữ không ngủ (hết hiệu lực khi script thoát).

Mốc thời gian:
  injected_ts_receiver   giờ VM ngay sau khi thao tác gây lỗi hoàn tất, đã trừ độ lệch đồng hồ VM so với monitor
                         (alert-recorder chạy trên monitor nên cùng đồng hồ với mốc nhận cảnh báo)
  injected_ts            giờ máy Windows lúc lệnh SSH trả về, chỉ để tham khảo
Ctrl+C giữa chừng: script gỡ lỗi rồi thoát. Kể cả khi script bị tắt hẳn, VM vẫn tự gỡ khi hết hạn.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.common import EVENT_LOG, WEBHOOK_URL, append_jsonl, http, iso, labels_match, prom_query  # noqa: E402
from lib.faultssh import VM_IPS, fault_ssh  # noqa: E402

VM_MAX_DURATION = 900     # giới hạn của obslab-fault
CLOCK_LIMIT_S = 0.1       # đồng hồ VM lệch monitor quá mức này thì không đo
SAFETY_MARGIN = 60        # VM tự gỡ muộn hơn script ngần này, phòng khi script chết
SERVICE_VM = {"nginx": "web", "demo-app": "web", "postgresql": "db"}
SERVICE_ROOT = {"nginx": "NginxDown", "demo-app": "ServiceDown", "postgresql": "PostgresDown"}

# kịch bản -> (cảnh báo gốc, các cảnh báo khác cũng là phát hiện hợp lệ của cùng lỗi)
EXPECTED = {
    "cpu": ("HostHighCpu", []),
    "memory": ("HostHighMemory", []),
    "disk": ("HostDiskAlmostFull", []),
    "latency": ("ServiceHighLatency", ["EndpointSlow"]),
    "errors": ("ServiceHighErrorRate", []),
}
PARAMS = {"cpu": [], "memory": ["percent"], "disk": ["percent"], "service-stop": ["service"],
          "latency": ["latency_ms"], "errors": ["error_rate"]}


class FaultError(Exception):
    pass


def call(vm: str, command: str) -> dict:
    """Gọi obslab-fault, trả về JSON. Ném FaultError kèm thông báo của VM nếu thất bại."""
    try:
        cp = fault_ssh(vm, command)
    except subprocess.TimeoutExpired:
        raise FaultError(f"{vm}: quá thời gian chờ SSH khi gọi '{command}'")
    if cp.returncode != 0:
        raise FaultError(f"{vm}: '{command}' thất bại (mã {cp.returncode}): {(cp.stderr or cp.stdout).strip()}")
    try:
        return json.loads(cp.stdout)
    except json.JSONDecodeError:
        raise FaultError(f"{vm}: kết quả không đọc được: {cp.stdout.strip()}")


def expected_alerts(scenario: str, service: str | None) -> tuple:
    if scenario != "service-stop":
        return EXPECTED[scenario]
    others = ["EndpointDown"] if service == "postgresql" else ["ServiceDown", "EndpointDown"]
    return SERVICE_ROOT[service], [x for x in others if x != SERVICE_ROOT[service]]


def match_labels(scenario: str, vm: str) -> dict:
    labels = {"host": vm}
    if scenario == "disk":
        labels["mountpoint"] = "/mnt/labdisk"
    return labels


def keep_awake(on: bool) -> None:
    """Giữ Windows không ngủ khi tiến trình này còn chạy (ngủ làm đứng VM và lệch đồng hồ). Không đổi cài đặt máy."""
    if os.name == "nt":
        import ctypes

        ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if on else 0))


# Đồng hồ VM − đồng hồ monitor: giá trị trong lần scrape trừ thời điểm scrape (gồm cả vài ms độ trễ scrape).
CLOCK_DIFF = 'node_time_seconds{job="node",instance="%s"} - timestamp(node_time_seconds{job="node",instance="%s"})'


def clock_problem(vm: str) -> str | None:
    """Đồng hồ VM phải ổn định suốt 2 phút gần nhất thì mốc gây lỗi mới tin được."""
    diff = CLOCK_DIFF % (vm, vm)
    n = prom_query(f'count_over_time(node_time_seconds{{job="node",instance="{vm}"}}[2m])')
    if not n or float(n[0]["value"][1]) < 6:
        return f"thiếu dữ liệu {vm} trong 2 phút qua (VM hoặc Windows vừa ngủ/khởi động?)"
    worst = max(float(r["value"][1]) for r in prom_query(f"max_over_time(abs({diff})[2m:15s])"))
    if worst > CLOCK_LIMIT_S:
        return f"đồng hồ {vm} lệch monitor tới {worst:.2f}s trong 2 phút qua (chờ chrony ổn định)"
    return None


def vm_clock_offset(vm: str) -> float | None:
    """Độ lệch đồng hồ VM so với monitor (giây), trung vị 2 phút."""
    expr = f"quantile_over_time(0.5, ({CLOCK_DIFF % (vm, vm)})[2m:15s])"
    try:
        r = prom_query(expr)
        return round(float(r[0]["value"][1]), 3) if r else None
    except Exception:
        return None


def active_alerts() -> list:
    return [f"{r['metric']['alertname']}({r['metric'].get('instance', '')}, {r['metric']['alertstate']})"
            for r in prom_query('ALERTS{alertname!="LabTestAlert"}')]


def dirty_reasons() -> list:
    """Lý do lab chưa sẵn sàng cho một phép đo sạch."""
    out = []
    for vm in VM_IPS:
        st = call(vm, "status")
        if st["active"]:
            out.append(f"{vm} đang có kịch bản {st['scenario']}")
        problem = clock_problem(vm)
        if problem:
            out.append(problem)
    return out + [f"cảnh báo {a}" for a in active_alerts()]


def wait_clean(limit: float, settle: float) -> None:
    deadline = time.time() + limit
    print(f"  Chờ lab sạch rồi nghỉ thêm {settle:.0f}s ...", flush=True)
    while True:
        reasons = dirty_reasons()
        if not reasons:
            break
        if time.time() > deadline:
            raise FaultError("lab chưa sạch: " + "; ".join(reasons))
        time.sleep(5)
    time.sleep(settle)


def received_alerts(root: str, others: list, match: dict, since: float) -> list:
    try:
        items = http("GET", f"{WEBHOOK_URL}/alerts?limit=500", timeout=5)["alerts"]
    except Exception:
        return []   # mất kết nối tạm thời: lần sau hỏi lại
    return [a for a in items
            if a.get("status") == "firing" and a.get("received_ts", 0) >= since
            and a.get("alertname") in [root, *others] and labels_match(a.get("labels", {}), match)]


def recover_vm(vm: str, command: str = "recover") -> float | None:
    """Gỡ lỗi, thử lại vài lần. Trả về giờ VM lúc gỡ xong, hoặc None nếu không gỡ được."""
    for attempt in range(3):
        try:
            return call(vm, command)["ts"]
        except FaultError as e:
            print(f"  ! {e}", file=sys.stderr, flush=True)
            time.sleep(3 * (attempt + 1))
    print(f"  ! Chưa gỡ được lỗi trên {vm}. VM sẽ tự gỡ khi hết hạn; kiểm tra: python tools/fault.py status",
          file=sys.stderr, flush=True)
    return None


def run_once(a: argparse.Namespace, params: dict) -> dict:
    root, others = expected_alerts(a.scenario, a.service)
    match = match_labels(a.scenario, a.vm)
    vm_duration = min(VM_MAX_DURATION, a.duration + SAFETY_MARGIN)
    command = " ".join([a.scenario, "start", f"duration={vm_duration}", *(f"{k}={v}" for k, v in params.items())])
    if a.jitter:
        d = random.uniform(0, a.jitter)   # rải đều pha so với chu kỳ scrape để kết quả không thiên lệch
        print(f"  Chờ ngẫu nhiên {d:.1f}s")
        time.sleep(d)

    offset = vm_clock_offset(a.vm)
    if offset is None:
        print("  ! Không đọc được độ lệch đồng hồ từ Prometheus, coi như 0")
    elif abs(offset) > CLOCK_LIMIT_S:
        print(f"  ! Đồng hồ {a.vm} lệch monitor {offset:+.3f}s (đã hiệu chỉnh, nhưng kết quả kém tin cậy)")

    ev = None
    stop_reason = "lỗi"
    try:
        print(f"  {a.vm}: {command}", flush=True)
        started = call(a.vm, command)
        local = time.time()
        t0 = started["started_ts"] - (offset or 0.0)
        ev = {
            "fault_id": f"{a.scenario}-{a.vm}-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}",
            "scenario": a.scenario if a.scenario != "service-stop" else f"service-stop:{a.service}",
            "target": a.vm, "params": params, "note": a.note,
            "expected_alerts": [root, *others], "root_alert": root, "match_labels": match,
            "injected_at": iso(t0), "injected_ts": round(local, 3),
            "injected_ts_receiver": round(t0, 3), "injected_ts_vm": started["started_ts"],
            "vm_clock_offset_s": offset, "hold_s": a.duration,
            "recovered_ts": None, "recovered_ts_receiver": None, "stop_reason": None,
        }
        append_jsonl(EVENT_LOG, ev)
        print(f"  Đã gây lỗi lúc {ev['injected_at']} — {ev['fault_id']}; chờ {root}", flush=True)

        seen = set()
        root_at = None
        end = time.monotonic() + a.duration
        stop_reason = "hết thời gian giữ"
        while time.monotonic() < end:
            for al in received_alerts(root, others, match, t0 - 2):
                key = (al["alertname"], al.get("fingerprint"))
                if key not in seen:
                    seen.add(key)
                    print(f"    + {al['alertname']} sau {al['received_ts'] - t0:.1f}s", flush=True)
                    if al["alertname"] == root and root_at is None:
                        root_at = time.monotonic()
            if a.stop_on_alert and root_at is not None and time.monotonic() - root_at >= a.linger:
                stop_reason = "đã nhận cảnh báo gốc"
                break
            time.sleep(min(2, max(0.0, end - time.monotonic())))
        if root_at is None:
            print(f"    KHÔNG nhận được {root} trong {a.duration}s", flush=True)
        ev["root_received"] = root_at is not None
    except KeyboardInterrupt:
        stop_reason = "người dùng ngắt (Ctrl+C)"
        print("\n  Ngắt — đang gỡ lỗi, vui lòng chờ ...", flush=True)
        raise
    finally:
        # Gỡ dù thành công, lỗi hay bị ngắt. Nếu start hỏng giữa chừng thì không biết lỗi đã tác động chưa -> cũng gỡ,
        # trừ khi VM từ chối vì đang chạy kịch bản của người khác (mã 3).
        exc = sys.exc_info()[1]
        refused = isinstance(exc, FaultError) and any(f"(mã {c})" in str(exc) for c in (2, 3, 126))
        if ev is not None or not refused:
            ts = recover_vm(a.vm, f"{a.scenario} stop" if ev is not None else "recover")
            if ev is not None:
                ev["recovered_ts_receiver"] = round(ts - (offset or 0.0), 3) if ts else None
                ev["recovered_ts"] = round(time.time(), 3) if ts else None
                ev["recovered_at"] = iso(ev["recovered_ts_receiver"]) if ts else None
                ev["stop_reason"] = stop_reason if ts else f"{stop_reason}; CHƯA gỡ được"
                append_jsonl(EVENT_LOG, ev)
                if ts:
                    print(f"  Đã gỡ lỗi lúc {ev['recovered_at']} ({stop_reason})", flush=True)
    return ev


def cmd_run(a: argparse.Namespace) -> int:
    if a.scenario == "service-stop":
        if not a.service:
            raise FaultError(f"service-stop cần --service ({', '.join(SERVICE_VM)})")
        if a.vm and a.vm != SERVICE_VM[a.service]:
            raise FaultError(f"{a.service} nằm trên VM {SERVICE_VM[a.service]}, không phải {a.vm}")
        a.vm = SERVICE_VM[a.service]
    elif a.scenario in ("latency", "errors"):
        if a.vm not in (None, "web"):
            raise FaultError(f"{a.scenario} chỉ chạy trên VM web")
        a.vm = "web"
    elif not a.vm:
        raise FaultError(f"{a.scenario} cần --vm web hoặc --vm db")
    params = {}
    for k in ("service", "percent", "latency_ms", "error_rate"):
        v = getattr(a, k)
        if v is None:
            continue
        if k not in PARAMS[a.scenario]:
            raise FaultError(f"kịch bản {a.scenario} không nhận --{k.replace('_', '-')}")
        params[k] = v
    if a.jitter is None:
        a.jitter = 15.0 if a.repeat > 1 else 0.0

    root, others = expected_alerts(a.scenario, a.service)
    print(f"Kịch bản {a.scenario} trên {a.vm} — cảnh báo gốc {root}" + (f", có thể kèm {', '.join(others)}" if others else ""))
    if a.dry_run:
        d = min(VM_MAX_DURATION, a.duration + SAFETY_MARGIN)
        print("  (dry-run) " + " ".join([a.scenario, "start", f"duration={d}", *(f"{k}={v}" for k, v in params.items())]))
        return 0

    keep_awake(True)
    missed = 0
    for i in range(1, a.repeat + 1):
        print(f"== Lần {i}/{a.repeat}", flush=True)
        if i == 1 and not a.wait_clean:
            reasons = dirty_reasons()
            if reasons and not a.force:
                raise FaultError("lab chưa sạch: " + "; ".join(reasons) + ". Chờ hết, hoặc --wait-clean, hoặc --force.")
        else:
            wait_clean(a.clean_timeout, a.cooldown)
        ev = run_once(a, params)
        missed += not ev["root_received"]
    print(f"\nXong {a.repeat} lần, không phát hiện: {missed}. Sự kiện: {EVENT_LOG}")
    return 1 if missed else 0


def cmd_list(_a) -> int:
    for vm in VM_IPS:
        d = call(vm, "list")
        print(f"{vm}: {d['scenarios']}  (service-stop: {d['services']}; {d['duration_min']}–{d['duration_max']}s)")
    return 0


def cmd_status(_a) -> int:
    for vm in VM_IPS:
        st = call(vm, "status")
        if st["active"]:
            print(f"{vm}: {st['scenario']} ({st['params']}), tự gỡ sau {st['until_ts'] - st['ts']:.0f}s")
        else:
            print(f"{vm}: không có lỗi")
    alerts = active_alerts()
    print("Cảnh báo pending/firing: " + (", ".join(alerts) or "không"))
    return 0


def cmd_recover(a) -> int:
    ok = True
    for vm in ([a.vm] if a.vm else VM_IPS):
        ts = recover_vm(vm)
        ok &= ts is not None
        print(f"{vm}: {'đã gỡ' if ts else 'CHƯA gỡ được'}")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="kịch bản được phép trên từng VM").set_defaults(fn=cmd_list)
    sub.add_parser("status", help="lỗi và cảnh báo đang hoạt động").set_defaults(fn=cmd_status)
    p = sub.add_parser("recover", help="gỡ mọi lỗi")
    p.add_argument("--vm", choices=list(VM_IPS))
    p.set_defaults(fn=cmd_recover)

    p = sub.add_parser("run", help="gây một kịch bản lỗi")
    p.add_argument("scenario", choices=list(PARAMS))
    p.add_argument("--vm", choices=list(VM_IPS))
    p.add_argument("--service", choices=list(SERVICE_VM))
    p.add_argument("--percent", type=int, help="memory 50–97, disk 50–99 (mặc định của VM: 95)")
    p.add_argument("--latency-ms", type=int, help="latency: 100–7000 (mặc định 3000)")
    p.add_argument("--error-rate", type=int, help="errors: 1–100 %% (mặc định 50)")
    p.add_argument("--duration", type=int, default=240, help="giữ lỗi bao nhiêu giây, 30–840 (mặc định 240)")
    p.add_argument("--stop-on-alert", action="store_true", help="gỡ sớm khi đã nhận cảnh báo gốc")
    p.add_argument("--linger", type=float, default=20, help="với --stop-on-alert: giữ thêm N giây để thấy cảnh báo kèm theo")
    p.add_argument("--repeat", type=int, default=1, help="số lần chạy")
    p.add_argument("--cooldown", type=float, default=90, help="nghỉ sau khi lab đã sạch, trước lần kế tiếp (giây)")
    p.add_argument("--clean-timeout", type=float, default=600, help="chờ lab sạch tối đa N giây")
    p.add_argument("--jitter", type=float, help="chờ ngẫu nhiên 0..N giây trước khi gây lỗi (mặc định 15 khi --repeat > 1)")
    p.add_argument("--wait-clean", action="store_true", help="chờ lab sạch cả ở lần đầu thay vì báo lỗi")
    p.add_argument("--force", action="store_true", help="bỏ qua kiểm tra lab sạch (kết quả đo có thể nhiễu)")
    p.add_argument("--note", default="", help="ghi chú lưu kèm sự kiện")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(fn=cmd_run)

    a = ap.parse_args()
    if a.cmd == "run" and (not 30 <= a.duration <= VM_MAX_DURATION - SAFETY_MARGIN or a.repeat < 1):
        ap.error(f"--duration phải trong 30..{VM_MAX_DURATION - SAFETY_MARGIN}, --repeat >= 1")
    try:
        return a.fn(a)
    except FaultError as e:
        print(f"LỖI: {e}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Đã dừng theo yêu cầu.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
