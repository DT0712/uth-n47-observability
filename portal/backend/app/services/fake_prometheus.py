"""Prometheus GIẢ sinh số dao động giống lab, CHỈ để xem thử giao diện khi chạy backend trên Windows.

  $env:PORTAL_FAKE_PROMETHEUS = "true"

Không kết nối mạng. Hiểu đúng các biểu thức trong services/monitoring.py (bộ chọn nhãn =, =~; `time() - X`;
`avg_over_time(X[..])`; ngưỡng `{__name__=~"lab:threshold:.*"}`); biểu thức khác trả rỗng.
Giá trị là đi bộ ngẫu nhiên kéo về mức trung bình (class Walk), cố định theo thời gian: biểu đồ và số hiện tại khớp nhau,
làm mới thì thay đổi dần như thật. Mức dao động lấy gần với baseline đo ở GĐ3 (CPU vài %, RAM 23–40 %, p95 ~ 47 ms).
"""

from __future__ import annotations

import hashlib
import math
import re
import time
from collections.abc import Callable
from typing import Any

SEL = re.compile(r"(?P<name>[a-zA-Z_:][\w:]*)?\{(?P<body>[^}]*)\}|(?P<bare>[a-zA-Z_:][\w:]*)")
MATCHER = re.compile(r'(\w+)\s*(=~|=)\s*"((?:[^"\\]|\\.)*)"')
Gen = Callable[[float], float]


def _noise(key: str, n: int) -> float:
    """Số giả ngẫu nhiên −1..1, cố định cho mỗi (chuỗi, bước n)."""
    h = hashlib.blake2b(f"{key}:{n}".encode(), digest_size=4).digest()
    return int.from_bytes(h, "big") / 0xFFFFFFFF * 2 - 1


