"""Sinh 5 dashboard Grafana (tổng quan, VM, demo app, Nginx, PostgreSQL) ra JSON.

Cách dùng:  python monitor/grafana/build_dashboards.py monitor/grafana/dashboards
Sửa dashboard bằng cách sửa file này rồi chạy lại (Grafana tự nạp lại sau ~30 giây), không sửa JSON bằng tay.
"""
import json, os, sys

OUT = sys.argv[1]
DS = {"type": "prometheus", "uid": "prometheus"}
_id = [0]


def nid():
    _id[0] += 1
    return _id[0]


def tgt(expr, legend="", ref="A", instant=False, fmt=None):
    t = {"datasource": DS, "expr": expr, "legendFormat": legend, "refId": ref, "range": not instant, "instant": instant}
    if fmt:
        t["format"] = fmt
    return t


def refs(targets):
    out = []
    for i, t in enumerate(targets):
        if isinstance(t, tuple):
            t = tgt(*t)
        t["refId"] = chr(65 + i)
        out.append(t)
    return out


def ts(title, targets, x, y, w=12, h=8, unit="short", desc="", minv=None, maxv=None, thr_ref=None, stack=False):
    fc = {"unit": unit, "custom": {"lineWidth": 2, "fillOpacity": 10, "showPoints": "never", "spanNulls": False,
                                   "stacking": {"mode": "normal" if stack else "none"}}}
    if minv is not None:
        fc["min"] = minv
    if maxv is not None:
        fc["max"] = maxv
    p = {"id": nid(), "type": "timeseries", "title": title, "description": desc, "datasource": DS,
         "gridPos": {"x": x, "y": y, "w": w, "h": h},
         "fieldConfig": {"defaults": fc, "overrides": []},
         "options": {"legend": {"displayMode": "table", "placement": "bottom", "calcs": ["lastNotNull", "max", "mean"]},
                     "tooltip": {"mode": "multi", "sort": "desc"}},
         "targets": refs(targets)}
    if thr_ref:
        # Đường ngưỡng lấy từ chuỗi lab:threshold:* -> nét đứt màu đỏ
        p["fieldConfig"]["overrides"].append({
            "matcher": {"id": "byName", "options": "ngưỡng"},
            "properties": [
                {"id": "color", "value": {"mode": "fixed", "fixedColor": "red"}},
                {"id": "custom.lineStyle", "value": {"fill": "dash", "dash": [10, 10]}},
                {"id": "custom.fillOpacity", "value": 0},
                {"id": "custom.stacking", "value": {"mode": "none"}},
            ]})
        p["targets"] = refs(targets + [(f"max({thr_ref})", "ngưỡng")])
    return p


def stat(title, expr, x, y, w=4, h=4, unit="short", steps=None, desc="", decimals=None, mappings=None):
    steps = steps or [{"color": "green", "value": None}]
    d = {"unit": unit, "thresholds": {"mode": "absolute", "steps": steps}, "color": {"mode": "thresholds"}}
    if decimals is not None:
        d["decimals"] = decimals
    if mappings:
        d["mappings"] = mappings
    return {"id": nid(), "type": "stat", "title": title, "description": desc, "datasource": DS,
            "gridPos": {"x": x, "y": y, "w": w, "h": h},
            "fieldConfig": {"defaults": d, "overrides": []},
            "options": {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                        "colorMode": "background", "graphMode": "area", "textMode": "auto", "justifyMode": "auto"},
            "targets": refs([(expr, "", "A", True)])}


UPDOWN = [{"type": "value", "options": {"0": {"text": "DOWN", "color": "red"}, "1": {"text": "UP", "color": "green"}}}]


def timeline(title, expr, legend, x, y, w=24, h=8, desc="", mappings=UPDOWN):
    return {"id": nid(), "type": "state-timeline", "title": title, "description": desc, "datasource": DS,
            "gridPos": {"x": x, "y": y, "w": w, "h": h},
            "fieldConfig": {"defaults": {"mappings": mappings, "color": {"mode": "thresholds"},
                                         "thresholds": {"mode": "absolute", "steps": [{"color": "red", "value": None}, {"color": "green", "value": 1}]},
                                         "custom": {"fillOpacity": 80, "lineWidth": 0}}, "overrides": []},
            "options": {"showValue": "never", "mergeValues": True, "rowHeight": 0.8, "legend": {"showLegend": False}},
            "targets": refs([(expr, legend)])}


