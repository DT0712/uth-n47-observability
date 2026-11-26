"""Prometheus giả cho test: đủ hiểu các biểu thức trong danh mục services/monitoring.py.

Dữ liệu là bảng (tên metric, nhãn) -> giá trị. Fake lọc theo bộ chọn nhãn (=, =~), hỗ trợ `time() - X`,
`avg_over_time(X[..])` và truy vấn ngưỡng `{__name__=~"lab:threshold:.*"}`. Ghi lại mọi truy vấn để test kiểm
portal không gửi biểu thức lạ. Đặt `fail = True` để giả lập Prometheus chết.
"""

from __future__ import annotations

import re
from typing import Any

from app.services.prometheus import PrometheusError

SEL = re.compile(r"(?P<name>[a-zA-Z_:][\w:]*)?\{(?P<body>[^}]*)\}|(?P<bare>[a-zA-Z_:][\w:]*)")
MATCHER = re.compile(r'(\w+)\s*(=~|=)\s*"((?:[^"\\]|\\.)*)"')

LAB = [
    # host
    ("up", {"job": "node", "instance": "monitor"}, 1), ("up", {"job": "node", "instance": "web"}, 1),
    ("up", {"job": "node", "instance": "db"}, 1),
    ("lab:host_cpu_usage:percent", {"instance": "monitor"}, 1.6), ("lab:host_cpu_usage:percent", {"instance": "web"}, 2.3),
    ("lab:host_cpu_usage:percent", {"instance": "db"}, 1.7),
    ("lab:host_memory_usage:percent", {"instance": "monitor"}, 30.1), ("lab:host_memory_usage:percent", {"instance": "web"}, 37.5),
    ("lab:host_memory_usage:percent", {"instance": "db"}, 23.3),
    ("lab:filesystem_usage:percent", {"instance": "web", "mountpoint": "/"}, 21.3),
    ("lab:filesystem_usage:percent", {"instance": "web", "mountpoint": "/mnt/labdisk"}, 7.4),
    ("lab:filesystem_usage:percent", {"instance": "db", "mountpoint": "/"}, 21.9),
    ("lab:filesystem_usage:percent", {"instance": "monitor", "mountpoint": "/"}, 26.0),
    ("lab:host_network_receive:bytes_per_second", {"instance": "web"}, 1580.0),
    ("lab:host_network_transmit:bytes_per_second", {"instance": "web"}, 4100.0),
    ("node_boot_time_seconds", {"job": "node", "instance": "web"}, 1795670000.0),
    # service
    ("up", {"job": "nginx", "service": "nginx", "instance": "web"}, 1),
    ("up", {"job": "demo-app", "service": "demo-app", "instance": "web"}, 1),
    ("up", {"job": "postgres", "service": "postgresql", "instance": "db"}, 1),
    ("probe_success", {"instance": "web:80"}, 1), ("probe_success", {"instance": "http://web/health"}, 1),
    ("probe_success", {"instance": "db:5432"}, 1),
    ("probe_duration_seconds", {"job": "blackbox-http", "instance": "http://web/health"}, 0.004),
    ("lab:service_request_rate:rps", {"service": "demo-app", "instance": "web"}, 1.47),
    ("lab:service_latency_p95:seconds", {"service": "demo-app", "instance": "web"}, 0.047),
    ("lab:service_error_ratio:ratio", {"service": "demo-app", "instance": "web"}, 0.0),
    ("lab:nginx_request_rate:rps", {"service": "nginx", "instance": "web"}, 6.2),
    ("lab:postgres_connections_usage:percent", {"service": "postgresql", "instance": "db"}, 2.0),
    # ngưỡng
    ("lab:threshold:host_cpu_usage_percent", {"threshold_status": "provisional", "basis": "chua do baseline"}, 85),
    ("lab:threshold:host_memory_usage_percent", {"threshold_status": "provisional", "basis": "chua do baseline"}, 90),
    ("lab:threshold:filesystem_usage_percent", {"threshold_status": "provisional", "basis": "chua do baseline"}, 90),
    ("lab:threshold:service_latency_p95_seconds", {"threshold_status": "provisional", "basis": "chua do baseline"}, 1),
    ("lab:threshold:endpoint_probe_duration_seconds", {"threshold_status": "provisional", "basis": "chua do baseline"}, 2),
]


class FakePrometheus:
    def __init__(self, now: float = 1795676400.0) -> None:
        self.data: list[tuple[str, dict[str, str], float]] = list(LAB)
        self.now = now
        self.fail = False
        self.calls: list[tuple[str, str]] = []
        self.is_ready = True

    def set(self, name: str, labels: dict[str, str], value: float) -> None:
        self.data = [d for d in self.data if not (d[0] == name and d[1] == labels)] + [(name, labels, value)]

    # ---------------------------------------------------------- đánh giá biểu thức đơn giản
    def _select(self, expr: str) -> list[tuple[dict[str, str], float]]:
        inner = expr
        if inner.startswith("time() - "):
            inner = inner[len("time() - "):]
        elif inner.startswith("avg_over_time("):
            inner = inner[len("avg_over_time("):inner.rindex("[")]
        match = SEL.search(inner)
        assert match, f"Biểu thức lạ: {expr}"
        name = match.group("name") or match.group("bare")
        matchers = MATCHER.findall(match.group("body") or "")
        assert match.start() == 0, f"Biểu thức lạ: {expr}"
        out = []
        for metric, labels, value in self.data:
            full = {"__name__": metric, **labels}
            if name and metric != name:
                continue
            ok = True
            for key, op, raw in matchers:
                want = raw.replace('\\"', '"').replace("\\\\", "\\")
                have = full.get(key, "")
                ok &= have == want if op == "=" else re.fullmatch(want, have) is not None
            if ok:
                out.append(({"__name__": metric, **labels} if not name else dict(labels), value))
        if expr.startswith("time() - "):
            out = [(lab, self.now - v) for lab, v in out]
        return out

    def _check(self, kind: str, expr: str) -> None:
        self.calls.append((kind, expr))
        if self.fail:
            raise PrometheusError("Prometheus giả đang tắt")

    def query(self, expr: str) -> list[dict[str, Any]]:
        self._check("query", expr)
        return [{"metric": lab, "value": [self.now, str(v)]} for lab, v in self._select(expr)]

    def query_range(self, expr: str, start: float, end: float, step: float) -> list[dict[str, Any]]:
        self._check("range", expr)
        n = int((end - start) // step) + 1
        return [{"metric": lab, "values": [[start + i * step, str(v)] for i in range(n)]} for lab, v in self._select(expr)]

    def ready(self) -> bool:
        self.calls.append(("ready", ""))
        return self.is_ready and not self.fail
