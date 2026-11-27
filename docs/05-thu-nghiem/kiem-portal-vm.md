# Kiểm portal trên VM monitor (GĐ7, 2026-11-27)

Portal (backend GĐ5, frontend GĐ6) đã xong trên Windows với dữ liệu giả. Tài liệu này ghi kết quả triển khai lên VM monitor
và 7 mục phải kiểm với lab thật. Mọi mục **đạt**.

## Triển khai

- 3 container trong Compose của VM monitor (`monitor/docker-compose.yml`, [kiến trúc §2](../02-thiet-ke/kien-truc-portal.md)):
  `portal-db` (PostgreSQL 16, volume riêng), `portal-api` (`portal/backend/Dockerfile`, Python 3.12, có OpenSSH client),
  `portal-web` (`portal/frontend/Dockerfile`: build bằng Node 22, phục vụ bằng Nginx, proxy `/api`).
- Lệnh: `vagrant provision monitor --provision-with monitor` (lần đầu ~8 phút, chủ yếu build ảnh). Cấu hình lấy từ
  `.env`/`.env.example` qua `Vagrantfile` → `/opt/obslab/monitor.env` (chỉ root đọc). Mở: <http://127.0.0.1:18080>.
- `portal-api` khởi động: chép khóa SSH sang `/lab-keys` (quyền 600), chạy migration, rồi chạy uvicorn
  (`portal/backend/docker-entrypoint.sh`).
- **Lỗi gặp khi triển khai:** `runbooks.py` và `fault_ssh.py` tìm thư mục repo bằng `Path(__file__).parents[4]`. Trong
  container code nằm ở `/app/app/...`, không đủ 5 cấp, nên `IndexError` và container khởi động lại liên tục. Đã sửa: rơi về
  `/` khi không đủ cấp (thư mục cấu hình `/runbooks`, `/lab-keys` vẫn được dùng trước).

## Kết quả 7 mục

| # | Mục | Kết quả |
|---|---|---|
| 1 | PostgreSQL | Đạt. 148/148 test trên PostgreSQL 16 (CSDL riêng `portal_test`, xem dưới) |
| 2 | Container | Đạt. 3 container healthy, mount chỉ đọc, chỉ `portal-web` mở cổng |
| 3 | Alertmanager → portal | Đạt. Cảnh báo thật vào CSDL portal, có token, có resolved |
| 4 | Truy vấn Prometheus thật | Đạt. Mọi PromQL trong danh mục có dữ liệu, số khớp Prometheus, độ trễ luật và đồng hồ VM khớp `tools/` |
| 5 | SSH thật từ container | Đạt. Khóa 600, known_hosts, `from=`, giới hạn lệnh; đi ra bằng IP VM monitor |
| 6 | Đối chiếu với CLI | Đạt. Thời gian phát hiện của portal khớp `detection_time.py` tới 0,1 s |
| 7 | Luồng nền | Đạt. Đồng hồ thật (gỡ sau cảnh báo gốc, hết thời gian giữ); khởi động lại container giữa chừng thì gỡ lỗi trên VM |

### 1. PostgreSQL
- Test chạy trong container tạm từ ảnh `portal-api` với repo mount chỉ đọc, CSDL **`portal_test`** tạo riêng trên `portal-db`
  (`PORTAL_TEST_DATABASE_URL`, `tests/conftest.py`). Mỗi test xóa schema và chạy migration lại; conftest từ chối mọi CSDL
  không có tên `*_test`. CSDL `portal` thật không bị đụng (sau khi chạy: 1 user, 0 sự cố như trước).
- 148/148 test qua, gồm migration lên head / so khớp models / hạ về base, BR-01…BR-09 và giá trị liệt kê.
- Index có điều kiện có trên PostgreSQL: `ux_incidents_open_key` (`status <> 'closed'`, BR-08), `ux_fault_runs_active_host`
  (BR-06); 14 ràng buộc CHECK.
- `SELECT … FOR UPDATE` (`services/incidents.py`): phiên thứ hai bị chặn tới `lock_timeout` 1 s (`LockNotAvailable`).