STEP = 15.0                                   # một bước của chuỗi = một chu kỳ scrape
ANCHOR = int((time.time() - 16 * 86400) // STEP)  # chuỗi bắt đầu 16 ngày trước (> retention 15 ngày)


def walk(key: str, mean: float, std: float, theta: float = 0.02, spike: float = 0.0, lo: float = 0.0,
         hi: float = math.inf) -> "Walk":
    """Walk theo độ lệch chuẩn mong muốn: OU có std ≈ sigma·0,577/√(2·theta) (nhiễu đều −1..1 có std 0,577)."""
    return Walk(key, mean, std * math.sqrt(2 * theta) / 0.577, theta, spike, lo=lo, hi=hi)


class Walk:
    """Đi bộ ngẫu nhiên có kéo về mức trung bình (Ornstein–Uhlenbeck rời rạc), thỉnh thoảng có đỉnh nhỏ tắt dần.

        x[n+1] = x[n] + theta·(mean − x[n]) + sigma·nhiễu(n) + đỉnh(n)

    Giá trị thay đổi từ từ, không nhảy độc lập mỗi điểm. Tính tuần tự một lần rồi nhớ lại (mỗi chuỗi ~92.000 bước cho
    16 ngày), nên cùng một thời điểm luôn ra cùng giá trị: biểu đồ và số hiện tại khớp nhau, làm mới không đổi quá khứ.
    """

    def __init__(self, key: str, mean: float, sigma: float, theta: float = 0.02, spike: float = 0.0,
                 spike_p: float = 0.004, lo: float = 0.0, hi: float = math.inf) -> None:
        self.key, self.mean, self.sigma, self.theta = key, mean, sigma, theta
        self.spike, self.spike_p, self.lo, self.hi = spike, spike_p, lo, hi
        self.values: list[float] = [mean]

    def _extend(self, n: int) -> None:
        x = self.values[-1]
        for i in range(len(self.values), n + 1):
            x = x + self.theta * (self.mean - x) + self.sigma * _noise(self.key, i)
            self.values.append(x)

    def _at(self, n: int) -> float:
        i = n - ANCHOR
        if i < 0:
            return self.mean
        if i >= len(self.values):
            self._extend(i)
        spike = 0.0
        if self.spike:  # đỉnh: tổng các đỉnh bắt đầu trong 8 bước gần nhất, tắt dần
            for k in range(8):
                j = n - k
                if (_noise(self.key + "/s", j) + 1) / 2 < self.spike_p:
                    spike += self.spike * (0.6 + 0.4 * (_noise(self.key + "/a", j) + 1) / 2) * 0.75 ** k
        return min(self.hi, max(self.lo, self.values[i] + spike))

    def __call__(self, t: float) -> float:
        """Nội suy tuyến tính giữa hai bước để đường mượt ở mọi bước truy vấn."""
        n = int(t // STEP)
        frac = (t - n * STEP) / STEP
        a, b = self._at(n), self._at(n + 1) if frac else 0.0
        return a + (b - a) * frac if frac else a


def const(v: float) -> Gen:
    return lambda t: v


BOOT = time.time() - 3 * 86400 - 4 * 3600  # VM "đã chạy" 3 ngày 4 giờ
THRESHOLDS = [("host_cpu_usage_percent", 85), ("host_memory_usage_percent", 90), ("filesystem_usage_percent", 90),
              ("endpoint_probe_duration_seconds", 0.25), ("service_latency_p95_seconds", 0.25), ("service_error_ratio", 0.05),
              ("service_min_request_rate_rps", 0.6), ("postgres_connections_usage_percent", 80)]  # ngưỡng v1 (thresholds.yml)


def _series() -> list[tuple[str, dict[str, str], Gen]]:
    rows: list[tuple[str, dict[str, str], Gen]] = []
    for host, cpu, mem, disk in (("monitor", 2.0, 30.0, 26.0), ("web", 3.0, 37.5, 21.3), ("db", 2.0, 23.5, 21.9)):
        rows += [
            ("up", {"job": "node", "instance": host, "host": host}, const(1)),
            ("lab:host_cpu_usage:percent", {"instance": host, "host": host}, walk(f"cpu{host}", cpu, cpu * 0.25, 0.03, spike=cpu * 2.5, lo=0.2, hi=100)),
            ("lab:host_memory_usage:percent", {"instance": host, "host": host}, walk(f"mem{host}", mem, 1.2, 0.005, lo=0, hi=100)),
            ("lab:filesystem_usage:percent", {"instance": host, "host": host, "mountpoint": "/"}, const(disk)),
            ("lab:filesystem_usage:percent", {"instance": host, "host": host, "mountpoint": "/mnt/labdisk"}, const(7.36)),
            ("lab:host_network_receive:bytes_per_second", {"instance": host, "host": host}, walk(f"rx{host}", 1600, 350, 0.03, spike=4000)),
            ("lab:host_network_transmit:bytes_per_second", {"instance": host, "host": host}, walk(f"tx{host}", 4000, 800, 0.03, spike=9000)),
            ("node_boot_time_seconds", {"job": "node", "instance": host, "host": host}, const(BOOT)),
        ]
    rows += [
        ("up", {"job": "nginx", "service": "nginx", "instance": "web", "host": "web"}, const(1)),
        ("up", {"job": "demo-app", "service": "demo-app", "instance": "web", "host": "web"}, const(1)),
        ("up", {"job": "postgres", "service": "postgresql", "instance": "db", "host": "db"}, const(1)),
        ("probe_success", {"job": "blackbox-tcp", "instance": "web:80"}, const(1)),
        ("probe_success", {"job": "blackbox-http", "instance": "http://web/health"}, const(1)),
        ("probe_success", {"job": "blackbox-tcp", "instance": "db:5432"}, const(1)),
        ("probe_duration_seconds", {"job": "blackbox-http", "instance": "http://web/health"}, walk("probe", 0.004, 0.0008, 0.05, spike=0.012, lo=0.001)),
        ("probe_duration_seconds", {"job": "blackbox-tcp", "instance": "web:80"}, walk("probe80", 0.002, 0.0004, 0.05, lo=0.0005)),
        ("probe_duration_seconds", {"job": "blackbox-tcp", "instance": "db:5432"}, walk("probe5432", 0.002, 0.0004, 0.05, lo=0.0005)),
        ("lab:service_request_rate:rps", {"service": "demo-app", "instance": "web", "host": "web"}, walk("rps", 1.5, 0.18, 0.02, lo=0)),
        ("lab:service_latency_p95:seconds", {"service": "demo-app", "instance": "web", "host": "web"}, walk("p95", 0.047, 0.004, 0.02, spike=0.03, lo=0.01)),
        ("lab:service_error_ratio:ratio", {"service": "demo-app", "instance": "web", "host": "web"}, const(0.0)),
        ("lab:nginx_request_rate:rps", {"service": "nginx", "instance": "web", "host": "web"}, walk("nginxrps", 6.0, 0.6, 0.02, lo=0)),
        ("nginx_connections_active", {"job": "nginx", "service": "nginx", "instance": "web", "host": "web"}, walk("conn", 2, 0.6, 0.05, lo=1)),
        ("lab:postgres_connections_usage:percent", {"service": "postgresql", "instance": "db", "host": "db"}, walk("pgconn", 2.0, 0.3, 0.02, lo=1)),
        ("lab:postgres_transactions:tps", {"service": "postgresql", "instance": "db", "host": "db"}, walk("tps", 3.0, 0.6, 0.03, lo=0)),
    ]
    rows += [(f"lab:threshold:{name}", {"threshold_status": "baselined", "basis": "baseline 2026-11-27 24h"}, const(v))
             for name, v in THRESHOLDS]
    return rows


class SyntheticPrometheus:
    """Cùng giao diện với PrometheusClient (query, query_range, ready, rule_last_evaluation)."""

    def __init__(self) -> None:
        self.data = _series()
        self.requests = 0

    def _select(self, expr: str, t: float) -> list[tuple[dict[str, str], float]]:
        inner, offset_now = expr, False
        if inner.startswith("time() - "):
            inner, offset_now = inner[len("time() - "):], True
        avg_window = None
        if inner.startswith("avg_over_time(") and "[" in inner:
            avg_window = inner[len("avg_over_time("):inner.rindex("[")]
            inner = avg_window
        m = SEL.match(inner)
        if not m:
            return []
        name = m.group("name") or m.group("bare")
        matchers = MATCHER.findall(m.group("body") or "")
        out = []
        for metric, labels, gen in self.data:
            full = {"__name__": metric, **labels}
            if name and metric != name:
                continue
            ok = True
            for key, op, raw in matchers:
                want = raw.replace('\\"', '"').replace("\\\\", "\\")
                have = full.get(key, "")
                ok = ok and (have == want if op == "=" else re.fullmatch(want, have) is not None)
            if ok:
                value = gen(t)
                out.append(({**labels} if name else full, t - value if offset_now else value))
        return out

    def query(self, expr: str, cache: bool = True) -> list[dict[str, Any]]:
        self.requests += 1
        t = time.time()
        return [{"metric": lab, "value": [t, repr(v)]} for lab, v in self._select(expr, t)]

    def query_range(self, expr: str, start: float, end: float, step: float) -> list[dict[str, Any]]:
        self.requests += 1
        start, end = math.floor(start / step) * step, math.ceil(end / step) * step
        times = [start + i * step for i in range(int((end - start) // step) + 1)]
        series: dict[str, dict[str, Any]] = {}
        for t in times:
            for lab, v in self._select(expr, t):
                key = repr(sorted(lab.items()))
                series.setdefault(key, {"metric": lab, "values": []})["values"].append([t, repr(v)])
        return list(series.values())

    def ready(self) -> bool:
        return True

    def rule_last_evaluation(self, rule: str) -> float | None:
        return time.time()
