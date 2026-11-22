---
alertname: ServiceHighLatency
title: Độ trễ p95 của demo app cao
severity: warning
category: service
applies_to: [web]
status: draft
---

# ServiceHighLatency — Độ trễ p95 của demo app cao

> Bản nháp GĐ2. Hoàn thiện sau khi chạy kịch bản lỗi ở GĐ3 (ghi lại thao tác thực tế đã dùng).

## Ý nghĩa

p95 thời gian xử lý `/api/work` vượt `lab:threshold:service_latency_p95_seconds`.

## Ảnh hưởng

Người dùng thấy ứng dụng chậm.

## Kiểm tra nhanh

1. Dashboard `lab-service` → *Latency /api/work* (p50/p95/p99).
1. CPU của VM web (HostHighCpu?), PostgreSQL có chậm không.

## Phân biệt báo giả

- Kịch bản `latency` đang chạy (lab_fault_active{fault="latency"} = 1).

## Xử lý

1. Kịch bản lỗi: gọi `/admin/reset` như trên.
1. Tải cao: giảm `RPS` hoặc xem tài nguyên VM.

## Xác minh & đóng

p95 về dưới ngưỡng.
Ghi kết luận vào sự cố (thật / báo giả + lý do) trước khi đóng (BR-01, BR-04).
