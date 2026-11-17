# Architecture Decision Records (ADR)

Mỗi quyết định kiến trúc quan trọng được ghi thành một file ngắn: **bối cảnh → quyết định → hệ quả → phương án đã cân nhắc**.
Không sửa ADR đã "Chấp nhận"; nếu đổi ý, viết ADR mới với trạng thái "Thay thế ADR-xxxx".

| ADR | Tiêu đề | Trạng thái | Ngày |
|---|---|---|---|
| [0001](0001-moi-truong-3-vm-vagrant.md) | Môi trường lab: 3 VM bằng Vagrant + VirtualBox | Chấp nhận | 2026-11-17 |
| [0002](0002-stack-giam-sat-docker-compose-tren-vm-monitor.md) | Stack giám sát và portal chạy bằng Docker Compose trong VM monitor | Chấp nhận | 2026-11-17 |
| [0003](0003-provisioning-bang-shell-script.md) | Provisioning bằng shell script | Chấp nhận | 2026-11-17 |
| [0004](0004-nguong-canh-bao-dang-recording-rule.md) | Ngưỡng cảnh báo là recording rule `lab:threshold:*`, chốt sau baseline | Chấp nhận | 2026-11-17 |
| [0005](0005-csdl-rieng-cho-portal.md) | Portal dùng PostgreSQL riêng trên VM monitor | Chấp nhận | 2026-11-17 |
| [0006](0006-alert-recorder-song-song-portal.md) | alert-recorder nhận webhook song song với portal | Chấp nhận | 2026-11-17 |
| [0007](0007-ssh-gioi-han-cho-kich-ban-loi.md) | Chạy kịch bản lỗi qua SSH bị giới hạn, chỉ admin | Chấp nhận | 2026-11-17 |
| [0008](0008-nhung-grafana-viewer-an-danh.md) | Nhúng Grafana bằng Viewer ẩn danh | Chấp nhận (có hạn chế) | 2026-11-17 |
