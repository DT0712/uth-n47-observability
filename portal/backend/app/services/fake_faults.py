"""Giả lập kịch bản lỗi CHỈ để xem thử giao diện trên Windows (bật cùng PORTAL_FAKE_PROMETHEUS=true).

Không kết nối VM nào. SimulatedFaultSSH trả JSON giống obslab-fault; sau khi "gây lỗi" nó tự gửi cảnh báo gốc vào đúng luồng
webhook của portal sau khoảng thời gian phát hiện đo được ở GĐ3 (docs/05-thu-nghiem/thoi-gian-phat-hien.md, đợt gd3-dot3),
và gửi resolved sau khi "gỡ lỗi". Nhờ vậy cả vòng đời lần chạy (running → recovering → completed, thời gian phát hiện,
báo cáo) chạy được mà không đụng lab.
"""

from __future__ import annotations

import logging
import random
import threading
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from app.core.clock import Clock
from app.services.fault_catalog import SERVICE_ROOT
from app.services.fault_ssh import FaultSSHError

log = logging.getLogger(__name__)

# Thời gian phát hiện TB (giây) theo cảnh báo gốc, đợt gd3-dot3
DETECT_MEAN_S = {"NginxDown": 39.4, "ServiceDown": 47.0, "PostgresDown": 53.0, "HostHighMemory": 75.8,
                 "HostDiskAlmostFull": 79.0, "ServiceHighLatency": 82.8, "ServiceHighErrorRate": 89.6, "HostHighCpu": 113.9}
ROOT = {"cpu": "HostHighCpu", "memory": "HostHighMemory", "disk": "HostDiskAlmostFull", "latency": "ServiceHighLatency",
        "errors": "ServiceHighErrorRate"}
SEVERITY = {"NginxDown": "critical", "ServiceDown": "critical", "PostgresDown": "critical"}
RESOLVE_S = 28.0  # resolved của cảnh báo gốc tới sau khi gỡ lỗi (đo được 27–59 s)


class SimulatedFaultSSH:
    def __init__(self, clock: Clock, deliver: Callable[[dict], None], speed: float = 1.0) -> None:
        self.clock, self.deliver, self.speed = clock, deliver, speed
        self.active: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def _alert(self, run: dict, status: str) -> dict:
        labels = {"alertname": run["root"], "instance": run["host"], "host": run["host"],
                  "severity": SEVERITY.get(run["root"], "warning"), "lab": "simulated"}
        if run.get("service"):
            labels["service"] = run["service"]
        if run["scenario"] == "disk":
            labels["mountpoint"] = "/mnt/labdisk"
        return {"status": status, "labels": labels, "startsAt": run["starts_at"],
                "endsAt": "0001-01-01T00:00:00Z" if status == "firing" else self.clock.now().isoformat(),
                "annotations": {"summary": f"[giả lập] {run['root']} trên {run['host']}"}, "fingerprint": run["fingerprint"]}

    def _send(self, run: dict, status: str) -> None:
        try:
            if status == "firing":
                run["starts_at"] = (self.clock.now() - timedelta(seconds=5)).isoformat().replace("+00:00", "Z")
            self.deliver({"version": "4", "status": status, "receiver": "portal", "groupKey": "simulated",
                          "alerts": [self._alert(run, status)]})
        except Exception:
            log.exception("Không gửi được cảnh báo giả lập")

    def _later(self, seconds: float, fn: Callable[[], None]) -> None:
        t = threading.Timer(max(0.0, seconds / self.speed), fn)
        t.daemon = True
        t.start()

    def call(self, host: str, command: str) -> dict[str, Any]:
        ts = self.clock.now().timestamp()
        words = command.split()
        with self._lock:
            if words == ["status"]:
                st = self.active.get(host)
                return {"ok": True, "action": "status", "host": host, "ts": ts, "active": bool(st),
                        **({"scenario": st["scenario"]} if st else {})}
            scenario, action = words[0], words[1]
            if action == "start":
                if host in self.active:
                    raise FaultSSHError("đang có kịch bản khác chạy trên VM này (xem status)", 3)
                params = dict(w.split("=", 1) for w in words[2:])
                service = params.get("service")
                root = SERVICE_ROOT[service] if scenario == "service-stop" else ROOT[scenario]
                run = {"scenario": scenario, "host": host, "service": service, "root": root,
                       "fingerprint": f"sim-{host}-{root}-{int(ts)}", "starts_at": None, "fired": False}
                self.active[host] = run
                delay = DETECT_MEAN_S[root] + random.uniform(-4, 4) - 5  # −5: portal nhận sau group_wait

                def fire() -> None:
                    with self._lock:
                        alive = self.active.get(host) is run
                    if alive:
                        run["fired"] = True
                        self._send(run, "firing")

                self._later(delay, fire)
                return {"ok": True, "action": "start", "host": host, "ts": ts, "active": True, "scenario": scenario,
                        "params": " ".join(words[2:]), "started_ts": ts, "until_ts": ts + float(params.get("duration", 300))}
            run = self.active.pop(host, None)
        if run and run["fired"]:
            self._later(RESOLVE_S + random.uniform(0, 4), lambda: self._send(run, "resolved"))
        return {"ok": True, "action": "stop", "host": host, "ts": ts, "active": False}


class SimulatedLabChecks:
    """Điều kiện đo luôn đạt (không có Prometheus thật để kiểm)."""

    def eval_lag(self) -> float | None:
        return 0.002

    def clock_offset(self, host: str) -> float | None:
        return 0.0

    def clock_problem(self, host: str) -> str | None:
        return None

    def active_alerts(self) -> list[str]:
        return []
