---
alertname: EndpointSlow
title: Endpoint phản hồi chậm (Blackbox)
severity: warning
category: endpoint
applies_to: [web]
status: draft
---

# EndpointSlow — Endpoint phản hồi chậm (Blackbox)

> Bản nháp GĐ2. Hoàn thiện sau khi chạy kịch bản lỗi ở GĐ3 (ghi lại thao tác thực tế đã dùng).

## Ý nghĩa

Thời gian probe HTTP vượt `lab:threshold:endpoint_probe_duration_seconds` liên tục 1 phút.

## Ảnh hưởng

Người dùng thấy chậm từ bên ngoài.

## Kiểm tra nhanh

1. Dashboard `lab-service` → *Thời gian probe /health*.
1. So sánh với độ trễ trong app (ServiceHighLatency).

## Phân biệt báo giả

- Kịch bản `latency` (cũng làm chậm /health).

## Xử lý

1. Như ServiceHighLatency.

## Xác minh & đóng

Thời gian probe về dưới ngưỡng.
Ghi kết luận vào sự cố (thật / báo giả + lý do) trước khi đóng (BR-01, BR-04).
