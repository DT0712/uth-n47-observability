---
alertname: PostgresTooManyConnections
title: PostgreSQL gần hết kết nối
severity: warning
category: service
applies_to: [db]
status: draft
---

# PostgresTooManyConnections — PostgreSQL gần hết kết nối

> Bản nháp GĐ2. Hoàn thiện sau khi chạy kịch bản lỗi ở GĐ3 (ghi lại thao tác thực tế đã dùng).

## Ý nghĩa

Số kết nối / `max_connections` vượt `lab:threshold:postgres_connections_usage_percent` liên tục 1 phút.

## Ảnh hưởng

Kết nối mới bị từ chối khi chạm `max_connections`.

## Kiểm tra nhanh

1. Dashboard **Lab — PostgreSQL** → *Kết nối theo CSDL*.
1. `vagrant ssh db -c "sudo -u postgres psql -c 'select datname,usename,state,count(*) from pg_stat_activity group by 1,2,3'"`.

## Phân biệt báo giả

- Ngưỡng `provisional`; demo app mở kết nối ngắn theo request nên đỉnh nhỏ là bình thường.

## Xử lý

1. Tìm client giữ kết nối `idle` lâu; kết thúc bằng `pg_terminate_backend` nếu cần.
1. Giảm tải nền (`RPS` của demo-loadgen) khi thử nghiệm.

## Xác minh & đóng

Tỉ lệ kết nối về dưới ngưỡng.
Ghi kết luận vào sự cố (thật / báo giả + lý do) trước khi đóng (BR-01, BR-04).