def table(title, expr, x, y, w=12, h=8, desc="", exclude=None, rename=None):
    exclude = exclude or {}
    return {"id": nid(), "type": "table", "title": title, "description": desc, "datasource": DS,
            "gridPos": {"x": x, "y": y, "w": w, "h": h},
            "fieldConfig": {"defaults": {}, "overrides": []},
            "options": {"showHeader": True, "cellHeight": "sm"},
            "transformations": [{"id": "organize", "options": {"excludeByName": exclude, "renameByName": rename or {}}}],
            "targets": refs([tgt(expr, "", "A", True, "table")])}


def row(title, y):
    return {"id": nid(), "type": "row", "title": title, "collapsed": False, "gridPos": {"x": 0, "y": y, "w": 24, "h": 1}, "panels": []}


ANNOTATIONS = {"list": [
    {"builtIn": 1, "datasource": {"type": "grafana", "uid": "-- Grafana --"}, "enable": True, "hide": True,
     "iconColor": "rgba(0, 211, 255, 1)", "name": "Annotations & Alerts", "type": "dashboard"},
    {"datasource": DS, "enable": True, "iconColor": "orange", "name": "Lỗi giả lập (fault)",
     "expr": "lab_fault_active == 1", "step": "15s", "titleFormat": "Fault {{fault}}", "textFormat": "{{service}}",
     "tagKeys": "service,fault", "useValueForTime": False},
    {"datasource": DS, "enable": True, "iconColor": "red", "name": "Cảnh báo firing",
     "expr": "ALERTS{alertstate=\"firing\"}", "step": "15s", "titleFormat": "{{alertname}}",
     "textFormat": "{{instance}} {{service}}", "tagKeys": "alertname,severity"},
]}


def dash(uid, title, panels, templating=None, desc=""):
    return {"uid": uid, "title": title, "description": desc, "tags": ["lab", "observability"], "timezone": "browser",
            "schemaVersion": 39, "version": 1, "editable": True, "graphTooltip": 1, "refresh": "30s",
            "time": {"from": "now-1h", "to": "now"},
            "timepicker": {"refresh_intervals": ["10s", "30s", "1m", "5m", "15m"]},
            "annotations": ANNOTATIONS, "templating": {"list": templating or []},
            "links": [{"title": "Dashboards lab", "type": "dashboards", "tags": ["lab"], "asDropdown": True, "includeVars": False, "keepTime": True}],
            "panels": panels}


def qvar(name, label, query, multi=False, include_all=False):
    return {"name": name, "label": label, "type": "query", "datasource": DS,
            "query": {"query": query, "refId": "PrometheusVariableQueryEditor-VariableQuery"},
            "definition": query, "refresh": 2, "sort": 1, "multi": multi, "includeAll": include_all,
            "current": {}, "options": [], "hide": 0}


PCT_STEPS = [{"color": "green", "value": None}, {"color": "orange", "value": 70}, {"color": "red", "value": 85}]

