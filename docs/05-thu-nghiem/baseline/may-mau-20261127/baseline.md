# Kết quả đo baseline

- Cửa sổ: **2026-11-26 13:53 → 2026-11-27 13:53** giờ máy (24.00 giờ; UTC 2026-11-26T06:53:21.372+00:00 → 2026-11-27T06:53:21.372+00:00), bước 15 s
- Nhãn: baseline-24h
- Mẫu có lỗi giả lập đang bật: **0**
- Vòng đánh giá luật bị lỡ (Windows ngủ/đứng): **0.000**
- Khoảng trống dữ liệu dài nhất: **15 s** (bình thường ≈ 15 s)
- Kết luận: **dữ liệu sạch, dùng được**

## Chất lượng dữ liệu (theo mẫu `up{job="node"}`)

| Máy ảo | Độ phủ mẫu | Mẫu down | Khoảng trống dài nhất (s) |
|---|---|---|---|
| db | 100.00 % | 0 | 15 |
| monitor | 100.00 % | 0 | 15 |
| web | 100.00 % | 0 | 15 |

## Cảnh báo đã bắn trong cửa sổ (ngưỡng hiện hành)

Không có.

Mỗi cảnh báo ở đây là một **báo giả** với ngưỡng hiện hành (không có lỗi giả lập nào).

## Theo từng máy ảo

| Máy ảo | Chỉ số | Series | Đơn vị | TB | p99 | Max | Cơ học |
|---|---|---|---|---|---|---|---|
| monitor | filesystem_usage_percent | instance=monitor,mountpoint=/,job=node | % | 26.229 | 26.394 | 26.400 | 31.680 |
| monitor | filesystem_usage_percent | instance=monitor,mountpoint=/boot,job=node | % | 11.344 | 11.344 | 11.344 | 13.613 |
| monitor | filesystem_usage_percent | instance=monitor,mountpoint=/mnt/labdisk,job=node | % | 7.360 | 7.360 | 7.360 | 8.832 |
| monitor | host_cpu_usage_percent | instance=monitor | % | 0.819 | 1.097 | 2.644 | 3.173 |
| monitor | host_memory_usage_percent | instance=monitor,job=node | % | 30.844 | 32.958 | 34.352 | 41.222 |
| web | endpoint_probe_duration_seconds | instance=http://web/health,service=demo-app,job=blackbox-http | s | 0.003 | 0.005 | 0.034 | 0.040 |
| web | filesystem_usage_percent | instance=web,mountpoint=/,job=node | % | 21.324 | 21.353 | 21.353 | 25.624 |
| web | filesystem_usage_percent | instance=web,mountpoint=/boot,job=node | % | 11.344 | 11.344 | 11.344 | 13.613 |
| web | filesystem_usage_percent | instance=web,mountpoint=/mnt/labdisk,job=node | % | 7.360 | 7.360 | 7.360 | 8.832 |
| web | host_cpu_usage_percent | instance=web | % | 1.594 | 2.051 | 5.701 | 6.841 |
| web | host_memory_usage_percent | instance=web,job=node | % | 38.938 | 42.310 | 42.841 | 51.409 |
| web | service_error_ratio | instance=web,service=demo-app | ratio | 0.000 | 0.000 | 0.000 | 0.000 |
| web | service_latency_p95_seconds | instance=web,service=demo-app | s | 0.047 | 0.048 | 0.067 | 0.081 |
| web | service_request_rate_rps | instance=web,service=demo-app | rps | 1.594 | 1.778 | 1.844 | 0.611 |
| db | filesystem_usage_percent | instance=db,mountpoint=/,job=node | % | 21.909 | 21.911 | 21.911 | 26.293 |
| db | filesystem_usage_percent | instance=db,mountpoint=/boot,job=node | % | 11.344 | 11.344 | 11.344 | 13.613 |
| db | filesystem_usage_percent | instance=db,mountpoint=/mnt/labdisk,job=node | % | 7.360 | 7.360 | 7.360 | 8.832 |
| db | host_cpu_usage_percent | instance=db | % | 1.135 | 1.538 | 5.333 | 6.400 |
| db | host_memory_usage_percent | instance=db,job=node | % | 23.539 | 24.252 | 27.276 | 32.731 |
| db | postgres_connections_usage_percent | instance=db,service=postgresql | % | 2.001 | 2.000 | 3.000 | 3.600 |

## Theo từng chỉ số (gộp mọi series) và ngưỡng gợi ý

