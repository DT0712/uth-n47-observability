"""Bộ kịch bản lỗi cho lab. Mỗi lần chạy ghi một sự kiện vào data/events/faults.jsonl.

Ví dụ (PowerShell hoặc WSL, chạy từ thư mục gốc repo):
  python scripts/fault.py list
  python scripts/fault.py cpu --duration 180
  python scripts/fault.py disk
  python scripts/fault.py service-down --target svc-payments
  python scripts/fault.py slow --target svc-api --latency-ms 3000
  python scripts/fault.py error --target svc-orders --error-rate 0.5
  python scripts/fault.py memory --mb 1024
  python scripts/fault.py all --cooldown 180         # chạy lần lượt các kịch bản chính
  python scripts/fault.py recover                    # gỡ mọi lỗi đang treo (khi script bị ngắt giữa chừng)

Mặc định mỗi kịch bản giữ lỗi trong --duration giây rồi tự khôi phục. Với --stop-on-alert,
script khôi phục ngay khi webhook-receiver nhận được cảnh báo mong đợi (tiết kiệm thời gian).

Mốc thời gian ghi lại:
  injected_ts            : (đồng hồ máy chạy script) ngay SAU khi thao tác gây lỗi hoàn tất
  injected_ts_receiver   : cùng thời điểm đó quy đổi sang đồng hồ webhook-receiver (dùng để tính
                           thời gian phát hiện, loại bỏ lệch đồng hồ Windows <-> WSL2)
  recovered_ts           : sau khi khôi phục
"""

from __future__ import annotations

import argparse
import sys
import time
import uuid
from dataclasses import dataclass, field
from typing import Callable, Optional

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from lib.common import (  # noqa: E402
    ALERT_LOG,
    EVENT_LOG,
    SERVICE_PORTS,
    append_jsonl,
    compose,
    http,
    iso,
    labels_match,
    prom_scalar,
    read_jsonl,
    receiver_clock_offset,
    run,
)

DEMO_IMAGE = "obslab/demo-service:local"
STRESS_CONTAINER = "obslab-fault-stress"
DISK_SERVICE = "svc-orders"  # dịch vụ gắn ổ lab-disk tại /data
SERVICES = list(SERVICE_PORTS)


@dataclass
class Scenario:
    name: str
    description: str
    expected_alerts: list
    inject: Callable[[argparse.Namespace], dict]
    recover: Callable[[argparse.Namespace], None]
    match_labels: Callable[[argparse.Namespace], dict] = field(default=lambda a: {})


# ------------------------------------------------------------------------- helpers
def threshold(name: str, default: float) -> float:
    v = prom_scalar(f"max(lab:threshold:{name})")
    if v is None:
        print(f"  (không đọc được ngưỡng {name} từ Prometheus, dùng {default})")
        return default
    return v


def svc_admin(service: str, path: str, body: Optional[dict] = None) -> dict:
    url = f"http://localhost:{SERVICE_PORTS[service]}{path}"
    print(f"  POST {url} {body or ''}")
    return http("POST", url, body=body or {}, timeout=10)


def rm_stress() -> None:
    run(["docker", "rm", "-f", STRESS_CONTAINER], check=False)


# ------------------------------------------------------------------------- CPU
def inject_cpu(a):
    rm_stress()
    workers = a.workers
    if not workers:
        cp = run(["docker", "info", "--format", "{{.NCPU}}"], check=False)
        workers = int(cp.stdout.strip() or 2) if cp.returncode == 0 else 2
    # Chạy lâu hơn duration một chút; recover sẽ xoá container. Nếu script bị ngắt,
    # container vẫn tự kết thúc sau thời gian này.
    run(["docker", "run", "-d", "--rm", "--name", STRESS_CONTAINER, "--label", "obslab.fault=cpu",
         DEMO_IMAGE, "python", "stress.py", "cpu", "--seconds", str(a.duration + 60), "--workers", str(workers)])
    return {"workers": workers}


def recover_stress(a):
    rm_stress()


# ------------------------------------------------------------------------- Memory
def inject_memory(a):
    rm_stress()
    mb = a.mb
    if not mb:
        total = prom_scalar('max(node_memory_MemTotal_bytes{job="node"})')
        used = prom_scalar("max(lab:host_memory_usage:percent)")
        thr = threshold("host_memory_usage_percent", 90)
        if total is None or used is None:
            sys.exit("Không đọc được RAM hiện tại từ Prometheus; hãy truyền --mb.")
        target = min(thr + 3, 97)
        mb = int(max(0, (target - used) / 100 * total / 1048576)) + 64
        print(f"  RAM đang dùng {used:.1f}%, ngưỡng {thr}%, cấp phát thêm ~{mb} MiB để vượt ngưỡng")
    run(["docker", "run", "-d", "--rm", "--name", STRESS_CONTAINER, "--label", "obslab.fault=memory",
         DEMO_IMAGE, "python", "stress.py", "memory", "--seconds", str(a.duration + 60), "--mb", str(mb)])
    return {"mb": mb}


