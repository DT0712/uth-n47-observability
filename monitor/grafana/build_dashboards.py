"""Sinh 3 dashboard Grafana (overview/host/service) ra JSON.

Cach dung:  python grafana/build_dashboards.py grafana/dashboards
Sua dashboard bang cach sua file nay roi chay lai, hoac sua tren UI -> Export JSON -> ghi de.
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
    stat("CPU host", 'max(lab:host_cpu_usage:percent)', 8, y, unit="percent", decimals=1, steps=PCT_STEPS),
    stat("RAM host", 'max(lab:host_memory_usage:percent)', 12, y, unit="percent", decimals=1, steps=PCT_STEPS),
    stat("Đĩa đầy nhất", 'max(lab:filesystem_usage:percent)', 16, y, unit="percent", decimals=1, steps=PCT_STEPS,
         desc="Giá trị lớn nhất trong các filesystem được theo dõi (kể cả ổ lab-disk)"),
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
p.append(row("Container (cAdvisor)", y)); y += 1
p += [
    ts("CPU theo container (% của 1 lõi)", [("topk(10, lab:container_cpu_usage:percent)", "{{name}}")], 0, y, unit="percent", minv=0),
    ts("RAM theo container (working set)", [("topk(10, lab:container_memory_working_set:bytes)", "{{name}}")], 12, y, unit="bytes", minv=0),
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
overview = dash("lab-overview", "Lab — Tổng quan", p, desc="Tổng quan sức khỏe host, dịch vụ, endpoint và cảnh báo")

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
    ts("Dung lượng đã dùng (%) — host + ổ lab", [('lab:filesystem_usage:percent{instance=~"$instance|lab-disk"}', "{{instance}} {{mountpoint}}")],
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
host = dash("lab-host", "Lab — Theo host", p,
            templating=[qvar("instance", "Host", 'label_values(node_uname_info, instance)')],
            desc="Chi tiết CPU, RAM, đĩa, network, uptime của host (máy ảo Docker Desktop/WSL2)")

# ------------------------------------------------------------------ Service
_id[0] = 0
y = 0
S = 'service="$service"'
p = [
    stat("Trạng thái scrape", f'up{{job="demo-services", {S}}}', 0, y, mappings=UPDOWN,
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
                  f'label_replace(up{{job="demo-services", {S}}}, "kind", "scrape /metrics", "", "") '
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
p.append(row("Tài nguyên container & lỗi giả lập", y)); y += 1
p += [
    ts("CPU container (% của 1 lõi)", [('lab:container_cpu_usage:percent{name="obslab-$service"}', "{{name}}")], 0, y, w=8, unit="percent", minv=0),
    ts("RAM container", [('lab:container_memory_working_set:bytes{name="obslab-$service"}', "{{name}}")], 8, y, w=8, unit="bytes", minv=0),
    ts("Lỗi giả lập đang bật", [(f'lab_fault_active{{{S}}}', "{{fault}}")], 16, y, w=8, minv=0, maxv=1,
       desc="1 = kịch bản lỗi đang tác động lên dịch vụ (đặt bởi tools/fault.py)"),
]
service = dash("lab-service", "Lab — Theo dịch vụ", p,
               templating=[qvar("service", "Dịch vụ", 'label_values(up{job="demo-services"}, service)')],
               desc="Sức khỏe từng dịch vụ demo: up/down, traffic, lỗi, độ trễ, tài nguyên container")

for name, d in [("lab-overview", overview), ("lab-host", host), ("lab-service", service)]:
    with open(os.path.join(OUT, name + ".json"), "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(name, len(d["panels"]), "panels")