# ------------------------------------------------------------------ Overview
_id[0] = 0
y = 0
p = [row("Tình trạng chung", y)]
y += 1
p += [
    stat("Targets UP", 'sum(up) / count(up) * 100', 0, y, unit="percent", decimals=0,
         steps=[{"color": "red", "value": None}, {"color": "orange", "value": 90}, {"color": "green", "value": 100}],
         desc="Tỉ lệ target Prometheus đang UP"),
    stat("Cảnh báo đang firing", 'count(ALERTS{alertstate="firing"}) or vector(0)', 4, y,
         steps=[{"color": "green", "value": None}, {"color": "red", "value": 1}]),
    stat("CPU cao nhất (VM)", 'max(lab:host_cpu_usage:percent)', 8, y, unit="percent", decimals=1, steps=PCT_STEPS),
    stat("RAM cao nhất (VM)", 'max(lab:host_memory_usage:percent)', 12, y, unit="percent", decimals=1, steps=PCT_STEPS),
    stat("Đĩa đầy nhất", 'max(lab:filesystem_usage:percent)', 16, y, unit="percent", decimals=1, steps=PCT_STEPS,
         desc="Giá trị lớn nhất trong các filesystem được theo dõi của 3 VM (kể cả /mnt/labdisk)"),
    stat("Endpoint OK", 'avg(probe_success{job="blackbox-http"}) * 100', 20, y, unit="percent", decimals=0,
         steps=[{"color": "red", "value": None}, {"color": "green", "value": 100}]),
]
y += 4
p.append(timeline("Lịch sử UP/DOWN của mọi target", 'up', "{{job}} / {{instance}}", 0, y, h=10))
y += 10
p.append(row("Host", y)); y += 1
p += [
    ts("CPU host (%)", [("lab:host_cpu_usage:percent", "{{instance}}")], 0, y, unit="percent", minv=0, maxv=100,
       thr_ref="lab:threshold:host_cpu_usage_percent"),
    ts("RAM host (%)", [("lab:host_memory_usage:percent", "{{instance}}")], 12, y, unit="percent", minv=0, maxv=100,
       thr_ref="lab:threshold:host_memory_usage_percent"),
]
y += 8
p += [
    ts("Dung lượng đĩa đã dùng (%)", [("lab:filesystem_usage:percent", "{{instance}} {{mountpoint}}")], 0, y,
       unit="percent", minv=0, maxv=100, thr_ref="lab:threshold:filesystem_usage_percent"),
    ts("Network host", [("lab:host_network_receive:bytes_per_second", "rx {{instance}}"),
                        ("-lab:host_network_transmit:bytes_per_second", "tx {{instance}}")], 12, y, unit="Bps",
       desc="Nhận (dương) / gửi (âm)"),
]
y += 8
p.append(row("Endpoint & dịch vụ", y)); y += 1
p.append(timeline("Blackbox probe (HTTP + TCP)", 'probe_success', "{{job}} {{instance}}", 0, y, h=8))
y += 8
p += [
    ts("Thời gian probe HTTP (s)", [('probe_duration_seconds{job="blackbox-http"}', "{{instance}}")], 0, y, unit="s", minv=0,
       thr_ref="lab:threshold:endpoint_probe_duration_seconds"),
    ts("Request rate /api/work (rps)", [("lab:service_request_rate:rps", "{{service}}")], 12, y, unit="reqps", minv=0),
]
y += 8
p += [
    ts("Tỉ lệ lỗi 5xx", [("lab:service_error_ratio:ratio", "{{service}}")], 0, y, unit="percentunit", minv=0,
       thr_ref="lab:threshold:service_error_ratio"),
    ts("Latency p95 /api/work", [("lab:service_latency_p95:seconds", "{{service}}")], 12, y, unit="s", minv=0,
       thr_ref="lab:threshold:service_latency_p95_seconds"),
]
y += 8
p.append(row("Nginx & PostgreSQL", y)); y += 1
p += [
    ts("Nginx: request/giây", [("lab:nginx_request_rate:rps", "{{instance}}")], 0, y, w=6, unit="reqps", minv=0),
    ts("Nginx: kết nối đang mở", [('nginx_connections_active{job="nginx"}', "{{instance}}")], 6, y, w=6, minv=0),
    ts("PostgreSQL: % kết nối / max_connections", [("lab:postgres_connections_usage:percent", "{{instance}}")], 12, y, w=6,
       unit="percent", minv=0, thr_ref="lab:threshold:postgres_connections_usage_percent"),
    ts("PostgreSQL: giao dịch/giây", [("lab:postgres_transactions:tps", "{{instance}}")], 18, y, w=6, unit="ops", minv=0),
]
y += 8
p.append(row("Cảnh báo & ngưỡng", y)); y += 1
p += [
    table("Cảnh báo đang hoạt động (pending/firing)", "ALERTS", 0, y, w=14,
          exclude={"Time": True, "__name__": True, "Value": True, "lab": True},
          desc="Từ series ALERTS của Prometheus. Lịch sử: xem annotation đỏ trên các biểu đồ."),
    table("Ngưỡng hiện hành (prometheus/rules/thresholds.yml)", '{__name__=~"lab:threshold:.*"}', 14, y, w=10,
          exclude={"Time": True, "lab": True}, rename={"__name__": "ngưỡng", "Value": "giá trị"},
          desc="threshold_status=provisional nghĩa là chưa chốt sau baseline"),
]
overview = dash("lab-overview", "Lab — Tổng quan", p, desc="Tổng quan sức khỏe 3 VM, dịch vụ, endpoint và cảnh báo")

