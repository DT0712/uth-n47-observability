# Thiết kế API portal (GĐ4, phần 2)

Hợp đồng đầy đủ: [openapi.yaml](openapi.yaml) (OpenAPI 3.1, 35 đường dẫn, 42 thao tác). Backend GĐ5 hiện thực đúng file này
và FastAPI tự sinh tài liệu tương tác tại `/docs`; khi cần đổi API thì sửa file này trước. Kiểm tra cú pháp:

```powershell
python -m venv $env:TEMP\oas; & $env:TEMP\oas\Scripts\pip install -q openapi-spec-validator
& $env:TEMP\oas\Scripts\openapi-spec-validator docs/02-thiet-ke/api/openapi.yaml
```

Xem dạng giao diện: extension *OpenAPI (Swagger) Editor* của VS Code, hoặc `/docs` của backend khi đã chạy.

## 1. Quy ước

| Chủ đề | Quy ước |
|---|---|
| Đường dẫn | Mọi API dưới `/api`, danh từ số nhiều (`/api/incidents`); thao tác nghiệp vụ là động từ con (`/acknowledge`, `/close`) thay vì PATCH trạng thái, để mỗi thao tác có kiểm tra và audit riêng |
| Xác thực | `Authorization: Bearer <JWT>`; webhook dùng token riêng `PORTAL_WEBHOOK_TOKEN` |
| Sửa | `PATCH` là sửa **một phần**: chỉ gửi trường cần đổi; gửi `null` để xóa trường tùy chọn; trường bắt buộc không nhận `null` (422) |
| Thời gian | UTC, ISO-8601, tới mili-giây; client tự đổi sang giờ địa phương |
| Phân trang | `?page=1&page_size=50` (tối đa 200) → `{"items": [...], "total", "page", "page_size"}` |
| Lọc | Tham số query cùng tên trường; nhiều giá trị phân tách bởi dấu phẩy (`?status=open,acknowledged`) |
| Lỗi | `{"error": {"code": "...", "message": "...", "details": [...]}}`; `message` tiếng Việt để hiển thị thẳng, `code` để client xử lý |
| Metric | Client chỉ gửi đối tượng và khoảng thời gian; backend dựng PromQL từ danh sách cố định và tự chọn bước (bội của 15 s) để mỗi series khoảng 120 điểm |
| Tác vụ dài | `POST /api/faults/runs` trả **202** khi đã gây lỗi; client hỏi lại trạng thái mỗi 2–5 s (không dùng WebSocket để giữ đơn giản) |

## 2. Mã lỗi

| HTTP | `error.code` | Khi nào |
|---|---|---|
| 401 | `not_authenticated`, `token_expired`, `invalid_credentials`, `account_disabled`, `invalid_webhook_token` | Thiếu/sai/hết hạn token; đăng nhập sai (thông báo chung, không nói sai tên hay sai mật khẩu) |
| 403 | `forbidden` | Operator gọi API của admin (NFR-03) |
| 404 | `not_found` | Không có đối tượng |
| 409 | `incident_not_open` | Xác nhận khi không ở trạng thái open |
| 409 | `incident_closed` | Ghi chú, báo giả, đóng khi đã đóng |
| 409 | `incident_still_firing` | Đóng khi còn đợt firing và chưa báo giả (BR-01) |
| 409 | `fault_host_busy` | VM đang có lần chạy khác (BR-06) |
| 409 | `fault_vm_refused` | VM từ chối lệnh (vd. dịch vụ đang không chạy nên không dừng được) |
| 409 | `fault_preflight_failed` | `require_clean=true` mà điều kiện đo không đạt |
| 409 | `fault_not_running` | Dừng lần chạy không ở trạng thái running |
| 409 | `self_modification`, `last_admin`, `duplicate` | Tự khóa/tự hạ vai trò; khóa/hạ admin đang hoạt động cuối cùng; trùng tên |
| 422 | `validation_error` | Sai kiểu, ngoài giới hạn (vd. `percent` ngoài 50–97); `details` liệt kê từng trường |
| 503 | `prometheus_unavailable`, `vm_unreachable` | Phụ thuộc không trả lời (timeout 5 s với Prometheus, 15 s với SSH) |

## 3. Ma trận quyền

`operator` dùng được mọi thứ trừ cột admin; `admin` dùng được tất cả. Quyền kiểm ở backend cho từng endpoint (`x-min-role`
trong openapi.yaml), giao diện chỉ ẩn nút.

