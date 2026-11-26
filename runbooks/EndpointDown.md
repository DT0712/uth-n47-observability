---
alertname: EndpointDown
title: Endpoint không truy cập được (Blackbox)
severity: critical
category: endpoint
applies_to: [web, db]
status: draft
---

# EndpointDown — Endpoint không truy cập được (Blackbox)

> Bản nháp GĐ2. Hoàn thiện sau khi chạy kịch bản lỗi ở GĐ3 (ghi lại thao tác thực tế đã dùng).

## Ý nghĩa

Blackbox probe HTTP/TCP thất bại liên tục 30 giây (không kết nối được, sai mã HTTP hoặc quá timeout).

Luật không tính khi nguyên nhân đã thấy rõ: Nginx hoặc PostgreSQL down trên cùng host, hoặc demo-app không scrape được
(khi đó chỉ có NginxDown, PostgresDown, ServiceDown). Vì vậy EndpointDown một mình nghĩa là dịch vụ vẫn báo up nhưng người
dùng không vào được, **hoặc** exporter của dịch vụ cũng mất (vd. cả VM chưa khởi động xong).

## Ảnh hưởng

Góc nhìn người dùng: dịch vụ không dùng được.

## Kiểm tra nhanh

1. Nhãn `instance` cho biết endpoint; `service` cho biết dịch vụ.
1. Từ VM monitor: `vagrant ssh monitor -c "curl -sv http://web/health"` hoặc `pg_isready -h db`.

## Phân biệt báo giả

- Thường là hệ quả của NginxDown/ServiceDown/PostgresDown — khi đó cảnh báo này bị inhibit.

## Xử lý

1. Xử lý theo cảnh báo nguyên nhân gốc; nếu chỉ có cảnh báo này thì kiểm tra mạng host-only giữa monitor và VM đích.

## Xác minh & đóng

`probe_success == 1`.
Ghi kết luận vào sự cố (thật / báo giả + lý do) trước khi đóng (BR-01, BR-04).