# ------------------------------------------------------------------ Host
_id[0] = 0
y = 0
I = 'instance="$instance"'
p = [
    stat("Uptime", f'time() - node_boot_time_seconds{{{I}}}', 0, y, unit="s", decimals=0),
    stat("Số lõi CPU", f'count(node_cpu_seconds_total{{{I}, mode="idle"}})', 4, y),
    stat("Tổng RAM", f'node_memory_MemTotal_bytes{{{I}}}', 8, y, unit="bytes"),
    stat("CPU", f'lab:host_cpu_usage:percent{{{I}}}', 12, y, unit="percent", decimals=1, steps=PCT_STEPS),
    stat("RAM", f'lab:host_memory_usage:percent{{{I}}}', 16, y, unit="percent", decimals=1, steps=PCT_STEPS),
    stat("Load 1m / lõi", f'node_load1{{{I}}} / count(node_cpu_seconds_total{{{I}, mode="idle"}})', 20, y, decimals=2,
         steps=[{"color": "green", "value": None}, {"color": "orange", "value": 1}, {"color": "red", "value": 2}]),
]
y += 4
p.append(row("CPU & RAM", y)); y += 1
p += [
    ts("CPU (%)", [(f"lab:host_cpu_usage:percent{{{I}}}", "CPU %")], 0, y, unit="percent", minv=0, maxv=100,
       thr_ref="lab:threshold:host_cpu_usage_percent"),
    ts("CPU theo mode", [(f'100 * sum by (mode) (rate(node_cpu_seconds_total{{{I}, mode!="idle"}}[1m])) / scalar(count(node_cpu_seconds_total{{{I}, mode="idle"}}))', "{{mode}}")],
       12, y, unit="percent", minv=0, stack=True),
]
y += 8
p += [
    ts("RAM (%)", [(f"lab:host_memory_usage:percent{{{I}}}", "RAM %")], 0, y, unit="percent", minv=0, maxv=100,
       thr_ref="lab:threshold:host_memory_usage_percent"),
    ts("RAM chi tiết", [
        (f"node_memory_MemTotal_bytes{{{I}}} - node_memory_MemAvailable_bytes{{{I}}}", "đã dùng"),
        (f"node_memory_Cached_bytes{{{I}}} + node_memory_Buffers_bytes{{{I}}}", "cache+buffers"),
        (f"node_memory_MemAvailable_bytes{{{I}}}", "khả dụng"),
        (f"node_memory_SwapTotal_bytes{{{I}}} - node_memory_SwapFree_bytes{{{I}}}", "swap đã dùng"),
    ], 12, y, unit="bytes", minv=0),
]
y += 8
p.append(row("Đĩa", y)); y += 1
p += [
    ts("Dung lượng đã dùng (%) theo mountpoint", [(f'lab:filesystem_usage:percent{{{I}}}', "{{mountpoint}}")],
       0, y, unit="percent", minv=0, maxv=100, thr_ref="lab:threshold:filesystem_usage_percent"),
    ts("Disk I/O", [(f'sum by (device) (rate(node_disk_read_bytes_total{{{I}}}[1m]))', "đọc {{device}}"),
                    (f'-sum by (device) (rate(node_disk_written_bytes_total{{{I}}}[1m]))', "ghi {{device}}")], 12, y, unit="Bps"),
]
y += 8
p.append(row("Network", y)); y += 1
p += [
    ts("Băng thông theo interface", [
        (f'rate(node_network_receive_bytes_total{{{I}, device!~"lo|veth.*|br-.*|docker.*"}}[1m])', "rx {{device}}"),
        (f'-rate(node_network_transmit_bytes_total{{{I}, device!~"lo|veth.*|br-.*|docker.*"}}[1m])', "tx {{device}}")],
       0, y, unit="Bps"),
    ts("Lỗi / drop gói tin", [
        (f'sum(rate(node_network_receive_errs_total{{{I}}}[1m]) + rate(node_network_transmit_errs_total{{{I}}}[1m]))', "errors"),
        (f'sum(rate(node_network_receive_drop_total{{{I}}}[1m]) + rate(node_network_transmit_drop_total{{{I}}}[1m]))', "drops")],
       12, y, unit="pps", minv=0),
]
y += 8
p.append(timeline("Dịch vụ systemd của lab trên VM (active = UP)",
                  f'node_systemd_unit_state{{{I}, state="active"}}', "{{name}}", 0, y, h=6,
                  desc="Collector systemd của Node Exporter, chỉ theo dõi các unit của lab"))
