# monitor/ — cấu hình chạy trên VM monitor

Toàn bộ thư mục này được triển khai lên VM monitor và chạy bằng Docker Compose (ADR-0002).

> **GĐ0:** các file dưới đây được **chuyển nguyên** từ bản Docker một máy (commit mốc `4a9db53`) và **chưa**
> được chỉnh cho 3 VM. Ở GĐ2 sẽ: viết `docker-compose.yml`, đổi target sang file_sd theo VM
> (`prometheus/targets/`), thêm luật/dashboard cho Nginx và PostgreSQL, bỏ các target chỉ có ở bản một máy
> (lab-disk-exporter, cAdvisor toàn host, traffic-generator).

| Thư mục | Nội dung | Dùng lại được |
|---|---|---|
| `prometheus/rules/thresholds.yml` | Ngưỡng `lab:threshold:*` (ADR-0004) | ✅ nguyên cách làm |
| `prometheus/rules/recording.yml`, `alerts.yml` | Chỉ số dẫn xuất, luật cảnh báo | ✅ cần thêm/đổi nhãn job |
| `prometheus/prometheus.yml` | Cấu hình scrape | ⚠️ viết lại target |
| `alertmanager/` | Route + inhibit, receiver webhook | ✅ thêm receiver portal |
| `blackbox/` | Module HTTP/TCP | ✅ |
| `grafana/` | Provisioning + `build_dashboards.py` sinh dashboard | ✅ thêm dashboard nginx/postgres |
| `alert-recorder/` | Nhận webhook, ghi JSONL (ADR-0006) | ✅ |
