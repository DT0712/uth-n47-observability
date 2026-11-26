"""Kiểm điều kiện đo trước khi gây lỗi, giống tools/fault.py (dirty_reasons):

- Prometheus đánh giá luật trễ ≤ 1 s (SC-04: sau khi đồng hồ nhảy, cảnh báo tới muộn và group_wait mất tác dụng)
- Đồng hồ VM có đủ dữ liệu 2 phút qua và lệch monitor ≤ 0,1 s (chrony ổn định)
- Không có cảnh báo nào đang pending/firing (kết quả đo sẽ lẫn)

Test thay cả lớp này bằng bản giả (tests/fakes.py: FakeLabChecks).
"""

from __future__ import annotations

from typing import Protocol

from app.services.prometheus import PrometheusAPI, PrometheusError, as_float

EVAL_LAG_LIMIT_S = 1.0
CLOCK_LIMIT_S = 0.1
THRESHOLD_RULE = "lab:threshold:host_cpu_usage_percent"
CLOCK_DIFF = 'node_time_seconds{{job="node",instance="{0}"}} - timestamp(node_time_seconds{{job="node",instance="{0}"}})'


class LabChecksAPI(Protocol):
    def eval_lag(self) -> float | None: ...
    def clock_offset(self, host: str) -> float | None: ...
    def clock_problem(self, host: str) -> str | None: ...
    def active_alerts(self) -> list[str]: ...


class LabChecks:
    def __init__(self, prom: PrometheusAPI) -> None:
        self.prom = prom

    def eval_lag(self) -> float | None:
        """lastEvaluation của nhóm luật trừ timestamp mẫu mới nhất mà nhóm đó ghi (bình thường ≈ 0)."""
        try:
            for _ in range(3):
                before = self.prom.rule_last_evaluation(THRESHOLD_RULE)
                rows = self.prom.query(f"{THRESHOLD_RULE}[2m]", cache=False)
                if before is None or not rows:
                    return None
                if self.prom.rule_last_evaluation(THRESHOLD_RULE) == before:  # không có lần đánh giá chen giữa
                    return round(before - float(rows[0]["values"][-1][0]), 3)
        except PrometheusError:
            return None
        return None

    def clock_offset(self, host: str) -> float | None:
        """Đồng hồ VM − đồng hồ monitor (giây), trung vị 2 phút."""
        try:
            rows = self.prom.query(f"quantile_over_time(0.5, ({CLOCK_DIFF.format(host)})[2m:15s])", cache=False)
        except PrometheusError:
            return None
        v = as_float(rows[0]["value"][1]) if rows else None
        return round(v, 3) if v is not None else None

    def clock_problem(self, host: str) -> str | None:
        try:
            n = self.prom.query(f'count_over_time(node_time_seconds{{job="node",instance="{host}"}}[2m])', cache=False)
            if not n or (as_float(n[0]["value"][1]) or 0) < 6:
                return f"thiếu dữ liệu {host} trong 2 phút qua (VM hoặc Windows vừa ngủ/khởi động?)"
            rows = self.prom.query(f"max_over_time(abs({CLOCK_DIFF.format(host)})[2m:15s])", cache=False)
        except PrometheusError as e:
            return f"không kiểm được đồng hồ {host}: {e}"
        worst = max((as_float(r["value"][1]) or 0 for r in rows), default=0)
        if worst > CLOCK_LIMIT_S:
            return f"đồng hồ {host} lệch monitor tới {worst:.2f}s trong 2 phút qua (chờ chrony ổn định)"
        return None

    def active_alerts(self) -> list[str]:
        try:
            rows = self.prom.query('ALERTS{alertname!="LabTestAlert"}', cache=False)
        except PrometheusError as e:
            return [f"không đọc được ALERTS: {e}"]
        return [f"{r['metric']['alertname']}({r['metric'].get('instance', '')}, {r['metric'].get('alertstate', '')})"
                for r in rows]