host = dash("lab-host", "Lab — Theo VM", p,
            templating=[qvar("instance", "VM", 'label_values(node_uname_info{job="node"}, instance)')],
            desc="Chi tiết CPU, RAM, đĩa, network, uptime, dịch vụ systemd của từng VM")

# ------------------------------------------------------------------ Service
_id[0] = 0
y = 0
S = 'service="$service"'
p = [
    stat("Trạng thái scrape", f'up{{job="demo-app", {S}}}', 0, y, mappings=UPDOWN,
         steps=[{"color": "red", "value": None}, {"color": "green", "value": 1}]),
    stat("Uptime tiến trình", f'time() - lab_service_start_time_seconds{{{S}}}', 4, y, unit="s", decimals=0),
    stat("Probe /health", f'probe_success{{job="blackbox-http", {S}}}', 8, y, mappings=UPDOWN,
         steps=[{"color": "red", "value": None}, {"color": "green", "value": 1}]),
    stat("Request rate", f'lab:service_request_rate:rps{{{S}}}', 12, y, unit="reqps", decimals=2),
    stat("Tỉ lệ lỗi", f'lab:service_error_ratio:ratio{{{S}}}', 16, y, unit="percentunit", decimals=1,
         steps=[{"color": "green", "value": None}, {"color": "red", "value": 0.05}]),
    stat("p95 latency", f'lab:service_latency_p95:seconds{{{S}}}', 20, y, unit="s", decimals=3),
]
y += 4
p.append(timeline("Lịch sử UP/DOWN (scrape + probe HTTP + probe TCP)",
                  f'label_replace(up{{job="demo-app", {S}}}, "kind", "scrape /metrics", "", "") '
                  f'or label_replace(probe_success{{{S}, job="blackbox-http"}}, "kind", "probe HTTP /health", "", "") '
                  f'or label_replace(probe_success{{{S}, job="blackbox-tcp"}}, "kind", "probe TCP", "", "")',
                  "{{kind}}", 0, y, h=6))
