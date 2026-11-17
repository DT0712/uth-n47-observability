# ADR-0004: Ngưỡng cảnh báo là recording rule `lab:threshold:*`, chốt sau baseline

- **Trạng thái:** Chấp nhận — 2026-11-17

## Bối cảnh
Đề tài yêu cầu không đặt ngưỡng tuỳ ý trước khi đo baseline. Ngưỡng sẽ được chỉnh nhiều lần; nếu ngưỡng nằm
rải rác trong biểu thức luật thì dễ sót và khó review.

## Quyết định
- Mỗi ngưỡng là một recording rule hằng số trong `monitor/prometheus/rules/thresholds.yml`,
  ví dụ `lab:threshold:host_cpu_usage_percent`, có nhãn `threshold_status` (`provisional`/`baselined`) và `basis`.
- Luật cảnh báo so sánh: `<chỉ số> > on() group_left() lab:threshold:<tên>`.
- Luật `ThresholdConfigMissing` báo khi thiếu chuỗi ngưỡng (tránh luật im lặng vĩnh viễn).
- Dashboard và portal đọc cùng chuỗi ngưỡng để vẽ đường ngưỡng/hiển thị — một nguồn duy nhất.
- Quy trình chốt: đo baseline (`tools/baseline.py`) → nhóm thống nhất → sửa file → `tools/reload.py` → commit.

## Hệ quả
- (+) Đổi ngưỡng không phải sửa luật; lịch sử thay đổi ngưỡng nằm trong git.
- (−) Thời gian `for` không tham số hoá được (giới hạn của Prometheus) → vẫn nằm trong `alerts.yml`.
- (−) Ngưỡng hiện là toàn cục; ngưỡng riêng theo host cần mở rộng thêm nhãn (để sau).
- Portal **chỉ hiển thị** ngưỡng trong phạm vi hiện tại; sửa ngưỡng từ portal là hướng phát triển.
