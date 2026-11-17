# Runbook xử lý cảnh báo

Mỗi loại cảnh báo có **một file** `runbooks/<AlertName>.md`. Đây là nguồn duy nhất: tài liệu báo cáo liên kết tới
đây, portal nạp các file này vào CSDL (FR-P11), nhãn `runbook` trong luật cảnh báo trỏ tới đây.

Nội dung runbook được viết ở GĐ2–3 cùng với luật cảnh báo cho môi trường 3 VM.

## Định dạng

```markdown
---
alertname: HostHighCpu          # phải trùng tên alert trong monitor/prometheus/rules/alerts.yml
title: CPU host cao
severity: warning               # warning | critical
category: host                  # host | service | endpoint | database | monitoring
applies_to: [web, db, monitor]
---

## Ý nghĩa
Cảnh báo này nói gì, ngưỡng lấy từ đâu (`lab:threshold:...`), điều kiện `for`.

## Ảnh hưởng
Người dùng/dịch vụ bị ảnh hưởng thế nào nếu là thật.

## Kiểm tra nhanh
1. Dashboard / truy vấn PromQL cần xem.
2. Lệnh kiểm tra trên VM (`vagrant ssh <vm>` ...).

## Phân biệt báo giả
- Dấu hiệu cho thấy là báo giả (đột biến ngắn hợp lệ, đang chạy kịch bản lỗi, lỗi exporter, ngưỡng còn provisional...).
- Khi đánh dấu báo giả trên portal, ghi lý do theo mẫu: `<nguyên nhân> — <đề xuất chỉnh ngưỡng/for/luật>`.

## Xử lý
Các bước khắc phục theo thứ tự, kèm lệnh.

## Xác minh & đóng
Dấu hiệu đã ổn định; cần ghi gì vào kết luận sự cố.
```

## Danh sách (dự kiến)

| Alert | Nhóm | GĐ |
|---|---|---|
| HostHighCpu, HostHighMemory, HostDiskAlmostFull, HostDown | host | 2 |
| ServiceDown, EndpointDown, EndpointSlow, ServiceHighErrorRate, ServiceHighLatency | service / endpoint | 2 |
| NginxDown, PostgresDown, PostgresTooManyConnections | service / database | 2 |
| TargetDown, ThresholdConfigMissing | monitoring | 2 |
