# Định hướng giao diện Obslab Portal

> GĐ4, ghi trước khi code. Frontend GĐ6 làm theo tài liệu này; chi tiết nhỏ (khoảng cách, cỡ chữ chính xác) chốt trên giao
> diện thật ([ADR-0009](adr/0009-bo-wireframe-gd4.md)). Màn hình và dữ liệu: [kiến trúc mục 5](kien-truc-portal.md#5-màn-hình-thay-cho-wireframe), [API](api/README.md).

Tên sản phẩm hiển thị: **Obslab Portal**. Giao diện tiếng Việt, tối ưu cho màn hình ≥ 1366 px (NFR-14).

## 1. Phong cách chung

- **Nền sáng:** trang trắng hoặc xám rất nhạt; nội dung nằm trong các **thẻ (card)** bo góc, nền xám nhạt, không viền đậm,
  nhiều khoảng trắng giữa và trong thẻ.
- **Ít màu, màu có nghĩa:** màu đậm chỉ dùng cho trạng thái (UP/DOWN, mức độ) và mục menu đang chọn. Ô KPI dùng màu pastel.
- **Font không chân**, chữ xám đậm; tiêu đề thẻ cỡ vừa, nhãn phụ nhỏ và xám nhạt hơn; số liệu quan trọng cỡ to.
- **Icon nét mảnh** (bộ `lucide-react`, nét 1,5 px), một màu theo ô chứa nó.
- Chỉ có giao diện sáng ở phiên bản này.

## 2. Bộ màu và chữ (design tokens)

Khai báo thành biến CSS trong một file duy nhất (`src/styles/tokens.css`); component không ghi mã màu trực tiếp.

| Token | Giá trị | Dùng cho |
|---|---|---|
| `--bg-page` | `#F7F8FA` | Nền trang |
| `--bg-card` | `#F1F3F5` | Nền thẻ |
| `--bg-surface` | `#FFFFFF` | Thanh menu, ô nhập, bảng bên trong thẻ |
| `--text` | `#1F2933` | Chữ chính |
| `--text-muted` | `#6B7280` | Nhãn phụ, chú thích, trục biểu đồ |
| `--line` | `#E4E7EB` | Lưới biểu đồ, đường kẻ bảng |
| `--nav-active` | `#1C2B3A` | Nút viên thuốc của mục menu đang chọn (chữ trắng) |
| `--radius-card` / `--radius-pill` | `12px` / `999px` | Bo góc thẻ / nút viên thuốc, chip, badge |

**Ô KPI pastel** (nền / icon):

| Tên | Nền | Icon |
|---|---|---|
| Cam đào | `#FDEBDD` | `#D9692F` |
| Tím nhạt | `#EEEAFB` | `#7356D6` |
| Hồng | `#FCE8EF` | `#C9416F` |
| Xanh dương nhạt | `#E3EEFB` | `#2D6CD2` |
| Xanh bạc hà | `#DDF3EA` | `#1E8F6A` |

**Trạng thái và mức độ** (badge viên thuốc, chữ trắng, luôn kèm chữ chứ không chỉ màu):

| Nhãn hiển thị | Giá trị dữ liệu | Màu |
|---|---|---|
| Nghiêm trọng | `severity=critical` | đỏ `#D93636` |
| Cao | `severity=warning` | cam `#E07B1F` |
| Thấp | `severity=info` | xanh ngọc `#12A39A` |
| UP / Online | `up=true` | xanh lá `#2E9E52` |
| DOWN | `up=false` | đỏ `#D93636` |
| Không rõ | `null` (mất dữ liệu) | xám `#9AA3AE` |

Các luật hiện có chỉ dùng `critical` và `warning`; `info` để sẵn.

**Màu đường biểu đồ:** `#2D6CD2`, `#7356D6`, `#12A39A`, `#E07B1F` theo thứ tự; đường ngưỡng nét đứt màu đỏ nhạt.

**Chữ:** font `Inter` (hỗ trợ đầy đủ tiếng Việt, đóng gói kèm frontend để chạy được khi không có Internet), dự phòng
`system-ui, "Segoe UI", sans-serif`. Cỡ: 13 px nhãn phụ, 14 px nội dung, 16 px tiêu đề thẻ (đậm vừa 600), 24–28 px số KPI.

## 3. Khung trang

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ Obslab Portal   (Tổng quan) Máy & dịch vụ  Sự cố  Runbook  Kịch bản lỗi  Ngưỡng  Quản trị  [ND] │  thanh menu ngang
├────────────────────────────────────────────────────────────────────────────────────────┤
│ Tổng quan › Toàn bộ lab                                                   [ 1 giờ  ▾ ]  │  breadcrumb, khoảng thời gian
│ (Máy: web ✕) (Dịch vụ: nginx ✕)  (+ Lọc)                                               │  chip lọc
├──────────────────────────┬───────────────────────────────┬─────────────────────────────┤
│ cột trái                 │ cột giữa                      │ cột phải                    │  lưới 3 cột
└──────────────────────────┴───────────────────────────────┴─────────────────────────────┘
```

- **Thanh menu ngang** trên cùng, nền trắng: tên "Obslab Portal" bên trái, các mục ở giữa, **mục đang chọn là nút viên thuốc
  nền `--nav-active` chữ trắng**. Mục chỉ dành cho admin (Quản trị) ẩn với operator. Góc phải: ô người dùng tròn (chữ cái đầu
  của tên), bấm ra menu: tên, vai trò, đổi mật khẩu, đăng xuất.
- **Dưới menu:** breadcrumb bên trái; **ô chọn khoảng thời gian** góc phải (1 giờ, 6 giờ, 24 giờ; trang chi tiết thêm 15 phút,
  7 ngày, tùy chọn); hàng **chip lọc** chọn máy/dịch vụ, chip có nút ✕ để bỏ. Bộ lọc và khoảng thời gian nằm trên URL
  (`?host=web&range=1h`) để chia sẻ link và giữ khi tải lại.
- **Lưới 3 cột** khi rộng ≥ 1366 px (tỉ lệ khoảng 1 : 1,1 : 1); dưới 1366 px còn 2 cột, cột phải xuống dưới. Khoảng cách
  giữa thẻ 16 px, đệm trong thẻ 16–20 px.

## 4. Màn hình tổng quan

| Cột | Thẻ | Nội dung | Dữ liệu |
|---|---|---|---|
| Trái | **Hàng ô KPI** (2 hàng × 3 ô) | Mỗi ô: icon nét mảnh, nhãn nhỏ, số to. Bấm vào ô thì sang trang lọc sẵn | `GET /api/overview` |
| | ↳ Máy đang giám sát (xanh dương nhạt) | Số host đang bật | `hosts` |
| | ↳ Máy DOWN (hồng) | Số host `up=false`; 0 thì hiện "Không có" | `hosts[].up` |
| | ↳ Cảnh báo đang firing (cam đào) | | `open_incidents.firing` |
| | ↳ Sự cố đang mở (tím nhạt) | | `open_incidents.total` |
| | ↳ Kịch bản lỗi đang chạy (xanh bạc hà) | 0 thì hiện "Không có" | `faults_running` |
| | ↳ Thời gian phát hiện TB (cam đào) | Giây, các lần chạy hợp lệ 24 giờ qua; chưa có thì "—" | `detection_mean_s` |
| | **Dịch vụ** | Mỗi dịch vụ một dòng: icon tròn, tên, chấm trạng thái + chữ "Online"/"DOWN", uptime % trong khoảng thời gian, máy chạy nó | `hosts[].services[]`, `GET /api/overview/series` |
| | **Độ trễ** | Đồng hồ bán nguyệt: p95 latency của demo-app, thời gian probe từng endpoint. Vạch màu theo ngưỡng hiện hành (xanh < 50 % ngưỡng, cam < 100 %, đỏ ≥ ngưỡng) | `GET /api/overview/series`, `GET /api/thresholds` |
| Giữa | **CPU**, **RAM** | Biểu đồ đường mảnh (1,5 px), mỗi máy một đường; trục và lưới nhạt; đường ngưỡng nét đứt; chú thích nhỏ phía dưới | `GET /api/overview/series` |
| | **Request** | Request/giây của demo-app | như trên |
| | **Độ trễ theo thời gian** | p95 latency, thời gian probe | như trên |
| Phải | **Sự cố theo mức độ** | Donut (Nghiêm trọng / Cao / Thấp) với tổng ở giữa; bên cạnh là danh sách cảnh báo nhiều sự cố nhất kèm badge và số lượng | `GET /api/incidents` (khoảng thời gian đang chọn) |
| | **Sự cố hiện tại** | Bảng: badge mức độ, tên cảnh báo, máy, trạng thái xử lý, mở lúc; bấm dòng sang chi tiết | `latest_incidents` |
| | **Tình trạng máy chủ** | Bảng: máy, badge UP/DOWN, CPU/RAM/đĩa %, uptime | `hosts[]` |
| | **Cảnh báo hiện tại** | Bảng các đợt đang firing: badge, tên, instance, firing từ | `GET /api/alerts?status=firing` |

- Tự làm mới mỗi 15 s (bằng chu kỳ scrape); có nút làm mới tay. Khi `metrics_available=false`: các thẻ biểu đồ và đồng hồ hiện
  "Không đọc được Prometheus", các thẻ sự cố vẫn hoạt động.
- Chip lọc máy/dịch vụ lọc mọi thẻ trên trang.

## 5. Màn hình khác

Dùng cùng khung (menu, breadcrumb, chip, khoảng thời gian) và cùng thẻ:

| Màn hình | Bố cục |
|---|---|
| Đăng nhập | Một thẻ giữa trang trên nền `--bg-page`: tên Obslab Portal, ô tên đăng nhập, mật khẩu, nút viên thuốc `--nav-active` |
| Máy & dịch vụ (chi tiết) | Hàng ô KPI của máy (CPU, RAM, đĩa, mạng, uptime); lưới biểu đồ 2 cột; thẻ dịch vụ con; thẻ sự cố liên quan; nút "Mở Grafana" |
| Sự cố (danh sách) | Chip lọc trạng thái/mức độ/máy/cảnh báo; một thẻ bảng rộng, phân trang |
| Sự cố (chi tiết) | 2 cột: trái là thông tin + các đợt cảnh báo + dòng thời gian + nút thao tác (Xác nhận, Ghi chú, Báo giả, Đóng); phải là runbook |
| Runbook | Danh sách bên trái, nội dung Markdown bên phải |
| Kịch bản lỗi | Thẻ form chạy (admin); thẻ lần chạy đang hoạt động với đồng hồ đếm và các cảnh báo đã nhận; bảng lịch sử với thời gian phát hiện; nút xuất CSV/Markdown |
| Ngưỡng | Bảng: tên, giá trị, badge provisional/baselined, cơ sở |
| Quản trị | Tab: Máy & dịch vụ, Người dùng, Nhật ký thao tác; mỗi tab một thẻ bảng + form trong hộp thoại |

## 6. Thành phần dùng lại

`AppHeader` (menu viên thuốc, ô người dùng), `PageToolbar` (breadcrumb, chip, khoảng thời gian), `Card`, `KpiTile`,
`StatusBadge`, `SeverityBadge`, `LineChartCard`, `GaugeCard`, `DonutCard`, `DataTable`, `EmptyState`, `ErrorState`.
Thư viện biểu đồ chốt ở GĐ6 (ứng viên: Recharts); tiêu chí: đường mảnh, tùy biến trục/lưới, có donut và vẽ được bán nguyệt.

## 7. Khả năng tiếp cận

- Màu không phải kênh duy nhất: badge luôn có chữ, chấm trạng thái kèm chữ "Online"/"DOWN".
- Tương phản chữ trên nền ≥ 4,5 : 1 (chữ trắng trên badge màu đậm; chữ `--text` trên nền pastel).
- Điều hướng được bằng bàn phím; ô focus có viền rõ.

## 8. API cần bổ sung cho bố cục này

Đã thêm vào [openapi.yaml](api/openapi.yaml):
- `Overview.faults_running`, `Overview.detection_mean_s`.
- `GET /api/overview/series?range=1h|6h|24h&host=&service=`: chuỗi thời gian gộp cho cột giữa và thẻ độ trễ/uptime, một lần
  gọi thay vì mỗi biểu đồ một lần (nhẹ cho Prometheus, cache 15 s).
- Tham số lọc `host`, `service` cho `GET /api/overview`.
