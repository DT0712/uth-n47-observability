---
alertname: ServiceHighErrorRate
title: Tỉ lệ lỗi 5xx của demo app cao
severity: warning
category: service
applies_to: [web]
status: draft
---

# ServiceHighErrorRate — Tỉ lệ lỗi 5xx của demo app cao

> Bản nháp GĐ2. Hoàn thiện sau khi chạy kịch bản lỗi ở GĐ3 (ghi lại thao tác thực tế đã dùng).

## Ý nghĩa

Tỉ lệ 5xx trên `/api/work` vượt `lab:threshold:service_error_ratio` liên tục 1 phút, khi lưu lượng đủ lớn (`lab:threshold:service_min_request_rate_rps`).

## Ảnh hưởng

Một phần request của người dùng thất bại.

## Kiểm tra nhanh

1. Dashboard **Lab — Demo app** → *Request rate theo mã trạng thái*, panel *Lỗi giả lập đang bật*.
1. `vagrant ssh web -c "curl -s 127.0.0.1:8000/admin/fault"` xem lỗi giả lập.

## Phân biệt báo giả

- Kịch bản `errors` đang chạy (lab_fault_active{fault="errors"} = 1).
- Lưu lượng rất thấp làm tỉ lệ dao động — đã chặn bằng ngưỡng lưu lượng tối thiểu.

## Xử lý

1. Kịch bản lỗi: `vagrant ssh web -c "curl -s -X POST 127.0.0.1:8000/admin/reset"`.
1. Lỗi thật: đọc `journalctl -u demo-app`.

## Xác minh & đóng

Tỉ lệ lỗi về dưới ngưỡng.
Ghi kết luận vào sự cố (thật / báo giả + lý do) trước khi đóng (BR-01, BR-04).
