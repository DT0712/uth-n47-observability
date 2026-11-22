---
alertname: TargetDown
title: Mất một target giám sát
severity: warning
category: monitoring
applies_to: [monitor, web, db]
status: draft
---

# TargetDown — Mất một target giám sát

> Bản nháp GĐ2. Hoàn thiện sau khi chạy kịch bản lỗi ở GĐ3 (ghi lại thao tác thực tế đã dùng).

## Ý nghĩa

Prometheus không scrape được một target (exporter hoặc thành phần giám sát) liên tục 1 phút.

## Ảnh hưởng

Mất dữ liệu giám sát → có thể bỏ sót sự cố. Nếu là `job=node` thì cả VM có thể đã tắt.

## Kiểm tra nhanh

1. http://192.168.56.10:9090/targets xem lỗi cụ thể.
1. `vagrant status` xem VM còn chạy không.
1. `vagrant ssh <vm> -c "systemctl status node_exporter nginx-exporter postgres-exporter"`.

## Phân biệt báo giả

- VM đang được `vagrant halt`/`reload` có chủ đích.

## Xử lý

1. Khởi động lại exporter hoặc VM; `vagrant provision <vm>` nếu cấu hình hỏng.
1. Thành phần trên monitor: `vagrant ssh monitor -c "obslab-compose ps; obslab-compose up -d"`.

## Xác minh & đóng

Target UP trên trang /targets, `python tools/check_lab.py` đạt.
Ghi kết luận vào sự cố (thật / báo giả + lý do) trước khi đóng (BR-01, BR-04).