y += 6
p.append(row("Traffic, lỗi, độ trễ", y)); y += 1
p += [
    ts("Request rate theo mã trạng thái", [(f'sum by (status) (rate(http_requests_total{{{S}, path="/api/work"}}[1m]))', "{{status}}")],
       0, y, unit="reqps", minv=0, stack=True),
    ts("Tỉ lệ lỗi 5xx", [(f"lab:service_error_ratio:ratio{{{S}}}", "tỉ lệ lỗi")], 12, y, unit="percentunit", minv=0,
       thr_ref="lab:threshold:service_error_ratio"),
]
y += 8
p += [
    ts("Latency /api/work", [
        (f'histogram_quantile(0.50, sum by (le) (rate(http_request_duration_seconds_bucket{{{S}, path="/api/work"}}[1m])))', "p50"),
        (f'lab:service_latency_p95:seconds{{{S}}}', "p95"),
        (f'histogram_quantile(0.99, sum by (le) (rate(http_request_duration_seconds_bucket{{{S}, path="/api/work"}}[1m])))', "p99")],
       0, y, unit="s", minv=0, thr_ref="lab:threshold:service_latency_p95_seconds"),
    ts("Thời gian probe /health (Blackbox)", [(f'probe_duration_seconds{{job="blackbox-http", {S}}}', "probe")], 12, y, unit="s", minv=0,
       thr_ref="lab:threshold:endpoint_probe_duration_seconds"),
]
y += 8
p.append(row("Truy vấn CSDL & lỗi giả lập", y)); y += 1
p += [
    ts("/api/db theo mã trạng thái", [(f'sum by (status) (rate(http_requests_total{{{S}, path="/api/db"}}[1m]))', "{{status}}")],
       0, y, w=8, unit="reqps", minv=0, stack=True, desc="Endpoint ghi/đọc PostgreSQL trên VM db"),
    ts("Lỗi kết nối CSDL", [(f'rate(lab_db_errors_total{{{S}}}[1m])', "lỗi/giây")], 8, y, w=8, unit="ops", minv=0),
    ts("Lỗi giả lập đang bật", [(f'lab_fault_active{{{S}}}', "{{fault}}")], 16, y, w=8, minv=0, maxv=1,
       desc="1 = kịch bản lỗi đang tác động lên dịch vụ (đặt bởi faults/ ở GĐ3)"),
]
service = dash("lab-service", "Lab — Demo app", p,
               templating=[qvar("service", "Dịch vụ", 'label_values(up{job="demo-app"}, service)')],
               desc="Sức khỏe demo app trên VM web: up/down, traffic, lỗi, độ trễ, truy vấn CSDL")

UP_STEPS = [{"color": "red", "value": None}, {"color": "green", "value": 1}]

# ------------------------------------------------------------------ Nginx
_id[0] = 0
y = 0
N = 'job="nginx", instance="$instance"'
p = [
    stat("Nginx", f'nginx_up{{{N}}}', 0, y, mappings=UPDOWN, steps=UP_STEPS),
    stat("Exporter", f'up{{{N}}}', 4, y, mappings=UPDOWN, steps=UP_STEPS),
    stat("Request/giây", 'lab:nginx_request_rate:rps{instance="$instance"}', 8, y, unit="reqps", decimals=2),
    stat("Kết nối đang mở", f'nginx_connections_active{{{N}}}', 12, y),
    stat("Probe TCP :80", 'probe_success{job="blackbox-tcp", service="nginx", host="$instance"}', 16, y,
         mappings=UPDOWN, steps=UP_STEPS),
    stat("Kết nối bị bỏ (accepted - handled)",
         f'nginx_connections_accepted{{{N}}} - nginx_connections_handled{{{N}}}', 20, y,
         steps=[{"color": "green", "value": None}, {"color": "red", "value": 1}],
         desc="Khác 0 nghĩa là Nginx hết worker_connections"),
]
y += 4
p.append(timeline("Lịch sử UP/DOWN",
                  f'label_replace(nginx_up{{{N}}}, "kind", "nginx (stub_status)", "", "") '
                  'or label_replace(probe_success{job="blackbox-tcp", service="nginx", host="$instance"}, "kind", "probe TCP :80", "", "")',
                  "{{kind}}", 0, y, h=5))
y += 5
p += [
    ts("Request/giây", [(f'rate(nginx_http_requests_total{{{N}}}[1m])', "request/s")], 0, y, unit="reqps", minv=0),
    ts("Trạng thái kết nối", [(f'nginx_connections_reading{{{N}}}', "reading"),
                               (f'nginx_connections_writing{{{N}}}', "writing"),
                               (f'nginx_connections_waiting{{{N}}}', "waiting")], 12, y, minv=0, stack=True),
]
y += 8
p += [
    ts("Kết nối mới/giây", [(f'rate(nginx_connections_accepted{{{N}}}[1m])', "accepted"),
                            (f'rate(nginx_connections_handled{{{N}}}[1m])', "handled")], 0, y, unit="ops", minv=0),
    ts("CPU & RAM của VM", [('lab:host_cpu_usage:percent{instance="$instance"}', "CPU %"),
                            ('lab:host_memory_usage:percent{instance="$instance"}', "RAM %")],
       12, y, unit="percent", minv=0, maxv=100),
]
nginx = dash("lab-nginx", "Lab — Nginx", p,
             templating=[qvar("instance", "VM", 'label_values(nginx_up{job="nginx"}, instance)')],
             desc="Nginx trên VM web: trạng thái, request, kết nối (nginx-prometheus-exporter đọc stub_status)")

