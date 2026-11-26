---
alertname: ServiceDown
title: Demo app không phản hồi /metrics
severity: critical
category: service
applies_to: [web]
status: draft
---

# ServiceDown — Demo app không phản hồi /metrics

> Bản nháp GĐ2. Hoàn thiện sau khi chạy kịch bản lỗi ở GĐ3 (ghi lại thao tác thực tế đã dùng).

## Ý nghĩa

Prometheus không scrape được `/metrics` của demo app (đi qua Nginx) liên tục 30 giây. Không tính khi Nginx đang down
(đường scrape duy nhất tới app); khi đó chỉ có NginxDown.

## Ảnh hưởng

Người dùng không dùng được ứng dụng. Các cảnh báo endpoint/lỗi/độ trễ của demo app bị chặn (inhibit).

## Kiểm tra nhanh

1. Nếu có `NginxDown` cùng lúc thì xử lý Nginx trước (cảnh báo này sẽ bị chặn).
1. `vagrant ssh web -c "systemctl status demo-app; journalctl -u demo-app -n 50"`.
1. `vagrant ssh web -c "curl -s 127.0.0.1:8000/health"` để gọi thẳng app không qua Nginx.

## Phân biệt báo giả

- Prometheus mất kết nối mạng tới VM web (khi đó có cả TargetDown của job node).

## Xử lý

1. `vagrant ssh web -c "sudo systemctl restart demo-app"`.
1. Nếu lỗi lặp lại: đọc log, kiểm tra `/etc/obslab/demo-app.env`, chạy lại `vagrant provision web`.

## Xác minh & đóng

Target `demo-app` UP trong Prometheus, `curl http://192.168.56.11/health` trả 200.
Ghi kết luận vào sự cố (thật / báo giả + lý do) trước khi đóng (BR-01, BR-04).
