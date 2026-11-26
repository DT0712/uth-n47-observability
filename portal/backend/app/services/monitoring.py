"""Danh mục truy vấn dựng sẵn và dữ liệu cho tổng quan, metric, ngưỡng (UC02, UC03, UC11; FR-P03, FR-P04, FR-P12).

Mọi biểu thức PromQL của portal nằm ở file này và dựa trên recording rule của lab
(monitor/prometheus/rules/recording.yml). Người dùng chỉ chọn đối tượng và khoảng thời gian.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.db import models as m
from app.services.inventory import grafana_url
from app.services.prometheus import PrometheusAPI, PrometheusError, as_float, selector

RANGES = {"15m": 900, "1h": 3600, "6h": 6 * 3600, "24h": 24 * 3600, "7d": 7 * 24 * 3600}
MAX_SPAN_S = 15 * 24 * 3600  # = retention
MAX_POINTS = 1000

# Chỉ số của host: tên -> (recording rule, đơn vị, tên ngưỡng, nhãn phụ)
HOST_METRICS: dict[str, tuple[str, str, str | None, dict[str, str]]] = {
    "cpu": ("lab:host_cpu_usage:percent", "%", "host_cpu_usage_percent", {}),
    "memory": ("lab:host_memory_usage:percent", "%", "host_memory_usage_percent", {}),
    "disk": ("lab:filesystem_usage:percent", "%", "filesystem_usage_percent", {}),
    "network_rx": ("lab:host_network_receive:bytes_per_second", "B/s", None, {}),
    "network_tx": ("lab:host_network_transmit:bytes_per_second", "B/s", None, {}),
}
# Chỉ số theo loại service (lọc bằng nhãn service=...): tên -> (biểu thức, đơn vị, tên ngưỡng)
SERVICE_KIND_METRICS: dict[str, dict[str, tuple[str, str, str | None]]] = {
    "app": {"request_rate": ("lab:service_request_rate:rps", "rps", None),
            "latency_p95": ("lab:service_latency_p95:seconds", "s", "service_latency_p95_seconds"),
            "error_ratio": ("lab:service_error_ratio:ratio", "ratio", "service_error_ratio")},
    "web": {"request_rate": ("lab:nginx_request_rate:rps", "rps", None),
            "connections_active": ("nginx_connections_active", "count", None)},
    "database": {"connections_usage": ("lab:postgres_connections_usage:percent", "%", "postgres_connections_usage_percent"),
                 "transactions": ("lab:postgres_transactions:tps", "rps", None)},
}


def unavailable(e: Exception) -> ApiError:
    return ApiError(503, "prometheus_unavailable", f"Không đọc được Prometheus: {e}")


# ------------------------------------------------------------------ khoảng thời gian
@dataclass
class Window:
    start: float
    end: float
    step: float


def window(now: datetime, range_: str | None, start: datetime | None, end: datetime | None) -> Window:
    if (start is None) != (end is None):
        raise ApiError(422, "validation_error", "Dữ liệu không hợp lệ",
                       [{"field": "start/end", "message": "Cần cả start và end", "type": "missing"}])
    if start is not None and end is not None:
        s, e = start.timestamp(), end.timestamp()
        if e <= s:
            raise ApiError(422, "validation_error", "Dữ liệu không hợp lệ",
                           [{"field": "end", "message": "end phải sau start", "type": "value_error"}])
        if e - s > MAX_SPAN_S:
            raise ApiError(422, "validation_error", "Dữ liệu không hợp lệ",
                           [{"field": "start", "message": "Khoảng tối đa 15 ngày (retention)", "type": "value_error"}])
    else:
        e = now.timestamp()
        s = e - RANGES[range_ or "1h"]
    return Window(s, e, step_for(e - s))


def step_for(span: float) -> float:
    """Bước là bội của 15 s (chu kỳ scrape) sao cho mỗi series ≤ 1.000 điểm."""
    return max(15.0, math.ceil(span / MAX_POINTS / 15) * 15.0)


def iso(ts: float) -> datetime:
    return datetime.fromtimestamp(ts, tz=timezone.utc)


# ------------------------------------------------------------------ ngưỡng
def thresholds(prom: PrometheusAPI) -> list[dict[str, Any]]:
    rows = []
    for r in prom.query('{__name__=~"lab:threshold:.*"}'):
        metric = r["metric"]
        rows.append({"name": metric["__name__"].split(":", 2)[2], "value": as_float(r["value"][1]),
                     "status": metric.get("threshold_status", "provisional"), "basis": metric.get("basis", "")})
    return sorted(rows, key=lambda x: x["name"])


def threshold_map(prom: PrometheusAPI) -> dict[str, float | None]:
    try:
        return {t["name"]: t["value"] for t in thresholds(prom)}
    except PrometheusError:
        return {}


# ------------------------------------------------------------------ chuỗi thời gian
def _points(values: list) -> list[list]:
    return [[float(t), as_float(v)] for t, v in values]


def _series(prom: PrometheusAPI, w: Window, name: str, expr: str, unit: str, label_key: str | None,
            threshold: float | None) -> list[dict]:
    out = []
    for r in prom.query_range(expr, w.start, w.end, w.step):
        metric = r["metric"]
        label = metric.get(label_key, "") if label_key else ""
        if label_key == "mountpoint":
            label = f"mountpoint={label}"
        out.append({"metric": name, "label": label, "unit": unit, "threshold": threshold, "points": _points(r["values"])})
    return sorted(out, key=lambda s: s["label"])


def series_set(w: Window, series: list[dict]) -> dict:
    return {"start": iso(w.start), "end": iso(w.end), "step_s": w.step, "series": series}


def host_metrics(prom: PrometheusAPI, host: m.Host, w: Window, names: list[str]) -> dict:
    thr = threshold_map(prom)
    series = []
    for name in names:
        rule, unit, thr_name, extra = HOST_METRICS[name]
        expr = selector(rule, {"instance": host.prom_instance, **extra})
        series += _series(prom, w, name, expr, unit, "mountpoint" if name == "disk" else None, thr.get(thr_name or ""))
    return series_set(w, series)


def service_metrics(prom: PrometheusAPI, service: m.Service, w: Window) -> dict:
    thr = threshold_map(prom)
    series = _series(prom, w, "up", selector("up", service.prom_labels), "0/1", None, None)
    if service.probe_instance:
        series += _series(prom, w, "probe_success", selector("probe_success", {"instance": service.probe_instance}),
                          "0/1", None, None)
        series += _series(prom, w, "probe_duration", selector("probe_duration_seconds", {"instance": service.probe_instance}),
                          "s", None, thr.get("endpoint_probe_duration_seconds"))
    svc_label = service.prom_labels.get("service", service.name)
    for name, (expr, unit, thr_name) in SERVICE_KIND_METRICS.get(service.kind, {}).items():
        series += _series(prom, w, name, selector(expr, {"service": svc_label}), unit, None, thr.get(thr_name or ""))
    return series_set(w, series)


# ------------------------------------------------------------------ tổng quan
def _by_instance(prom: PrometheusAPI, metric: str, instances: list[str], extra: dict[str, str] | None = None,
                 wrap: str = "{}") -> dict[str, float | None]:
    expr = wrap.format(selector(metric, extra, {"instance": instances}))
    return {r["metric"].get("instance", ""): as_float(r["value"][1]) for r in prom.query(expr)}


def _instant_one(prom: PrometheusAPI, expr: str) -> float | None:
    rows = prom.query(expr)
    return as_float(rows[0]["value"][1]) if rows else None


def _selected(db: Session, host: str | None, service: str | None) -> list[m.Host]:
    hosts = list(db.scalars(select(m.Host).where(m.Host.enabled).order_by(m.Host.name)))
    if host:
        hosts = [h for h in hosts if h.name == host]
    if service:
        hosts = [h for h in hosts if any(s.name == service for s in h.services)]
    return hosts


def _services(h: m.Host, service: str | None) -> list[m.Service]:
    return [s for s in h.services if s.enabled and (service is None or s.name == service)]


def overview(db: Session, prom: PrometheusAPI, now: datetime, grafana_base: str, host: str | None = None,
             service: str | None = None) -> dict:
    from app.services.incidents import summaries

    hosts = _selected(db, host, service)
    names = [h.prom_instance for h in hosts]
    probes = [s.probe_instance for h in hosts for s in _services(h, service) if s.probe_instance]
    metrics_ok, values, service_up, probe_ok = True, {}, {}, {}
    try:
        if names:
            values = {
                "up": _by_instance(prom, "up", names, {"job": "node"}),
                "cpu": _by_instance(prom, "lab:host_cpu_usage:percent", names),
                "memory": _by_instance(prom, "lab:host_memory_usage:percent", names),
                "disk": _by_instance(prom, "lab:filesystem_usage:percent", names, {"mountpoint": "/"}),
                "rx": _by_instance(prom, "lab:host_network_receive:bytes_per_second", names),
                "tx": _by_instance(prom, "lab:host_network_transmit:bytes_per_second", names),
                "uptime": _by_instance(prom, "node_boot_time_seconds", names, {"job": "node"}, "time() - {}"),
            }
        for h in hosts:
            for s in _services(h, service):
                service_up[s.id] = _instant_one(prom, selector("up", s.prom_labels))
        if probes:
            probe_ok = _by_instance(prom, "probe_success", probes)
    except PrometheusError:
        metrics_ok, values, service_up, probe_ok = False, {}, {}, {}

    open_q = select(m.Incident).where(m.Incident.status != "closed")
    open_rows = list(db.scalars(open_q.order_by(m.Incident.opened_at.desc(), m.Incident.id.desc())))
    if host:
        open_rows = [i for i in open_rows if i.host == host]
    if service:
        open_rows = [i for i in open_rows if i.service == service]

    def flag(v: float | None) -> bool | None:
        return None if v is None else v >= 1

    out_hosts = []
    for h in hosts:
        inst = h.prom_instance
        get = lambda key: values.get(key, {}).get(inst)  # noqa: E731
        out_hosts.append({
            "id": h.id, "name": h.name, "up": flag(get("up")), "cpu_percent": get("cpu"), "memory_percent": get("memory"),
            "disk_percent": get("disk"), "network_rx_bps": get("rx"), "network_tx_bps": get("tx"), "uptime_s": get("uptime"),
            "open_incidents": sum(1 for i in open_rows if i.host == h.name),
            "grafana_url": grafana_url(grafana_base, h.grafana_dashboard_uid, inst),
            "services": [{"id": s.id, "name": s.name, "up": flag(service_up.get(s.id)),
                          "probe_ok": flag(probe_ok.get(s.probe_instance)) if s.probe_instance else None,
                          "open_incidents": sum(1 for i in open_rows if i.host == h.name and i.service == s.name)}
                         for s in _services(h, service)],
        })

    since = now - timedelta(hours=24)
    mean = db.scalar(select(func.avg(m.FaultRun.root_detection_s)).where(
        m.FaultRun.status == "completed", m.FaultRun.valid, m.FaultRun.root_detection_s.is_not(None),
        m.FaultRun.injected_at >= since))
    return {
        "generated_at": now, "metrics_available": metrics_ok, "hosts": out_hosts,
        "open_incidents": {"total": len(open_rows),
                           "critical": sum(1 for i in open_rows if i.severity == "critical"),
                           "warning": sum(1 for i in open_rows if i.severity == "warning"),
                           "firing": sum(1 for i in open_rows if i.firing)},
        "latest_incidents": summaries(db, open_rows[:10]),
        "faults_running": db.scalar(select(func.count()).select_from(m.FaultRun).where(
            m.FaultRun.status.in_(m.FAULT_RUN_ACTIVE))) or 0,
        "detection_mean_s": round(mean, 1) if mean is not None else None,
    }


def overview_series(db: Session, prom: PrometheusAPI, now: datetime, range_: str, host: str | None = None,
                    service: str | None = None) -> dict:
    w = window(now, range_, None, None)
    hosts = _selected(db, host, service)
    names = [h.prom_instance for h in hosts]
    svcs = [s for h in hosts for s in _services(h, service)]
    app_services = [s.prom_labels.get("service", s.name) for s in svcs if s.kind == "app"]
    probes = [s.probe_instance for s in svcs if s.probe_instance and s.probe_instance.startswith("http")]
    empty = series_set(w, [])
    try:
        thr = threshold_map(prom)
        cpu = series_set(w, _series(prom, w, "cpu", selector("lab:host_cpu_usage:percent", None, {"instance": names}), "%",
                                    "instance", thr.get("host_cpu_usage_percent"))) if names else empty
        memory = series_set(w, _series(prom, w, "memory", selector("lab:host_memory_usage:percent", None,
                                                                   {"instance": names}), "%", "instance",
                                       thr.get("host_memory_usage_percent"))) if names else empty
        requests = series_set(w, _series(prom, w, "request_rate", selector("lab:service_request_rate:rps", None,
                                                                           {"service": app_services}), "rps", "service",
                                         None)) if app_services else empty
        lat = []
        if app_services:
            lat += _series(prom, w, "latency_p95", selector("lab:service_latency_p95:seconds", None, {"service": app_services}),
                           "s", "service", thr.get("service_latency_p95_seconds"))
        if probes:
            lat += _series(prom, w, "probe_duration", selector("probe_duration_seconds", None, {"instance": probes}), "s",
                           "instance", thr.get("endpoint_probe_duration_seconds"))
        latency_now = []
        for name in app_services:
            latency_now.append({"name": f"{name} p95", "threshold_s": thr.get("service_latency_p95_seconds"),
                                "value_s": _instant_one(prom, selector("lab:service_latency_p95:seconds", {"service": name}))})
        for p in probes:
            latency_now.append({"name": f"probe {p}", "threshold_s": thr.get("endpoint_probe_duration_seconds"),
                                "value_s": _instant_one(prom, selector("probe_duration_seconds", {"instance": p}))})
        uptime = [{"service_id": s.id, "ratio": _instant_one(prom, f"avg_over_time({selector('up', s.prom_labels)}"
                                                                     f"[{int(w.end - w.start)}s])")} for s in svcs]
        return {"range": range_, "step_s": w.step, "metrics_available": True, "cpu": cpu, "memory": memory,
                "requests": requests, "latency": series_set(w, lat), "latency_now": latency_now, "uptime": uptime}
    except PrometheusError:
        return {"range": range_, "step_s": w.step, "metrics_available": False, "cpu": empty, "memory": empty,
                "requests": empty, "latency": empty, "latency_now": [], "uptime": []}