# ------------------------------------------------------------------ PostgreSQL
_id[0] = 0
y = 0
G = 'job="postgres", instance="$instance"'
DB = 'datname!~"template.*"'
p = [
    stat("PostgreSQL", f'pg_up{{{G}}}', 0, y, mappings=UPDOWN, steps=UP_STEPS),
    stat("Uptime", f'time() - pg_postmaster_start_time_seconds{{{G}}}', 4, y, unit="s", decimals=0),
    stat("% kết nối", 'lab:postgres_connections_usage:percent{instance="$instance"}', 8, y, unit="percent",
         decimals=0, steps=PCT_STEPS),
    stat("Giao dịch/giây", 'lab:postgres_transactions:tps{instance="$instance"}', 12, y, unit="ops", decimals=2),
    stat("Cache hit", f'sum(rate(pg_stat_database_blks_hit{{{G}}}[5m])) / '
                      f'clamp_min(sum(rate(pg_stat_database_blks_hit{{{G}}}[5m])) + sum(rate(pg_stat_database_blks_read{{{G}}}[5m])), 1e-9)',
         16, y, unit="percentunit", decimals=1,
         steps=[{"color": "red", "value": None}, {"color": "orange", "value": 0.9}, {"color": "green", "value": 0.99}]),
    stat("Deadlock (1h)", f'sum(increase(pg_stat_database_deadlocks{{{G}}}[1h]))', 20, y, decimals=0,
         steps=[{"color": "green", "value": None}, {"color": "red", "value": 1}]),
]
y += 4
p.append(timeline("Lịch sử UP/DOWN",
                  f'label_replace(pg_up{{{G}}}, "kind", "pg_up (exporter kết nối được)", "", "") '
                  'or label_replace(probe_success{job="blackbox-tcp", service="postgresql", host="$instance"}, "kind", "probe TCP :5432", "", "")',
                  "{{kind}}", 0, y, h=5))
y += 5
p += [
    ts("Kết nối theo CSDL", [(f'pg_stat_database_numbackends{{{G}, {DB}}}', "{{datname}}"),
                            (f'max(pg_settings_max_connections{{{G}}})', "max_connections")], 0, y, minv=0),
    ts("Giao dịch/giây theo CSDL", [(f'rate(pg_stat_database_xact_commit{{{G}, {DB}}}[1m])', "commit {{datname}}"),
                                   (f'rate(pg_stat_database_xact_rollback{{{G}, {DB}}}[1m])', "rollback {{datname}}")],
       12, y, unit="ops", minv=0),
]
y += 8
p += [
    ts("Dòng ghi/giây", [(f'rate(pg_stat_database_tup_inserted{{{G}, {DB}}}[1m])', "insert {{datname}}"),
                         (f'rate(pg_stat_database_tup_deleted{{{G}, {DB}}}[1m])', "delete {{datname}}")],
       0, y, unit="ops", minv=0),
    ts("Dung lượng CSDL", [(f'pg_database_size_bytes{{{G}, {DB}}}', "{{datname}}")], 12, y, unit="bytes", minv=0),
]
postgres = dash("lab-postgres", "Lab — PostgreSQL", p,
                templating=[qvar("instance", "VM", 'label_values(pg_up{job="postgres"}, instance)')],
                desc="PostgreSQL trên VM db: trạng thái, kết nối, giao dịch, cache, dung lượng (postgres_exporter)")

for name, d in [("lab-overview", overview), ("lab-host", host), ("lab-service", service),
                ("lab-nginx", nginx), ("lab-postgres", postgres)]:
    # newline="\n": giữ LF cả khi chạy trên Windows để git không báo thay đổi giả.
    with open(os.path.join(OUT, name + ".json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(name, len(d["panels"]), "panels")
