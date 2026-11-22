---
alertname: ThresholdConfigMissing
title: Thiếu chuỗi ngưỡng cảnh báo
severity: warning
category: monitoring
applies_to: [monitor]
status: draft
---

# ThresholdConfigMissing — Thiếu chuỗi ngưỡng cảnh báo

> Bản nháp GĐ2. Hoàn thiện sau khi chạy kịch bản lỗi ở GĐ3 (ghi lại thao tác thực tế đã dùng).

## Ý nghĩa

Ít nhất một chuỗi `lab:threshold:*` không tồn tại — luật cảnh báo dùng nó sẽ không bao giờ kích hoạt.

## Ảnh hưởng

Hệ thống im lặng giả: có sự cố mà không báo.

## Kiểm tra nhanh

1. `python tools/reload.py --check-only`.
1. http://192.168.56.10:9090/rules xem nhóm `lab-thresholds`.

## Phân biệt báo giả

- Không có — luôn cần xử lý.

## Xử lý

1. Khôi phục tên/biểu thức trong `monitor/prometheus/rules/thresholds.yml`, chạy `python tools/reload.py`.

## Xác minh & đóng

Truy vấn `{__name__=~"lab:threshold:.*"}` trả đủ số chuỗi; cảnh báo resolved.
Ghi kết luận vào sự cố (thật / báo giả + lý do) trước khi đóng (BR-01, BR-04).
