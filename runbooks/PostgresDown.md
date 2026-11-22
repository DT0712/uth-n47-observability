---
alertname: PostgresDown
title: PostgreSQL trên VM db không kết nối được
severity: critical
category: service
applies_to: [db]
status: draft
---

# PostgresDown — PostgreSQL trên VM db không kết nối được

> Bản nháp GĐ2. Hoàn thiện sau khi chạy kịch bản lỗi ở GĐ3 (ghi lại thao tác thực tế đã dùng).

## Ý nghĩa

postgres-exporter vẫn chạy nhưng không kết nối được PostgreSQL liên tục 30 giây.

## Ảnh hưởng

`/api/db` của demo app trả lỗi 502; dữ liệu không ghi được.

## Kiểm tra nhanh

1. `vagrant ssh db -c "systemctl status postgresql@16-main; pg_isready"`.
1. `vagrant ssh db -c "sudo journalctl -u postgresql@16-main -n 50"`.
1. Đĩa đầy cũng làm PostgreSQL dừng — xem có HostDiskAlmostFull trên db không.

## Phân biệt báo giả

- Mật khẩu role `postgres_exporter` sai sau khi đổi `.env` mà chưa provision lại (PostgreSQL vẫn chạy).

## Xử lý

1. `vagrant ssh db -c "sudo systemctl start postgresql@16-main"`.
1. Lỗi xác thực của exporter: `vagrant provision db`.

## Xác minh & đóng

`pg_up == 1`, `curl http://192.168.56.11/api/db` trả 200.
Ghi kết luận vào sự cố (thật / báo giả + lý do) trước khi đóng (BR-01, BR-04).