| Chỉ số | Đơn vị | Series | Mẫu | TB | p99 | Max | σ | Ngưỡng hiện hành | Cơ học | Ngưỡng gợi ý | Lý do |
|---|---|---|---|---|---|---|---|---|---|---|---|
| host_cpu_usage_percent | % | 3 | 17283 | 1.183 | 1.911 | 5.701 | 0.346 | 85 (provisional) | 6.841 | **85** | giữ: bình thường không chạm (max×1,2 / p99+3σ ≤ ngưỡng hiện hành) |
| host_memory_usage_percent | % | 3 | 17283 | 31.107 | 42.161 | 42.841 | 6.371 | 90 (provisional) | 51.409 | **90** | giữ: bình thường không chạm (max×1,2 / p99+3σ ≤ ngưỡng hiện hành) |
| filesystem_usage_percent | % | 9 | 51849 | 13.953 | 26.350 | 26.400 | 6.824 | 90 (provisional) | 31.680 | **90** | giữ: bình thường không chạm (max×1,2 / p99+3σ ≤ ngưỡng hiện hành) |
| postgres_connections_usage_percent | % | 1 | 5761 | 2.001 | 2.000 | 3.000 | 0.029 | 80 (provisional) | 3.600 | **80** | giữ: bình thường không chạm (max×1,2 / p99+3σ ≤ ngưỡng hiện hành) |
| endpoint_probe_duration_seconds | s | 1 | 5761 | 0.003 | 0.005 | 0.034 | 0.001 | 2 (provisional) | 0.040 | **0.041** | đệm trên mức bình thường; đối chiếu SLO trước khi chốt |
| service_latency_p95_seconds | s | 1 | 5761 | 0.047 | 0.048 | 0.067 | 0.001 | 1 (provisional) | 0.081 | **0.081** | đệm trên mức bình thường; đối chiếu SLO trước khi chốt |
| service_error_ratio | ratio | 1 | 5761 | 0.000 | 0.000 | 0.000 | 0.000 | 0.05 (provisional) | 0.000 | **0.05** | giữ: không có lỗi nào trong baseline, chọn theo SLO |
| service_request_rate_rps | rps | 1 | 5761 | 1.594 | 1.778 | 1.844 | 0.086 | 0.2 (provisional) | 0.611 | **0.611** | một nửa lưu lượng thấp nhất |
| endpoint_probe_success | 0/1 | 3 | 17283 | 1.000 | 1.000 | 1.000 | 0.000 | — |  |  |  |
| host_load1_per_core |  | 3 | 17283 | 0.016 | 0.180 | 0.690 | 0.042 | — |  |  |  |
| host_network_rx_Bps | B/s | 3 | 17283 | 1598.377 | 3518.686 | 50800.396 | 1589.272 | — |  |  |  |
| host_network_tx_Bps | B/s | 3 | 17283 | 1704.514 | 3321.274 | 256694.953 | 3530.865 | — |  |  |  |
| nginx_active_connections |  | 1 | 5761 | 2.043 | 3.000 | 3.000 | 0.220 | — |  |  |  |

## Quy tắc gợi ý

- **Cơ học** = max(p99 + 3σ, max × 1,2) của từng series với ngưỡng trên; min × 0,5 với lưu lượng tối thiểu. Ở bảng
  theo chỉ số lấy series khắt khe nhất (vì mỗi chỉ số chỉ có một ngưỡng chung). Đây là mức thấp nhất mà baseline này
  không báo giả.
- **Sức chứa** (CPU, RAM, đĩa, kết nối PostgreSQL): giữ ngưỡng hiện hành nếu cơ học không vượt nó, ngược lại nâng lên
  cơ học. Không hạ ngưỡng xuống sát mức bình thường: ngưỡng sức chứa báo khi sắp hết tài nguyên, không phải khi khác thường.
  Đĩa gần như không đổi trong 24 giờ, nên phân phối % không nói được tốc độ đầy.
- **Chất lượng dịch vụ** (thời gian probe, p95 latency, tỉ lệ lỗi): cơ học làm tròn lên. Nhóm đối chiếu với SLO; nếu SLO
  thấp hơn mức bình thường thì vấn đề là năng lực hệ thống, không phải ngưỡng.
- Khi đã chốt: sửa `monitor/prometheus/rules/thresholds.yml` (`threshold_status: baselined`, ghi `basis`), chạy
  `python tools/reload.py`, ghi lý do vào `docs/05-thu-nghiem/`.
