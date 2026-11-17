# ADR-0007: Chạy kịch bản lỗi qua SSH bị giới hạn, chỉ admin

- **Trạng thái:** Chấp nhận — 2026-11-17

## Bối cảnh
Portal cần gây lỗi trên VM web/db (CPU cao, disk đầy, dừng service). Một khoá SSH có quyền root nằm trong
container của portal là rủi ro lớn: lỗ hổng ở portal đồng nghĩa với chiếm quyền mọi VM.

## Quyết định
- Khoá SSH **riêng của lab** (ed25519), sinh lúc provision vào `.lab-keys/` (gitignore), không dùng khoá cá nhân.
- Trên web/db: user `obslab-fault`, không mật khẩu, không shell tương tác. `authorized_keys` dùng
  `command="/opt/obslab/faults/obslab-fault-ssh",no-pty,no-port-forwarding,no-agent-forwarding,no-X11-forwarding`
  → mọi kết nối chỉ chạy được wrapper này. Wrapper đọc `SSH_ORIGINAL_COMMAND` và **chỉ chấp nhận danh sách
  kịch bản cho phép** (`cpu`, `disk`, `service-stop`, ... với `start|stop|status`, tham số được kiểm tra).
- sudoers chỉ cho phép `obslab-fault` chạy đúng `/opt/obslab/faults/obslab-fault` với quyền root.
- Kịch bản luôn có thời hạn tự kết thúc (không để lỗi treo nếu portal mất kết nối).
- Trong portal: chỉ vai trò **admin** được chạy kịch bản; mọi lần chạy ghi audit log.
- CLI trên Windows dùng cùng cơ chế (dự phòng khi portal chưa có).

## Hệ quả
- (+) Lộ khoá cũng chỉ gây được các lỗi mô phỏng có thời hạn, không có shell.
- (−) Thêm kịch bản mới phải sửa cả danh sách cho phép trên VM (chủ ý).
