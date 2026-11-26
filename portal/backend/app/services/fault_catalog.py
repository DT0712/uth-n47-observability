"""Danh mục kịch bản lỗi: VM áp dụng, tham số và giới hạn, cảnh báo mong đợi (UC16, FR-P13).

Khớp với faults/obslab-fault (giới hạn tham số kiểm lại trên VM) và tools/fault.py (cảnh báo gốc/mong đợi, nhãn khớp).
Cấu hình đo (BR-07) khớp monitor/prometheus/prometheus.yml, rules/alerts.yml, alertmanager.yml; test kiểm sự khớp này.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.errors import ApiError

VM_MAX_DURATION = 900   # giới hạn của obslab-fault
SAFETY_MARGIN = 60      # VM tự gỡ muộn hơn thời gian giữ ngần này, phòng khi backend chết
SERVICE_HOST = {"nginx": "web", "demo-app": "web", "postgresql": "db"}
SERVICE_ROOT = {"nginx": "NginxDown", "demo-app": "ServiceDown", "postgresql": "PostgresDown"}

# Cấu hình ảnh hưởng thời gian phát hiện (BR-07); "for" theo cảnh báo gốc
LAB_CONFIG = {"scrape_interval_s": 15, "evaluation_interval_s": 15, "group_wait_s": 5}
ALERT_FOR_S = {"HostHighCpu": 60, "HostHighMemory": 60, "HostDiskAlmostFull": 60, "NginxDown": 30, "ServiceDown": 30,
               "PostgresDown": 30, "ServiceHighLatency": 60, "ServiceHighErrorRate": 60, "EndpointDown": 30,
               "EndpointSlow": 60}


@dataclass(frozen=True)
class Param:
    name: str
    type: str                  # integer | enum
    min: int | None = None
    max: int | None = None
    default: Any = None
    choices: tuple[str, ...] = ()


@dataclass(frozen=True)
class Scenario:
    scenario: str
    title: str
    hosts: tuple[str, ...]
    params: tuple[Param, ...]
    root_alert: str | None              # None: tùy service (service-stop)
    expected: tuple[str, ...] = ()


SCENARIOS: dict[str, Scenario] = {s.scenario: s for s in (
    Scenario("cpu", "CPU cao (stress-ng mọi lõi)", ("web", "db"), (), "HostHighCpu"),
    Scenario("memory", "RAM cao", ("web", "db"), (Param("percent", "integer", 50, 97, 95),), "HostHighMemory"),
    Scenario("disk", "Đĩa /mnt/labdisk gần đầy", ("web", "db"), (Param("percent", "integer", 50, 99, 95),),
             "HostDiskAlmostFull"),
    Scenario("service-stop", "Dừng dịch vụ", ("web", "db"),
             (Param("service", "enum", choices=tuple(SERVICE_HOST)),), None),
    Scenario("latency", "Demo app chậm", ("web",), (Param("latency_ms", "integer", 100, 7000, 3000),),
             "ServiceHighLatency", ("EndpointSlow",)),
    Scenario("errors", "Demo app trả lỗi 5xx", ("web",), (Param("error_rate", "integer", 1, 100, 50),),
             "ServiceHighErrorRate"),
)}


@dataclass(frozen=True)
class Plan:
    """Kết quả kiểm tra yêu cầu chạy: đủ để gửi lệnh tới VM và khớp cảnh báo."""
    scenario: str
    host: str
    params: dict[str, Any]
    root_alert: str
    expected: tuple[str, ...]          # gồm cả cảnh báo gốc
    match_labels: dict[str, str]
    vm_duration: int

    def command(self, action: str) -> str:
        if action != "start":
            return f"{self.scenario} {action}"
        return " ".join([self.scenario, "start", f"duration={self.vm_duration}",
                         *(f"{k}={v}" for k, v in self.params.items())])


def _bad(field: str, message: str) -> ApiError:
    return ApiError(422, "validation_error", "Dữ liệu không hợp lệ", [{"field": field, "message": message, "type": "value_error"}])


def plan(scenario: str, host: str, params: dict[str, Any], hold_s: int) -> Plan:
    sc = SCENARIOS.get(scenario)
    if sc is None:
        raise _bad("scenario", f"Không có kịch bản {scenario!r}")
    if host not in sc.hosts:
        raise _bad("host", f"Kịch bản {scenario} chỉ chạy trên {', '.join(sc.hosts)}")
    allowed = {p.name: p for p in sc.params}
    unknown = set(params) - set(allowed)
    if unknown:
        raise _bad("params", f"Kịch bản {scenario} không nhận tham số {sorted(unknown)}")
    clean: dict[str, Any] = {}
    for p in sc.params:
        value = params.get(p.name, p.default)
        if p.type == "integer":
            if isinstance(value, bool) or not isinstance(value, int) or not p.min <= value <= p.max:
                raise _bad(f"params.{p.name}", f"{p.name} phải là số nguyên {p.min}–{p.max}")
        elif value not in p.choices:
            raise _bad(f"params.{p.name}", f"{p.name} phải là một trong {list(p.choices)}")
        clean[p.name] = value
    if scenario == "service-stop":
        service = clean["service"]
        if SERVICE_HOST[service] != host:
            raise _bad("host", f"{service} nằm trên VM {SERVICE_HOST[service]}, không phải {host}")
        root = SERVICE_ROOT[service]
        others = ("EndpointDown",) if service == "postgresql" else ("ServiceDown", "EndpointDown")
        expected = (root, *[x for x in others if x != root])
    else:
        root, expected = sc.root_alert, (sc.root_alert, *sc.expected)
    match = {"host": host, **({"mountpoint": "/mnt/labdisk"} if scenario == "disk" else {})}
    return Plan(scenario, host, clean, root, expected, match, min(VM_MAX_DURATION, hold_s + SAFETY_MARGIN))


def catalog(max_hold_s: int, simulated: bool = False) -> list[dict[str, Any]]:
    out = []
    for sc in SCENARIOS.values():
        out.append({
            "scenario": sc.scenario, "title": sc.title, "hosts": list(sc.hosts),
            "params": [{"name": p.name, "type": p.type, "min": p.min, "max": p.max, "default": p.default,
                        "choices": list(p.choices)} for p in sc.params],
            "root_alert": sc.root_alert or "theo service: " + ", ".join(f"{k}→{v}" for k, v in SERVICE_ROOT.items()),
            "expected_alerts": list(sc.expected), "max_hold_s": max_hold_s,
            "simulated": simulated,  # true: chế độ xem thử, không đụng VM; false: gây lỗi THẬT trên VM
        })
    return out
