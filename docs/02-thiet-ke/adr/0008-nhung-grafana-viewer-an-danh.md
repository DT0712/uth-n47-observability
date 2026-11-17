# ADR-0008: Nhúng Grafana bằng Viewer ẩn danh

- **Trạng thái:** Chấp nhận, có hạn chế — 2026-11-17

## Bối cảnh
Portal cần nút mở dashboard Grafana tương ứng và/hoặc nhúng panel. Nhúng iframe cần trình duyệt truy cập được
Grafana mà không bị bắt đăng nhập riêng.

## Quyết định
- Bật `GF_AUTH_ANONYMOUS_ENABLED=true` với vai trò **Viewer** và `GF_SECURITY_ALLOW_EMBEDDING=true`.
- Portal nhúng panel ở chế độ `d-solo` và tạo link tới dashboard kèm biến (`var-instance`, `var-service`) và
  khoảng thời gian.

## Hệ quả / Hạn chế (ghi vào mục hạn chế của báo cáo)
- Bất kỳ ai truy cập được cổng Grafana đều **xem** được mọi dashboard mà không cần đăng nhập. Chấp nhận được
  vì Grafana chỉ bind `127.0.0.1` của máy host và dữ liệu là dữ liệu lab.
- Phân quyền admin/operator của portal **không** áp dụng lên Grafana.
- Môi trường thật nên thay bằng auth proxy/SSO hoặc service account + render ảnh phía server.