# ------------------------------------------------------------------------- Disk
def inject_disk(a):
    pct = a.percent or min(threshold("filesystem_usage_percent", 90) + 5, 99)
    compose("exec", "-T", DISK_SERVICE, "python", "fill_disk.py", "--path", "/data", "--percent", str(pct))
    return {"percent": pct, "volume": "lab-disk", "service": DISK_SERVICE}


def recover_disk(a):
    compose("exec", "-T", DISK_SERVICE, "python", "fill_disk.py", "--path", "/data", "--clean", check=False)


# ------------------------------------------------------------------------- Service down
def inject_down(a):
    compose("stop", a.target, timeout=60)
    return {"service": a.target}


def recover_down(a):
    compose("start", a.target, timeout=60)


# ------------------------------------------------------------------------- Slow / error
def inject_slow(a):
    latency = a.latency_ms or 3000
    svc_admin(a.target, "/admin/fault", {"latency_ms": latency})
    return {"service": a.target, "latency_ms": latency}


def inject_error(a):
    rate = a.error_rate if a.error_rate is not None else 0.5
    svc_admin(a.target, "/admin/fault", {"error_rate": rate})
    return {"service": a.target, "error_rate": rate}


def recover_fault_api(a):
    try:
        svc_admin(a.target, "/admin/reset")
    except Exception as e:  # dịch vụ có thể đang down
        print(f"  reset lỗi: {e}")


SCENARIOS = {
    s.name: s
    for s in [
        Scenario("cpu", "CPU cao: chạy container stress chiếm mọi lõi của host",
                 ["HostHighCpu"], inject_cpu, recover_stress),
        Scenario("memory", "RAM cao (tuỳ chọn): container cấp phát RAM tới quá ngưỡng",
                 ["HostHighMemory"], inject_memory, recover_stress),
        Scenario("disk", "Disk đầy giả lập: ghi file lớn vào ổ lab-disk (tmpfs giới hạn)",
                 ["HostDiskAlmostFull"], inject_disk, recover_disk, lambda a: {"instance": "lab-disk"}),
        Scenario("service-down", "Service down: dừng container dịch vụ",
                 ["ServiceDown", "EndpointDown"], inject_down, recover_down, lambda a: {"service": a.target}),
        Scenario("slow", "Endpoint chậm: tiêm độ trễ vào /health và /api/work",
                 ["EndpointSlow", "ServiceHighLatency"], inject_slow, recover_fault_api, lambda a: {"service": a.target}),
        Scenario("error", "Endpoint lỗi: tiêm tỉ lệ lỗi 5xx vào /api/work",
                 ["ServiceHighErrorRate"], inject_error, recover_fault_api, lambda a: {"service": a.target}),
    ]
}
DEFAULT_ALL = ["cpu", "disk", "service-down", "slow", "error"]


# ------------------------------------------------------------------------- vòng chạy
def wait_for_alert(expected: list, match: dict, since_receiver_ts: float, timeout: float) -> Optional[dict]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        for rec in read_jsonl(ALERT_LOG):
            if (rec.get("status") == "firing" and rec.get("alertname") in expected
                    and rec.get("received_ts", 0) >= since_receiver_ts - 1
                    and labels_match(rec.get("labels", {}), match)):
                return rec
        remaining = int(deadline - time.time())
        print(f"\r  chờ cảnh báo {expected} ... còn {remaining:4d}s", end="", flush=True)
        time.sleep(5)
    print()
    return None


