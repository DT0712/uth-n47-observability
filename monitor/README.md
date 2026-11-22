# monitor/ — stack giám sát trên VM monitor

Chạy bằng Docker Compose trong VM monitor (ADR-0002). `provision/monitor.sh` khởi động stack bằng wrapper
`obslab-compose` (= `docker compose -p obslab --env-file /opt/obslab/monitor.env -f /vagrant/monitor/docker-compose.yml`).

Container bind-mount cấu hình **thẳng từ thư mục repo** (`/vagrant/monitor`, thư mục chia sẻ của Vagrant): sửa file
trên Windows rồi `python tools/reload.py` là có hiệu lực, không cần provision lại. Dữ liệu (TSDB Prometheus,
Grafana, Alertmanager) nằm trong volume Docker của VM; JSONL của alert-recorder ghi về `data/alerts/` của repo.

| Thành phần | Image | Cổng trên VM monitor | Ghi chú |
|---|---|---|---|
| Prometheus | `prom/prometheus:v2.54.1` | 9090 | `--web.enable-lifecycle` để reload |
| Alertmanager | `prom/alertmanager:v0.27.0` | 9093 | route → alert-recorder; 4 luật inhibit |
| Grafana | `grafana/grafana:11.2.0` | 3000 | provisioning từ file; Viewer ẩn danh + cho nhúng (ADR-0008) |
| Blackbox Exporter | `prom/blackbox-exporter:v0.25.0` | (nội bộ) | probe `http://web/health`, TCP `web:80`, `db:5432` |
| alert-recorder | build từ `alert-recorder/` | 5001 | ghi thời điểm nhận cảnh báo (ADR-0006) |

Từ Windows: `http://192.168.56.10:<cổng>` hoặc cổng forward `http://localhost:<HOST_PORT_*>` (Grafana, Prometheus,
Alertmanager).

## Target (prometheus/prometheus.yml)

| Job | Target | Nhãn chính |
|---|---|---|
| `node` | `monitor:9100`, `web:9100`, `db:9100` | `instance`=`host`= tên VM |
| `demo-app` | `web:80/metrics` (qua Nginx) | `service=demo-app` |
| `nginx` | `web:9113` (nginx-prometheus-exporter) | `service=nginx` |
| `postgres` | `db:9187` (postgres_exporter, role `pg_monitor`) | `service=postgresql` |
| `blackbox-http`, `blackbox-tcp` | `http://web/health`; `web:80`, `db:5432` | `host`, `service` |
| `prometheus`, `alertmanager`, `grafana`, `blackbox-exporter`, `alert-recorder` | trong mạng Compose | `host=monitor` |

## Luật (prometheus/rules/)

- `thresholds.yml`: 8 ngưỡng `lab:threshold:*`, tất cả đang `provisional` (ADR-0004), chốt sau baseline ở GĐ3.
- `recording.yml`: chỉ số dẫn xuất cho host, demo app, Nginx, PostgreSQL.
- `alerts.yml`: 13 luật. Host: HostHighCpu, HostHighMemory, HostDiskAlmostFull. Dịch vụ: ServiceDown, NginxDown,
  PostgresDown, PostgresTooManyConnections, ServiceHighErrorRate, ServiceHighLatency. Endpoint: EndpointDown,
  EndpointSlow. Giám sát: TargetDown, ThresholdConfigMissing. Mỗi luật trỏ tới `runbooks/<alertname>.md`.

## Dashboard (grafana/)

Sinh bằng `python monitor/grafana/build_dashboards.py monitor/grafana/dashboards`, không sửa JSON bằng tay:
`lab-overview` (Tổng quan), `lab-host` (Theo VM), `lab-service` (Demo app), `lab-nginx`, `lab-postgres`.
