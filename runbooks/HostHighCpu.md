---
alertname: HostHighCpu
title: CPU của VM cao
severity: warning
category: host
applies_to: [monitor, web, db]
status: draft
---

# HostHighCpu — CPU của VM cao

> Bản nháp GĐ2. Hoàn thiện sau khi chạy kịch bản lỗi ở GĐ3 (ghi lại thao tác thực tế đã dùng).

## Ý nghĩa

CPU trung bình mọi lõi của VM vượt `lab:threshold:host_cpu_usage_percent` liên tục 1 phút.

## Ảnh hưởng

Dịch vụ trên VM phản hồi chậm; nếu kéo dài có thể kéo theo ServiceHighLatency/EndpointSlow.

## Kiểm tra nhanh

1. Dashboard **Lab — Theo VM** (`lab-host`), chọn VM: panel *CPU theo mode* cho biết user/system/iowait.
1. `vagrant ssh <vm> -c "top -b -n1 | head -20"` để xem tiến trình chiếm CPU.
1. Kiểm tra có kịch bản lỗi `cpu` đang chạy không (`stress-ng` trong danh sách tiến trình).

## Phân biệt báo giả

- Tải đột biến ngắn hợp lệ (cài gói, `apt` chạy nền, build Docker trên monitor).
- Ngưỡng còn `provisional` — đối chiếu với baseline trước khi kết luận.

## Xử lý

1. Nếu là kịch bản lỗi: chờ tự khôi phục hoặc dừng kịch bản.
1. Nếu là tiến trình lạ: xác định nguồn gốc, dừng/khởi động lại dịch vụ liên quan.
1. Nếu tải thật tăng lâu dài: ghi nhận để xem xét tăng vCPU trong `.env`.

## Xác minh & đóng

CPU về dưới ngưỡng trên dashboard, Alertmanager gửi `resolved`.
Ghi kết luận vào sự cố (thật / báo giả + lý do) trước khi đóng (BR-01, BR-04).