def run_scenario(name: str, a: argparse.Namespace) -> dict:
    sc = SCENARIOS[name]
    fault_id = f"{time.strftime('%Y%m%d-%H%M%S')}-{name}-{uuid.uuid4().hex[:4]}"
    match = sc.match_labels(a)
    print(f"\n=== [{fault_id}] {sc.description}")
    print(f"    mong đợi cảnh báo: {', '.join(sc.expected_alerts)} {match or ''}")

    offset = receiver_clock_offset()
    if offset is None:
        print("  ! Không kết nối được webhook-receiver: sẽ dùng đồng hồ local (có thể lệch).")

    t_before = time.time()
    params = sc.inject(a)
    t_inj = time.time()
    event = {
        "fault_id": fault_id,
        "scenario": name,
        "description": sc.description,
        "target": match.get("service") or match.get("instance") or "lab-docker-host",
        "params": params,
        "expected_alerts": sc.expected_alerts,
        "match_labels": match,
        "inject_started_ts": round(t_before, 3),
        "injected_ts": round(t_inj, 3),
        "injected_at": iso(t_inj),
        "clock_offset_s": offset,
        "injected_ts_receiver": round(t_inj + offset, 3) if offset is not None else None,
        "duration_s": a.duration,
        "notes": a.notes or "",
    }
    print(f"  -> lỗi đã gây lúc {event['injected_at']} (lệch đồng hồ receiver: {offset}s)")

    detected = None
    try:
        if a.no_recover:
            print("  --no-recover: giữ nguyên lỗi. Gỡ bằng: python scripts/fault.py recover")
        elif a.stop_on_alert:
            ref = event["injected_ts_receiver"] or t_inj
            detected = wait_for_alert(sc.expected_alerts, match, ref, a.duration)
        else:
            end = t_inj + a.duration
            while time.time() < end:
                print(f"\r  giữ lỗi ... còn {int(end - time.time()):4d}s", end="", flush=True)
                time.sleep(min(5, max(0.1, end - time.time())))
            print()
    except KeyboardInterrupt:
        print("\n  bị ngắt — khôi phục ngay.")
    finally:
        if not a.no_recover:
            sc.recover(a)
            t_rec = time.time()
            event["recovered_ts"] = round(t_rec, 3)
            event["recovered_at"] = iso(t_rec)
            if offset is not None:
                event["recovered_ts_receiver"] = round(t_rec + offset, 3)
        append_jsonl(EVENT_LOG, event)

    if detected:
        ref = event["injected_ts_receiver"] or t_inj
        print(f"  ✓ nhận {detected['alertname']} sau {detected['received_ts'] - ref:.1f}s")
    print(f"  đã ghi sự kiện vào {EVENT_LOG.relative_to(EVENT_LOG.parents[2])}")
    return event


def recover_all(a: argparse.Namespace) -> None:
    print("Gỡ mọi lỗi giả lập ...")
    rm_stress()
    compose("exec", "-T", DISK_SERVICE, "python", "fill_disk.py", "--path", "/data", "--clean", check=False)
    for svc in SERVICES:
        compose("start", svc, check=False)
    time.sleep(3)
    for svc in SERVICES:
        try:
            svc_admin(svc, "/admin/reset")
        except Exception as e:
            print(f"  {svc}: {e}")
    print("Xong.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("scenario", choices=["list", "all", "recover", *SCENARIOS])
    ap.add_argument("--target", default=None, help=f"dịch vụ đích cho service-down/slow/error ({', '.join(SERVICES)})")
    ap.add_argument("--duration", type=int, default=180, help="giữ lỗi bao lâu (giây), mặc định 180")
    ap.add_argument("--stop-on-alert", action="store_true", help="khôi phục ngay khi nhận cảnh báo mong đợi")
    ap.add_argument("--no-recover", action="store_true", help="không tự khôi phục")
    ap.add_argument("--cooldown", type=int, default=180, help="(all) nghỉ giữa các kịch bản để cảnh báo resolve")
    ap.add_argument("--repeat", type=int, default=1, help="(all) lặp toàn bộ bộ kịch bản N lần")
    ap.add_argument("--workers", type=int, default=0, help="(cpu) số tiến trình, mặc định = số lõi")
    ap.add_argument("--mb", type=int, default=0, help="(memory) MiB cần cấp phát, mặc định tự tính theo ngưỡng")
    ap.add_argument("--percent", type=float, default=0, help="(disk) lấp đầy tới %%, mặc định ngưỡng+5")
    ap.add_argument("--latency-ms", type=float, default=0, help="(slow) độ trễ tiêm vào, mặc định 3000")
    ap.add_argument("--error-rate", type=float, default=None, help="(error) tỉ lệ lỗi 0..1, mặc định 0.5")
    ap.add_argument("--notes", default="", help="ghi chú lưu kèm sự kiện")
    a = ap.parse_args()

    if a.scenario == "list":
        for s in SCENARIOS.values():
            print(f"{s.name:<13} {s.description}\n{'':<13} -> {', '.join(s.expected_alerts)}")
        return
    if a.scenario == "recover":
        recover_all(a)
        return

    defaults = {"service-down": "svc-payments", "slow": "svc-api", "error": "svc-orders"}
    if a.scenario == "all":
        user_target = a.target
        for i in range(a.repeat):
            for j, name in enumerate(DEFAULT_ALL):
                a.target = user_target or defaults.get(name)
                if not a.stop_on_alert:
                    a.stop_on_alert = True  # bộ "all" mặc định khôi phục khi đã phát hiện
                run_scenario(name, a)
                last = i == a.repeat - 1 and j == len(DEFAULT_ALL) - 1
                if not last:
                    print(f"  nghỉ {a.cooldown}s để hệ thống trở lại bình thường ...")
                    time.sleep(a.cooldown)
        print("\nHoàn tất. Tính thời gian phát hiện: python scripts/detection_time.py")
        return

    if a.target is None:
        a.target = defaults.get(a.scenario)
    if a.target and a.target not in SERVICES and a.scenario in defaults:
        sys.exit(f"--target phải là một trong {SERVICES}")
    run_scenario(a.scenario, a)


if __name__ == "__main__":
    main()
