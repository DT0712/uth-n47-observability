# ADR-0001: Môi trường lab gồm 3 VM bằng Vagrant + VirtualBox

- **Trạng thái:** Chấp nhận — 2026-11-17
- **Thay thế:** bản Docker Compose một máy (commit mốc `4a9db53`)

## Bối cảnh
Phiên bản đầu chạy toàn bộ trên Docker Desktop của một máy Windows. Giảng viên phản hồi: hệ thống giám sát phải
thể hiện được việc theo dõi **nhiều máy chủ** riêng biệt, gần với hạ tầng thật (mỗi máy có hệ điều hành, đĩa,
dịch vụ systemd riêng). Máy host là Windows 16 GB RAM.

## Quyết định
Dùng Vagrant + VirtualBox tạo 3 VM Ubuntu trong mạng host-only `192.168.56.0/24`:

| VM | IP | Tài nguyên | Vai trò |
|---|---|---|---|
| monitor | .10 | 2 vCPU / 2 GB (trước 2026-11-25: 4 GB) | Prometheus, Alertmanager, Grafana, Blackbox, alert-recorder, portal |
| web | .11 | 1 vCPU / 1 GB | Nginx + ứng dụng demo, nginx-exporter |
| db | .12 | 1 vCPU / 1.5 GB | PostgreSQL, postgres-exporter |

Mọi VM chạy Node Exporter. Tài nguyên cấu hình qua `.env`.

Phiên bản đã kiểm thử: **Vagrant 2.4.9**, **VirtualBox 7.2.22**, box `bento/ubuntu-24.04`.

## Hệ quả
- (+) Metric host là của VM thật (đĩa, CPU, RAM riêng); kịch bản lỗi tác động tới đúng một máy.
- (+) Dịch vụ chạy bằng systemd như máy chủ thật, nên kịch bản "dừng service" sát thực tế.
- (−) Tốn ~4.5 GB RAM; `vagrant up` lần đầu chậm (tải box, cài gói).
- (−) VirtualBox có thể xung đột với Hyper-V/WSL2 → khuyến nghị tắt Docker Desktop khi chạy lab.

## Phương án đã cân nhắc
- **Docker Compose một máy:** nhẹ nhưng không thể hiện được nhiều host (lý do đổi hướng).
- **Kubernetes (kind/k3s):** vượt phạm vi, tốn tài nguyên, không cần cho mục tiêu đề tài.
- **Vagrant + Hyper-V:** tránh xung đột nhưng giảng viên yêu cầu VirtualBox; giữ làm dự phòng.
