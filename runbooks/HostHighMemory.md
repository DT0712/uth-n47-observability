---
alertname: HostHighMemory
title: RAM của VM cao
severity: warning
category: host
applies_to: [monitor, web, db]
status: draft
---

# HostHighMemory — RAM của VM cao

> Bản nháp GĐ2. Hoàn thiện sau khi chạy kịch bản lỗi ở GĐ3 (ghi lại thao tác thực tế đã dùng).

## Ý nghĩa

RAM đã dùng (1 − MemAvailable/MemTotal) vượt `lab:threshold:host_memory_usage_percent` liên tục 1 phút.

## Ảnh hưởng

Nguy cơ OOM killer dừng tiến trình (PostgreSQL, Prometheus, demo app).

## Kiểm tra nhanh

1. Dashboard `lab-host` → *RAM chi tiết* (đã dùng, cache, swap).
1. `vagrant ssh <vm> -c "ps aux --sort=-rss | head"`.
1. `vagrant ssh <vm> -c "journalctl -k | grep -i oom"` để xem OOM đã xảy ra chưa.

## Phân biệt báo giả

- Page cache lớn không phải vấn đề (đã được trừ qua MemAvailable).
- Kịch bản lỗi `memory` (stress-ng --vm) đang chạy.

## Xử lý

1. Dừng kịch bản lỗi nếu có.
1. Khởi động lại tiến trình rò rỉ bộ nhớ.
1. Trên monitor: kiểm tra container chiếm RAM bằng `docker stats --no-stream`.

## Xác minh & đóng

RAM về dưới ngưỡng, không có OOM mới trong `journalctl -k`.
Ghi kết luận vào sự cố (thật / báo giả + lý do) trước khi đóng (BR-01, BR-04).
