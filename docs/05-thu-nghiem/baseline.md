# Baseline 24 giờ và ngưỡng v1 (GĐ3)

Đợt đo: **`baseline-24h`**, 2026-11-26 13:53 → 2026-11-27 13:53 (giờ máy, UTC+7), bước 15 s, trên
[máy mẫu](baseline/may-mau-20261127/may.md). Ngưỡng v1 chốt ngày 2026-11-27 trong
[`thresholds.yml`](../../monitor/prometheus/rules/thresholds.yml) (`threshold_status: baselined`), quy trình theo
[ADR-0004](../02-thiet-ke/adr/0004-nguong-canh-bao-dang-recording-rule.md).

Dữ liệu thô: [baseline/may-mau-20261127/](baseline/may-mau-20261127/) (`baseline.md`, `baseline.csv` do
`tools/baseline.py` sinh; `meta.json`; `health.jsonl` sức khỏe lab mỗi 10 phút). Tính lại từ Prometheus (khi TSDB còn
dữ liệu): `python tools/baseline.py --from-state`.

## Cách đo
- `python tools/baseline.py --minutes 1440 --wait --label baseline-24h` theo [hướng dẫn](../04-trien-khai/huong-dan-do-baseline.md).
- Hệ thống chạy bình thường: chỉ có tải nền đều của `loadgen` (`RPS=2`, 80 % vào `/api/work`, 10 % `/api/db`, 10 % `/`).
  Không chạy kịch bản lỗi, không reload/restart thành phần nào trong 24 giờ.
- Thống kê theo từng series (n, min, mean, σ, p50/p90/p95/p99, max), rồi gộp theo chỉ số lấy series khắt khe nhất.

## Chất lượng dữ liệu: sạch

