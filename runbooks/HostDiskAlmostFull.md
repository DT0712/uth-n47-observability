---
alertname: HostDiskAlmostFull
title: Đĩa của VM gần đầy
severity: warning
category: host
applies_to: [monitor, web, db]
status: draft
---

# HostDiskAlmostFull — Đĩa của VM gần đầy

> Bản nháp GĐ2. Hoàn thiện sau khi chạy kịch bản lỗi ở GĐ3 (ghi lại thao tác thực tế đã dùng).

## Ý nghĩa

Một filesystem (kể cả ổ giả lập `/mnt/labdisk`) dùng quá `lab:threshold:filesystem_usage_percent`.

## Ảnh hưởng

Ghi file thất bại; PostgreSQL có thể dừng ghi; Prometheus mất dữ liệu nếu là đĩa monitor.

## Kiểm tra nhanh

1. Nhãn `mountpoint` của cảnh báo cho biết đĩa nào.
1. `vagrant ssh <vm> -c "df -h; sudo du -xh <mountpoint> --max-depth=1 | sort -h | tail"`.

## Phân biệt báo giả

- `/mnt/labdisk` chỉ là ổ thử nghiệm 512 MB — đầy do kịch bản lỗi `disk` là chủ đích.

## Xử lý

1. Kịch bản `disk`: dừng kịch bản (file lấp đầy sẽ bị xóa).
1. Đĩa hệ thống: xóa log cũ (`journalctl --vacuum-size=100M`), `docker system prune` trên monitor.
1. Monitor: cân nhắc giảm `PROM_RETENTION`.

## Xác minh & đóng

Dung lượng về dưới ngưỡng trên panel *Dung lượng đã dùng*.
Ghi kết luận vào sự cố (thật / báo giả + lý do) trước khi đóng (BR-01, BR-04).
