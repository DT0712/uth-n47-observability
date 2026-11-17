# ADR-0005: Portal dùng PostgreSQL riêng trên VM monitor

- **Trạng thái:** Chấp nhận — 2026-11-17

## Bối cảnh
VM db chạy PostgreSQL của ứng dụng demo. Đây là **đối tượng bị giám sát** và bị cố ý làm hỏng trong kịch bản
lỗi (dừng service, disk đầy).

## Quyết định
Portal có PostgreSQL riêng, chạy như một container trong Compose của VM monitor, volume riêng.

## Hệ quả
- (+) Kịch bản "db down" không làm sập công cụ dùng để xử lý chính sự cố đó.
- (+) Tách biệt dữ liệu vận hành (cảnh báo, sự cố, người dùng) khỏi dữ liệu nghiệp vụ demo.
- (−) Thêm một CSDL cần backup/migrate (dùng Alembic).