### 2. Container
- `runbooks/` và `.lab-keys/` mount chỉ đọc (`touch` báo Read-only file system); 13/13 runbook nạp vào CSDL.
- Khóa SSH gốc trên thư mục chia sẻ có quyền 777 (ssh sẽ từ chối), bản chép trong container 600, thư mục 700.
- `portal-api` (8000) và `portal-db` (5432) không mở cổng ra ngoài; `portal-web` 8080 → `127.0.0.1:18080` trên Windows.
- Prometheus scrape `/metrics` của portal (`up{job="portal-api"} = 1`); `tools/reload.py` qua.

### 3. Alertmanager → portal
- Route con `alert-recorder` (`continue: true`) rồi `portal`, cùng `group_wait` 5 s; `send_resolved: true`; token Bearer qua
  `credentials_file` (`/opt/obslab/portal-webhook-token`, 0640 root:nogroup, do `provision/monitor.sh` ghi, không có trong git).
- Dừng nginx bằng CLI: NginxDown sau 43,3 s; portal nhận firing 08:57:48.961 (alert-recorder 08:57:48.959), resolved
  08:59:18.963. CSDL portal có đợt cảnh báo, sự cố và dòng thời gian opened → episode_firing → episode_resolved.
- Webhook thiếu token hoặc sai token: 401.

### 4. Truy vấn Prometheus thật
- Mọi chỉ số trong danh mục (`services/monitoring.py`) trả dữ liệu 1 giờ qua: mỗi host 7 chuỗi (CPU, RAM, 3 phân vùng, mạng
  nhận/gửi), postgresql 5, demo-app 6, nginx 5; biểu đồ tổng quan 120–122 điểm.
- CPU, RAM, đĩa `/` trên `/api/overview` khớp truy vấn trực tiếp tới 2 chữ số thập phân; ngưỡng v1 hiện đủ 8, `baselined`.
- Độ trễ đánh giá luật (`/api/v1/rules`): portal 0,001 s = `tools/lib/common.rule_eval_lag()`. Đồng hồ VM lệch monitor
  0,007 s (web), 0,009 s (db); preflight `clean`.

### 5. SSH thật từ container
- `status` tới web và db trả JSON; `id`, `status; id`, `run cpu duration=99999` bị wrapper từ chối.
- sshd trên web ghi `Accepted publickey for obslab-fault from 192.168.56.10`: container đi ra bằng IP VM monitor, nằm trong
  `from="192.168.56.1,192.168.56.10"`. Cùng khóa dùng từ VM web (192.168.56.11) sang db: `Permission denied (publickey)`.

### 6. Đối chiếu với CLI
Ba lần chạy từ portal, sự kiện dựng từ lần chạy của portal và tính lại bằng `tools/detection_time.py` trên log alert-recorder:

| Lần | Kịch bản | Portal: gốc / resolved (s) | `detection_time.py` (s) | CLI trước đây, TB (min–max) |
|---|---|---|---|---|
| #1 | dừng nginx | 43,164 / 57,239 | 43,2 / 57,2 | 43,2 (36,5–47,3), `gd3-dot4` |
| #2 | cpu web | 119,238 / 27,371 | 119,2 / 27,4 | 113,9 (110,5–122,2), `gd3-dot3` |
| #3 | errors web | 85,916 / 57,660 | 85,9 / 57,7 | 85,0 (78,0–97,1), `gd3-dot5` |

- Hai bên dùng chung mốc gây lỗi của portal; phần độc lập là thời điểm nhận (hai receiver, lệch 2 ms) và cách tính.
- Cả 3 lần: hợp lệ, không cảnh báo hệ quả, không nhiễu lúc khôi phục; sự cố được gắn nhãn thử nghiệm (BR-09).
- Lần #1 gộp vào sự cố NginxDown còn mở từ mục 3 (BR-08) và gắn nhãn thử nghiệm cho cả sự cố, đúng quy tắc "giữ lần chạy đầu".

### 7. Luồng nền theo dõi lần chạy
- Đồng hồ thật: gỡ lỗi 32,3–32,8 s sau cảnh báo gốc (`linger` 30 s); `memory db` giữ 30 s không phát hiện → gỡ sau 31,5 s,
  `stop_reason=not_detected`. Độ trễ 1,5–2,8 s là nhịp kiểm của luồng nền cộng một lần SSH.
