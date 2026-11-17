# ADR-0002: Stack giám sát và portal chạy bằng Docker Compose trong VM monitor

- **Trạng thái:** Chấp nhận — 2026-11-17

## Bối cảnh
VM monitor chứa nhiều thành phần (Prometheus, Alertmanager, Grafana, Blackbox, alert-recorder, portal backend,
frontend, CSDL portal). Cài từng thứ bằng binary + systemd rất tốn công và khó đồng bộ phiên bản.

## Quyết định
- Trên **monitor**: cài Docker Engine, chạy toàn bộ bằng `monitor/docker-compose.yml` (phiên bản image được ghim).
- Trên **web** và **db**: cài trực tiếp bằng gói/binary + systemd (Nginx, PostgreSQL, exporter), vì đây là
  "máy chủ được giám sát" và kịch bản lỗi cần thao tác với dịch vụ systemd thật.

## Hệ quả
- (+) Dùng lại cấu hình đã có ở bản Docker (rules, dashboard, alert-recorder).
- (+) Portal sau này chỉ là thêm service vào cùng Compose.
- (−) Trên monitor có hai lớp (VM + container): Node Exporter đo VM, còn tài nguyên từng container cần cAdvisor
  (tuỳ chọn, chỉ trên monitor).

## Phương án đã cân nhắc
- Tất cả binary + systemd: đồng nhất nhưng nhiều việc, khó nâng cấp.
- Docker trên cả 3 VM: làm mờ ranh giới "máy chủ thật", kịch bản dừng service kém sát thực tế.
