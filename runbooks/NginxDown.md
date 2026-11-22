---
alertname: NginxDown
title: Nginx trên VM web dừng
severity: critical
category: service
applies_to: [web]
status: draft
---

# NginxDown — Nginx trên VM web dừng

> Bản nháp GĐ2. Hoàn thiện sau khi chạy kịch bản lỗi ở GĐ3 (ghi lại thao tác thực tế đã dùng).

## Ý nghĩa

nginx-exporter vẫn chạy nhưng không đọc được `stub_status` liên tục 30 giây.

## Ảnh hưởng

Mọi request HTTP tới VM web thất bại. ServiceDown, EndpointDown... trên cùng VM bị chặn (inhibit).

## Kiểm tra nhanh

1. `vagrant ssh web -c "systemctl status nginx; sudo nginx -t"`.
1. `vagrant ssh web -c "journalctl -u nginx -n 50"`.

## Phân biệt báo giả

- nginx-exporter cấu hình sai URL (khi đó Nginx vẫn phục vụ được `curl http://192.168.56.11/health`).

## Xử lý

1. Lỗi cấu hình: sửa theo `nginx -t`, hoặc `vagrant provision web` để ghi lại cấu hình chuẩn.
1. `vagrant ssh web -c "sudo systemctl start nginx"`.

## Xác minh & đóng

`nginx_up == 1`, probe `http://web/health` thành công.
Ghi kết luận vào sự cố (thật / báo giả + lý do) trước khi đóng (BR-01, BR-04).
