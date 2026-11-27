# Đo thời gian phát hiện (GĐ3, phần 3)

Đợt đo chính thức: **`gd3-dot3`**, 2026-11-26 00:39–03:02, 8 trường hợp × 5 lần, với luật cảnh báo trước phương án D.
Đợt kiểm chứng D: **`gd3-dot4`**, 3 trường hợp dừng dịch vụ × 5 lần ([bên dưới](#kiểm-chứng-trên-lab-gd3-dot4)). Hai đợt đo với ngưỡng **tạm thời**.
Ngưỡng v1 ([baseline.md](baseline.md), 2026-11-27) đổi ngưỡng probe, p95 latency và lưu lượng tối thiểu: cần đo lại `latency web`
và `errors web`; các trường hợp còn lại không đổi ngưỡng.

## Cách đo
- `python tools/fault.py suite --id gd3-dot3 --rounds 5`: mỗi vòng đủ 8 trường hợp theo thứ tự ngẫu nhiên; trước mỗi lần chờ
  thêm ngẫu nhiên 0–15 giây để rải pha so với nhịp scrape; gỡ lỗi 30 giây sau khi nhận cảnh báo gốc.
- Mốc 0: giờ VM ngay sau khi thao tác gây lỗi hoàn tất, hiệu chỉnh theo đồng hồ monitor.
- **Phát hiện đầu tiên:** lúc alert-recorder nhận cảnh báo bất kỳ của lỗi. **Cảnh báo gốc:** lúc nhận cảnh báo chỉ đúng nguyên nhân.
- Cấu hình: scrape 15 s, đánh giá luật 15 s, `group_wait` 5 s. Monitor 2 GB, web 1 GB, db 1,5 GB.

Dữ liệu thô và script mô phỏng inhibit (`mo-phong-inhibit.py`): [du-lieu/](du-lieu/README.md). Tính lại bằng `python tools/detection_time.py --suite gd3-dot3` (cần `data/`).

## Kết quả (giây, mỗi dòng 5 lần)

Cả 40 lần hợp lệ, 40/40 phát hiện được và 40/40 có cảnh báo gốc.

| Trường hợp | Cảnh báo gốc | Gốc: min | TB | Trung vị | Max | Độ lệch chuẩn | Đầu tiên: TB |
|---|---|---|---|---|---|---|---|
| dừng nginx | NginxDown | 35,9 | 39,4 | 39,7 | 42,7 | 2,8 | 39,4 |
| dừng demo-app | ServiceDown | 42,0 | 47,0 | 47,7 | 52,2 | 4,0 | 47,0 |
| dừng postgresql | PostgresDown | 51,1 | 53,0 | 52,6 | 56,4 | 2,0 | 53,0 |
| memory db | HostHighMemory | 71,6 | 75,8 | 74,1 | 81,8 | 4,5 | 75,8 |
| disk db | HostDiskAlmostFull | 71,5 | 79,0 | 80,7 | 82,9 | 4,5 | 79,0 |
| latency web | ServiceHighLatency | 78,4 | 82,8 | 83,1 | 89,3 | 4,5 | 80,2 |
| errors web | ServiceHighErrorRate | 85,3 | 89,6 | 87,8 | 94,4 | 3,9 | 89,6 |
| cpu web | HostHighCpu | 110,5 | 113,9 | 112,2 | 122,2 | 4,8 | 113,9 |

Đối chiếu lý thuyết: chờ scrape (0–15) + chờ đánh giá (0–15) + `for` + `group_wait` (5).
- `for: 30s` (các cảnh báo Down): 35–65 s; đo được 35,9–56,4.
- `for: 1m` trên giá trị tức thời (memory, disk): khoảng 65–110 s, vì còn qua recording rule (thêm 0–15 s); đo được 71,5–82,9.
- cpu, errors, latency cộng thêm thời gian để `rate(...[1m])` vượt ngưỡng, nên không có chặn trên đơn giản.

**Từ lúc gỡ lỗi tới khi nhận resolved của cảnh báo gốc:** 27–29 s với cpu, memory, disk; 55–59 s với các trường hợp còn lại,
trừ 2/5 lần dừng postgresql là 85 s. Cảnh báo gốc của nhóm Down cố ý giữ thêm `keep_firing_for: 45s`.

### Thông báo thừa
- Dừng nginx, demo-app, postgresql: **0/15 lần** có cảnh báo hệ quả. Không có nhiễu lúc khôi phục.
- latency web: 5/5 lần nhận cả ServiceHighLatency và EndpointSlow (3 lần EndpointSlow tới trước, 2 lần tới sau). Chưa có
  luật inhibit cho cặp này.

## Chất lượng phép đo

| Kiểm tra | Giá trị | Giới hạn |
|---|---|---|
| Độ trễ đánh giá luật của Prometheus | ≤ 0,005 s | 1 s |
| Lệch đồng hồ VM so với monitor | ≤ 0,092 s (đã hiệu chỉnh) | 0,1 s |
| Mất dữ liệu giám sát | 0 lần | 0 |
| RAM trống của Windows lúc gây lỗi | 2,0–3,4 GB | – |
| RAM monitor dùng | tối đa 30 % của 2 GB, không dùng swap | – |

- Lệch đồng hồ 60–92 ms ở 4 lần trong khoảng 01:31–01:45, các lần khác ≤ 18 ms. Cùng khoảng đó chrony trên monitor và db ghi
  `falseticker` và đổi nguồn NTP. Đây là nguyên nhân có khả năng nhất, chưa chứng minh. Các lần này đã hiệu chỉnh.
- **Phiên đo ảnh hưởng kết quả.** Pha scrape cố định trong một phiên và khác nhau giữa các phiên bật VM, nên độ lệch chuẩn
  trong bảng (một phiên) nhỏ hơn biến động thật. Không so sánh chênh lệch vài giây giữa các loại lỗi.
- n = 5 cho mỗi trường hợp: số trung bình chỉ mang tính mô tả.

## Hai đợt không dùng

| Đợt | Số lần | Lý do |
|---|---|---|
| `gd3-dot1` (2026-11-24) | 40/40 bị loại | Prometheus đánh giá luật trễ 10,44 s sau khi Windows ngủ ([SC-04](../04-trien-khai/xu-ly-su-co.md)): cảnh báo tới muộn thêm 5,4 s, `group_wait` bị bỏ qua, 14/15 lần dừng dịch vụ có cảnh báo hệ quả |
| `gd3-dot2` (2026-11-24) | 7/40, dở dang | Windows khởi động lại đột ngột; 7 lần hợp lệ nhưng không gộp vào `gd3-dot3` (khác phiên, monitor 4 GB) |

## Chỉnh inhibit: phương án D (đã áp dụng 2026-11-26)

Hiện tượng "EndpointDown tới trước NginxDown" có hai nguyên nhân:
1. Lỗi trễ đánh giá luật làm `group_wait` mất tác dụng (SC-04). Đã sửa.
2. **Pha scrape** có thể làm EndpointDown bắn trước cảnh báo gốc hơn 5 s. Chưa sửa.

Khoảng cách (gốc − EndpointDown) tính từ chuỗi `ALERTS`: `gd3-dot3` là 4,45 s hoặc −10,55 s nên đều chặn được; `gd3-dot1` có 3/15 lần
là 19,45 s, dù `group_wait` hoạt động cũng không chặn được. Mức 4,45 s chỉ kém `group_wait` 0,55 s. **Vậy 0/15 của `gd3-dot3`
một phần do pha scrape của phiên này thuận lợi**, không chứng minh cấu hình hiện tại bền vững.

Mô phỏng với pha scrape ngẫu nhiên đều, pha đánh giá luật giữ như thật, 100.000 lần. "Lọt" là có ít nhất một cảnh báo hệ quả
không bị chặn:

| Phương án | dừng nginx | dừng demo-app | dừng postgresql | Cái giá |
|---|---|---|---|---|
| Hiện tại | 20,3 % | 5,8 % | 5,7 % | – |
| A. `EndpointDown for: 1m` | 16,8 % (do ServiceDown) | 0 % | 0 % | Lỗi chỉ ở endpoint báo trễ thêm 30 s |
| B. `group_wait` 25 s cho cảnh báo hệ quả | 0 % | 0 % | 0 % | Lỗi chỉ ở endpoint hoặc app báo trễ thêm 20 s |
| C. Gộp chung rule group | 30,0 % | 16,6 % | 16,5 % | Tệ hơn: chỉ bỏ lệch pha đánh giá |
| **D. Thêm `unless` vào luật (đề xuất)** | 0 % (*) | 0 % (*) | 0 % (*) | Luật phức tạp hơn; không báo trễ thêm |

(*) D không qua mô phỏng này mà suy ra từ lập luận và kiểm tra thử ngược bên dưới.

**D** (nhóm duyệt và áp dụng ngày 2026-11-26): cảnh báo hệ quả không được tính khi nguyên nhân đang thấy rõ; giữ inhibit
hiện tại làm lớp thứ hai. Luật thật nằm trong `monitor/prometheus/rules/alerts.yml` (có thêm bộ lọc `job`):

```yaml
- alert: EndpointDown
  expr: |
    (probe_success{job=~"blackbox-http|blackbox-tcp"} == 0)
      unless on(host) (nginx_up == 0 or pg_up == 0)
      unless on(host, service) (up{job="demo-app"} == 0)
- alert: ServiceDown
  expr: (up{job="demo-app"} == 0) unless on(host) (nginx_up == 0)
```

- **Vì sao đủ:** nguyên nhân hiện ra trong dữ liệu chậm nhất 15 s sau hệ quả, nên biểu thức hệ quả đúng liên tục dưới 15 s, không
  đạt `for: 30s`. Giả định: scrape của nguyên nhân không bị lỡ và exporter của nó vẫn chạy.
- **Thử ngược** trên dữ liệu đã ghi (80 lần của dot1 và dot3), bước 1 s: thời gian dài nhất biểu thức EndpointDown đúng liên tục là
  74–104 s với luật hiện tại và **11 s với D**. ServiceDown vẫn đúng 74–89 s khi dừng demo-app (vẫn báo), và chỉ 4 s khi dừng nginx.
- **Mất exporter của nguyên nhân** thì không có `nginx_up`/`pg_up`, nên EndpointDown vẫn báo như cũ.
- **Unit test** `monitor/prometheus/tests/alerts-nguyen-nhan.test.yml` (`promtool test rules`, chạy tự động trong
  `tools/reload.py`): dừng nginx, dừng postgresql, dừng demo-app (hệ quả tới trước nguyên nhân 1 lần scrape), lỗi chỉ ở
  endpoint (vẫn báo), mất exporter của nguyên nhân (vẫn báo). Luật D qua cả 5; luật cũ trượt 3 test về cảnh báo thừa.

### Kiểm chứng trên lab (`gd3-dot4`)

`python tools/fault.py suite --id gd3-dot4 --rounds 5 --cases "dừng nginx" "dừng demo-app" "dừng postgresql"`,
2026-11-26 12:55–13:45, cùng cách đo như `gd3-dot3`. 15/15 lần hợp lệ: độ trễ đánh giá luật ≤ 0,006 s (riêng 1 lần 0,888 s,
dưới giới hạn 1 s, độ trễ gửi cảnh báo gốc vẫn 5,01 s như mọi lần), lệch đồng hồ ≤ 0,017 s, RAM trống Windows 1,4–3,2 GB.
Bảng trích bằng [`kiem-chung-d.py`](du-lieu/kiem-chung-d.py) (truy vấn `ALERTS` và biểu thức luật trên TSDB) và
`tools/detection_time.py`.

| Trường hợp | Đợt | Thông báo hệ quả | Hệ quả **firing** trong Prometheus | Hệ quả lên pending | Cảnh báo gốc TB (min–max), s |
|---|---|---|---|---|---|
| dừng nginx | trước (`gd3-dot3`) | 0/5 | 5/5 | 5/5 | 39,4 (35,9–42,7) |
| | sau (`gd3-dot4`) | 0/5 | **0/5** | 0/5 | 43,2 (36,5–47,3) |
| dừng demo-app | trước | 0/5 | 5/5 | 5/5 | 47,0 (42,0–52,2) |
| | sau | 0/5 | **0/5** | 5/5 | 47,9 (42,6–54,3) |
| dừng postgresql | trước | 0/5 | 5/5 | 5/5 | 53,0 (51,1–56,4) |
| | sau | 0/5 | **0/5** | 4/5 | 47,4 (43,1–51,9) |

- **Trước D**, thông báo hệ quả bằng 0 chỉ nhờ inhibit và pha scrape thuận lợi; trong Prometheus, EndpointDown (và ServiceDown khi
  dừng nginx) vẫn lên firing ở **15/15** lần, nên vẫn hiện trên trang Alerts của Prometheus và Grafana.
- **Sau D**, không lần nào cảnh báo hệ quả lên firing, nên không còn phụ thuộc pha scrape hay `group_wait`. Biểu thức hệ quả
  đúng liên tục tối đa 10 s (dừng demo-app, postgresql) và 4 s (dừng nginx), dưới `for: 30s`; vì vậy EndpointDown vẫn thoáng
  lên **pending** ở 9/15 lần, không gửi đi đâu.
- **Không làm chậm phát hiện:** cảnh báo gốc vẫn là cảnh báo đầu tiên, mất 36,5–54,3 s, cùng khoảng của `gd3-dot3`. Chênh lệch
  trung bình (+3,8 s nginx, −5,6 s postgresql) nằm trong biến động do pha scrape giữa hai phiên (xem phần Chất lượng phép đo).
- Lúc khôi phục: 0 thông báo nhiễu; resolved của cảnh báo gốc 55,9–58,8 s (1 lần dừng postgresql 85,0 s, giống `gd3-dot3`).
- **Giới hạn đã thấy:** lúc bật lab (12:51, trước đợt đo), db khởi động sau monitor nên probe PostgreSQL hỏng khi exporter
  của PostgreSQL chưa chạy, không có `pg_up`, và EndpointDown vẫn báo 1 lần. Đây đúng là trường hợp "mất exporter" mà D cố ý
  không chặn. Lỗi chỉ ở endpoint mới thử bằng unit test, chưa gây lỗi thật trên lab.

**EndpointSlow và ServiceHighLatency:** không có quan hệ nguyên nhân rõ như trên nên chưa đề xuất inhibit. Xem lại sau baseline.
