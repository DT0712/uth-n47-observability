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

### Hiện thực (bổ sung 2026-11-23, GĐ3)

| Lớp | Cách làm |
|---|---|
| Nguồn kết nối | `from=` chỉ cho Windows host (`192.168.56.1`) và VM monitor |
| Khóa | `/etc/ssh/obslab_fault_authorized_keys` thuộc root, user không tự thêm khóa được; có `restrict` |
| sshd | `Match User obslab-fault`: chỉ publickey, `ForceCommand`, không PTY, không forwarding, không user rc |
| Wrapper | Chỉ nhận `[a-z0-9_= -]`, tối đa 200 ký tự, 8 từ; không eval, không shell |
| sudo | Đúng một lệnh `/opt/obslab/faults/obslab-fault` |
| Script root | Kịch bản/dịch vụ theo `/etc/obslab/fault.conf` (khai báo trong Vagrantfile), tham số có khoảng cho phép |
| Host key | Sinh riêng cho từng VM (box công khai dùng chung một key cho mọi VM); provision ghi vào `.lab-keys/known_hosts` → client dùng `StrictHostKeyChecking=yes` |

User có shell `/bin/sh` vì sshd chạy `ForceCommand` qua shell của user; không có đường nào tới shell đó. Toàn bộ các
lớp trên được kiểm tra bằng `tools/check_fault_ssh.py`.

**Hạn chế đã biết:** `/vagrant` là thư mục chia sẻ quyền 0777, nên mọi user trên cả 3 VM đọc được `.lab-keys/` (và
`.env`). Trong lab chấp nhận vì khóa chỉ gây được lỗi mô phỏng có thời hạn và bị giới hạn nguồn kết nối; môi trường
thật phải cấp khóa qua kênh riêng.

## Hệ quả
- (+) Lộ khoá cũng chỉ gây được các lỗi mô phỏng có thời hạn, không có shell.
- (−) Thêm kịch bản mới phải sửa cả danh sách cho phép trên VM (chủ ý).