| Nhóm | operator | admin | Không cần đăng nhập |
|---|---|---|---|
| auth | `GET /api/auth/me`, `POST /api/auth/logout`, `POST /api/auth/password` | | `POST /api/auth/login` |
| users | | `GET/POST /api/users`, `PATCH /api/users/{id}` | |
| inventory | `GET /api/hosts`, `GET /api/hosts/{id}`, `GET /api/services/{id}` | `POST/PATCH/DELETE` host và service | |
| monitoring | `GET /api/overview`, `GET /api/overview/series`, `GET /api/hosts/{id}/metrics`, `GET /api/services/{id}/metrics`, `GET /api/thresholds` | | |
| incidents | `GET /api/incidents`, `GET /api/incidents/{id}`, `POST .../acknowledge`, `.../notes`, `.../false-positive`, `.../close`, `GET /api/alerts` | | |
| runbooks | `GET /api/runbooks`, `GET /api/runbooks/{alertname}` | `POST /api/runbooks/reload` | |
| faults | `GET /api/faults/scenarios`, `GET /api/faults/runs`, `GET /api/faults/runs/{id}` | `GET /api/faults/preflight`, `POST /api/faults/runs`, `POST .../stop`, `GET /api/reports/fault-runs` | |
| system | | `GET /api/audit` | `GET /api/health`, `GET /metrics` (chỉ trong mạng Compose) |
| webhooks | | | `POST /api/webhooks/alertmanager` (token webhook) |

## 4. Truy vết yêu cầu

| Yêu cầu | API |
|---|---|
| FR-P01, FR-P02 | `/api/auth/*`, `x-min-role` mọi endpoint |
| FR-P03 | `GET /api/overview`, `GET /api/overview/series` ([bố cục](../giao-dien.md)) |
| FR-P04 | `GET /api/hosts/{id}/metrics`, `GET /api/services/{id}/metrics` (`range` 15m…7d hoặc `start`/`end`) |
| FR-P05, FR-P06 | `grafana_url` trong host, service, sự cố; nhúng panel do frontend dựng từ `grafana_dashboard_uid` |
| FR-P07 | `/api/hosts`, `/api/services` |
| FR-P08 | `POST /api/webhooks/alertmanager` |
| FR-P09 | `GET /api/incidents`, `GET /api/alerts` |
| FR-P10 | `POST /api/incidents/{id}/acknowledge`, `/notes`, `/false-positive`, `/close` |
| FR-P11 | `runbook` trong chi tiết sự cố, `/api/runbooks/*` |
| FR-P12 | `GET /api/thresholds` |
| FR-P13, FR-P14 | `/api/faults/*` |
| FR-P15 | `GET /api/reports/fault-runs?format=csv\|md` |
| FR-P16 | `/api/users` |
| FR-P17 | `GET /api/audit` (ghi tự động ở mọi thao tác thay đổi) |
| FR-P18 (C) | Chưa thiết kế; để sau |
| NFR-05, NFR-06 | Token webhook; idempotent theo `(fingerprint, startsAt)` và hash payload |
| NFR-13 | `GET /metrics` |

## 5. Ví dụ: màn hình tổng quan

```http
GET /api/overview
Authorization: Bearer eyJhbGciOi...
```

```json
{
  "generated_at": "2026-11-26T07:40:00.000Z",
  "metrics_available": true,
  "hosts": [
    {"id": 2, "name": "web", "up": true, "cpu_percent": 2.3, "memory_percent": 37.5, "disk_percent": 21.3,
     "network_rx_bps": 1580, "network_tx_bps": 4100, "uptime_s": 10820, "open_incidents": 0,
     "grafana_url": "http://localhost:3000/d/lab-host?var-instance=web&from=now-1h&to=now",
     "services": [{"id": 1, "name": "nginx", "up": true, "probe_ok": true, "open_incidents": 0},
                  {"id": 2, "name": "demo-app", "up": true, "probe_ok": true, "open_incidents": 0}]}
  ],
  "open_incidents": {"total": 0, "critical": 0, "warning": 0, "firing": 0},
  "latest_incidents": []
}
```

Khi Prometheus không trả lời: vẫn 200, `metrics_available: false`, các giá trị metric là `null`; số sự cố vẫn đúng vì lấy từ
CSDL. Nhờ vậy portal vẫn dùng được để xử lý sự cố ngay cả khi chính hệ thống giám sát gặp lỗi.
