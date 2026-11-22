# Runbook xử lý cảnh báo

Mỗi loại cảnh báo có **một file** `runbooks/<AlertName>.md`. Đây là nguồn duy nhất: tài liệu báo cáo liên kết tới
đây, portal nạp các file này vào CSDL (FR-P11), nhãn `runbook` trong luật cảnh báo trỏ tới đây.

GĐ2 đã có bản nháp (`status: draft`) cho cả 13 cảnh báo; GĐ3 hoàn thiện sau khi chạy kịch bản lỗi thật.

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

## Danh sách

| Alert | Nhóm | Trạng thái |
|---|---|---|
| [HostHighCpu](HostHighCpu.md), [HostHighMemory](HostHighMemory.md), [HostDiskAlmostFull](HostDiskAlmostFull.md) | host | nháp |
| [ServiceDown](ServiceDown.md), [NginxDown](NginxDown.md), [PostgresDown](PostgresDown.md), [PostgresTooManyConnections](PostgresTooManyConnections.md) | service | nháp |
| [ServiceHighErrorRate](ServiceHighErrorRate.md), [ServiceHighLatency](ServiceHighLatency.md) | service | nháp |
| [EndpointDown](EndpointDown.md), [EndpointSlow](EndpointSlow.md) | endpoint | nháp |
| [TargetDown](TargetDown.md), [ThresholdConfigMissing](ThresholdConfigMissing.md) | monitoring | nháp |

"Mất cả VM" được phát hiện bằng TargetDown với `job=node` (luật inhibit chặn các cảnh báo khác trên VM đó).
