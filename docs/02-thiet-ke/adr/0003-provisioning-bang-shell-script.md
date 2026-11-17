# ADR-0003: Provisioning bằng shell script

- **Trạng thái:** Chấp nhận — 2026-11-17

## Bối cảnh
Lab phải dựng lại được từ đầu bằng `vagrant up`. Ansible không chạy trực tiếp trên Windows và là thêm một công cụ
nhóm phải học.

## Quyết định
Dùng shell provisioner của Vagrant với các script trong `provision/`:
`common.sh` (mọi VM) → `node_exporter.sh` → `fault_agent.sh` → script theo vai trò (`monitor.sh`, `web.sh`, `db.sh`).
Phiên bản phần mềm ghim tập trung ở `provision/versions.env`.

Quy ước bắt buộc:
- `set -euo pipefail`; script **idempotent** (chạy lại `vagrant provision` không gây lỗi hay nhân đôi cấu hình).
- File dùng LF (ép bằng `.gitattributes`).
- Không hard-code mật khẩu: đọc từ biến môi trường do Vagrantfile truyền vào từ `.env`.

## Hệ quả
- (+) Dễ đọc, dễ gỡ lỗi, không cần cài thêm gì trên Windows.
- (−) Tính idempotent phải tự đảm bảo (kiểm tra trước khi tạo/sửa).

## Phương án đã cân nhắc
- Ansible (`ansible_local`): gọn hơn khi hệ thống lớn, nhưng nhóm chọn shell cho đơn giản.