- Khởi động lại container khi `cpu web` đang chạy (giữ 240 s): API lên lại sau 12 s, `recover_on_startup` gỡ lỗi trên VM
  (`active: False`), lần chạy thành `completed`, `valid=False`, `stop_reason=backend_restarted`, lý do "backend khởi động lại
  giữa chừng". 90 s sau lab sạch, không lần chạy nào treo.

Sau khi kiểm: đã đóng các sự cố thử nghiệm, lab không còn cảnh báo. CSDL `portal_test` để lại trên `portal-db` cho lần chạy
test sau.

## GĐ7: kịch bản lỗi, báo cáo, Grafana

Đối chiếu với lộ trình GĐ7 ("chạy kịch bản lỗi từ portal (chỉ admin), tự tính thời gian phát hiện, xuất báo cáo, link/nhúng
Grafana; kết quả portal khớp với CLI trong sai số đã nêu"):

| Hạng mục | Trạng thái |
|---|---|
| Chạy kịch bản lỗi từ portal, chỉ admin (FR-P13) | Đạt (mục 6, 7). `/api/faults/scenarios` báo `simulated: false` cho cả 6 kịch bản: chạy trên lab thật |
| Tự tính thời gian phát hiện (FR-P14) | Đạt (mục 6) |
| Khớp với CLI trong sai số | Đạt. Lộ trình chưa ghi con số sai số; đề xuất **≤ 1 s** so với `detection_time.py` trên cùng lần chạy (dưới 1/15 chu kỳ scrape). Đo được ≤ 0,05 s (chỉ do làm tròn) |
| Xuất báo cáo CSV, Markdown (FR-P15) | Đạt trên dữ liệu thật: `/api/reports/fault-runs?format=csv|md` trả file tải về (`thoi-gian-phat-hien-<thời điểm>.csv/.md`), 21 cột, đủ lần chạy hợp lệ, không hợp lệ và không phát hiện, kèm lý do |
| Link Grafana (FR-P05) | **Bổ sung.** Trước đây luôn `now-1h`. Nay trang chi tiết máy/dịch vụ mở theo khoảng đang chọn; sự cố mở dashboard của **dịch vụ** (NginxDown → `lab-nginx`, ServiceHighErrorRate → `lab-service`), cảnh báo của máy → `lab-host`, khoảng từ lúc mở − 15 phút tới lúc đóng + 15 phút (chưa đóng: tới hiện tại) |
| Nhúng panel Grafana (FR-P06) | **Bổ sung.** Thẻ "Panel Grafana" ở trang chi tiết máy và dịch vụ, `d-solo` cùng biến và khoảng thời gian, tự làm mới mỗi phút; chọn panel portal không tự vẽ (CPU theo mode, Disk I/O, systemd; UP/DOWN, request theo mã, kết nối Nginx/PostgreSQL) |

- Trên lab thật: link của 3 sự cố và 6 dashboard/panel (`lab-host`, `lab-service`, `lab-nginx`, `lab-postgres`) mở được ẩn
  danh (HTTP 200); Grafana không gửi `X-Frame-Options` nên iframe được phép (ADR-0008).
- Test: backend 149 (thêm link Grafana của sự cố đang mở/đã đóng/của máy), frontend 53 (link theo khoảng thời gian, panel
  nhúng đúng `d-solo`, `panelId`, biến).
- Chưa làm: nhúng panel ở trang chi tiết sự cố (đã có nút mở Grafana đúng khoảng thời gian), ảnh panel phía server cho môi
  trường thật (hạn chế của ADR-0008).

## Chạy lại test với PostgreSQL

```powershell
vagrant ssh monitor -c 'PW=$(sudo grep ^PORTAL_DB_PASSWORD= /opt/obslab/monitor.env | cut -d= -f2-); sudo docker run --rm --network obslab_default -v /vagrant:/repo:ro -w /repo/portal/backend -e PORTAL_TEST_DATABASE_URL="postgresql+psycopg://portal:${PW}@portal-db:5432/portal_test" --entrypoint sh obslab/portal-api:local -c "pip install -q pytest==8.3.4 && python -m pytest -q -p no:cacheprovider"'
```

Lần đầu tạo CSDL: `vagrant ssh monitor -c "sudo docker exec obslab-portal-db psql -U portal -d postgres -c 'CREATE DATABASE portal_test OWNER portal'"`.