| Tiêu chí | Kết quả |
|---|---|
| Độ phủ mẫu `up{job="node"}` | 100 % cả 3 VM, 0 mẫu down |
| Khoảng trống dài nhất | 15 s (đúng 1 chu kỳ scrape) |
| Vòng đánh giá luật bị lỡ | 0 |
| Prometheus đánh giá luật trễ | tối đa 0,006 s (giới hạn 1 s, [SC-04](../04-trien-khai/xu-ly-su-co.md#sc-04-prometheus-đánh-giá-luật-trễ-sau-khi-đồng-hồ-nhảy)) |
| Mẫu có lỗi giả lập | 0 |
| Cảnh báo bắn với ngưỡng tạm thời | **0** → 0 báo giả trong 24 giờ |

## Mức bình thường

| Chỉ số | TB | p99 | Max | Series khắt khe nhất |
|---|---|---|---|---|
| CPU (%) | 1,2 | 1,9 | 5,7 | web |
| RAM đã dùng (%) | 31,1 | 42,2 | 42,8 | web (42,3 p99) |
| Đĩa đã dùng (%) | 14,0 | 26,4 | 26,4 | monitor `/` |
| Kết nối PostgreSQL (% max) | 2,0 | 2,0 | 3,0 | db |
| Thời gian probe `/health` (s) | 0,003 | 0,005 | 0,034 | web |
| p95 `/api/work` (s) | 0,047 | 0,048 | 0,067 | web |
| Tỉ lệ lỗi `/api/work` | 0 | 0 | 0 | web |
| Lưu lượng `/api/work` (rps) | 1,59 | 1,78 | 1,84 | min 1,22 |

Đĩa gần như không đổi trong 24 giờ (monitor `/` TB 26,2 %, max 26,4 %), nên số liệu này không nói được tốc độ đầy đĩa.

## Theo từng máy

| Máy | Chỉ số | Đơn vị | Trung bình | Cao nhất | Ngưỡng v1 |
|---|---|---|---|---|---|
| **monitor** | CPU | % | 0,8 | 2,6 | > 85 |
|  | RAM đã dùng | % | 30,8 | 34,4 | > 90 |
|  | Đĩa `/` | % | 26,2 | 26,4 | > 90 |
|  | Đĩa `/mnt/labdisk` | % | 7,4 | 7,4 | > 90 |
|  | Mạng nhận | kB/s | 3,32 | 50,80 | — |
|  | Mạng gửi | kB/s | 0,66 | 256,69 | — |
| **web** | CPU | % | 1,6 | 5,7 | > 85 |
|  | RAM đã dùng | % | 38,9 | 42,8 | > 90 |
|  | Đĩa `/` | % | 21,3 | 21,4 | > 90 |
|  | Đĩa `/mnt/labdisk` | % | 7,4 | 7,4 | > 90 |
|  | Mạng nhận | kB/s | 0,84 | 43,43 | — |
|  | Mạng gửi | kB/s | 2,21 | 3,72 | — |
|  | Request `/api/work` | req/s | 1,59 | 1,84 | < 0,6 thì không xét tỉ lệ lỗi |
|  | p95 `/api/work` | ms | 46,6 | 67,5 | > 250 |
|  | Thời gian probe `/health` | ms | 2,8 | 33,5 | > 250 |
|  | Tỉ lệ lỗi 5xx | % | 0,0 | 0,0 | > 5 |
| **db** | CPU | % | 1,1 | 5,3 | > 85 |
|  | RAM đã dùng | % | 23,5 | 27,3 | > 90 |
|  | Đĩa `/` | % | 21,9 | 21,9 | > 90 |
|  | Đĩa `/mnt/labdisk` | % | 7,4 | 7,4 | > 90 |
|  | Mạng nhận | kB/s | 0,64 | 40,90 | — |
|  | Mạng gửi | kB/s | 2,25 | 3,45 | — |
|  | Kết nối PostgreSQL | kết nối (/100) | 2,0 | 3 | > 80 |

Mạng không có ngưỡng cảnh báo; đỉnh mạng gửi của monitor (257 kB/s) là các đợt ngắn, p99 chỉ 8,9 kB/s. `max_connections`
của PostgreSQL là 100, nên số kết nối bằng đúng phần trăm. `/boot` cả 3 máy cố định 11,3 %. Ngưỡng tỉ lệ lỗi chỉ xét khi
lưu lượng ≥ 0,6 req/s.

## Ngưỡng v1

| Ngưỡng (`lab:threshold:*`) | Tạm thời | Cơ học¹ | **v1** | Lý do |
|---|---|---|---|---|
| `host_cpu_usage_percent` | 85 | 6,8 | **85** | Sức chứa: giữ. Mức bình thường cách ngưỡng > 79 điểm % |
| `host_memory_usage_percent` | 90 | 51,4 | **90** | Sức chứa: giữ. Cao nhất 42,8 % |
| `filesystem_usage_percent` | 90 | 31,7 | **90** | Sức chứa: giữ. Cao nhất 26,4 % |
| `postgres_connections_usage_percent` | 80 | 3,6 | **80** | Sức chứa: giữ. Thường 2/100 kết nối |
| `endpoint_probe_duration_seconds` | 2 | 0,040 | **0,25** | Chất lượng dịch vụ, xem dưới |
| `service_latency_p95_seconds` | 1 | 0,081 | **0,25** | Chất lượng dịch vụ, xem dưới |
| `service_error_ratio` | 0,05 | 0 | **0,05** | Baseline không có lỗi nào; giữ theo mục tiêu 95 % request thành công |
| `service_min_request_rate_rps` | 0,2 | 0,61 | **0,6** | ½ lưu lượng thấp nhất, xem dưới |

¹ `tools/baseline.py`: max(p99 + 3σ, max × 1,2) cho ngưỡng trên, min × 0,5 cho ngưỡng dưới. Là mức thấp nhất mà
baseline này không báo giả, chưa phải ngưỡng nên dùng.

**Ngưỡng sức chứa** (CPU, RAM, đĩa, kết nối) giữ nguyên: chúng báo khi sắp hết tài nguyên, không phải khi khác thường.
Hạ xuống gần mức bình thường (vd. CPU 7 %) sẽ báo cả khi tải tăng hợp lệ. Các kịch bản lỗi GĐ3 (stress CPU ~100 %,
lấp đĩa 95 %, chiếm RAM) vẫn vượt ngưỡng rõ ràng.

**Thời gian probe và p95 latency: 0,25 s thay vì 0,04 s / 0,08 s cơ học.**
- Giá trị cơ học chỉ cao hơn max đúng 20 %. Đây là số đo trên một máy, trong 24 giờ yên tĩnh; máy thành viên khác hoặc
  lúc Windows bận có thể dao động hơn mà dịch vụ vẫn tốt. Ngưỡng sát như vậy dễ báo giả.
- 0,25 s là **mốc bucket** của histogram `http_request_duration_seconds` (… 0,1; 0,25; 0,5 …). p95 vượt 0,25 s nghĩa là
  hơn 5 % request chậm hơn 250 ms, không phụ thuộc phép nội suy trong bucket. Ngưỡng 0,081 s nằm giữa bucket 0,05–0,1,
  nên p95 tính ra phụ thuộc cách nội suy hơn là độ trễ thật.
- 0,25 s gấp ~5 lần p95 bình thường (0,047 s) và ~7 lần thời gian probe cao nhất (0,034 s). Người dùng vẫn chưa thấy
  chậm rõ ở mức này, nên báo lúc đó là sớm nhưng không ồn.
- So với tạm thời (2 s, 1 s): phát hiện được độ trễ nhỏ hơn nhiều. Kịch bản `latency` mặc định 3 000 ms vẫn vượt
  ngưỡng; giờ cả `latency_ms` từ ~300 ms cũng bị phát hiện (trước đây cần > 1 000 ms).

**Lưu lượng tối thiểu 0,6 rps** (chỉ dùng để chặn `ServiceHighErrorRate` khi quá ít request): `loadgen` gửi đều
~1,6 rps vào `/api/work` (thấp nhất 1,22). Ở 0,2 rps, cửa sổ 1 phút chỉ có ~12 request, một lỗi lẻ đã là 8 % > 5 %.
Ở 0,6 rps có ≥ 36 request, cần ≥ 2 lỗi mới vượt. Kịch bản `errors` không làm giảm lưu lượng (loadgen gửi theo nhịp, mỗi
request một luồng), nên vẫn được phát hiện.

**Thời gian `for`** (nằm trong `alerts.yml`) giữ nguyên ở v1: baseline không có lần vượt ngưỡng nào để cần lọc thêm.

## Kiểm tra sau khi chốt
- `python tools/reload.py`: promtool kiểm cú pháp (thresholds 8 luật, recording 11, alerts 13), amtool kiểm Alertmanager,
  unit test luật `alerts-nguyen-nhan.test.yml` **SUCCESS**; đã reload Prometheus và Alertmanager ngày 2026-11-27, sau khi đo xong.
- Prometheus trả đủ 8 chuỗi `lab:threshold:*` với `threshold_status="baselined"` và giá trị v1. Ngay sau reload không có
  cảnh báo nào pending hay firing.

## Giới hạn và việc tiếp theo
- **Một máy.** Theo [hướng dẫn](../04-trien-khai/huong-dan-do-baseline.md), thành viên khác đo trên máy mình rồi gửi vào
  `baseline/<tên>-<ngày>/`. Nếu máy nào có mức bình thường gần ngưỡng v1 (đáng chú ý nhất: probe và p95), nhóm xem lại
  và chốt v2.
- **Đã đo lại thời gian phát hiện** với ngưỡng v1 cho `latency web` và `errors web` (`gd3-dot5`, 2026-11-27): 10/10 phát
  hiện, thời gian không đổi so với ngưỡng tạm thời ([chi tiết](thoi-gian-phat-hien.md#đo-lại-với-ngưỡng-v1-gd3-dot5)).
- Theo dõi báo giả khi chạy lâu: trang Ngưỡng của portal có tỉ lệ báo giả, không tính sự cố do kịch bản lỗi (BR-09).
  Báo giả nhiều ở một ngưỡng là dấu hiệu cần đo baseline lại.
