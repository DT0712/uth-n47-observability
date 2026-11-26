# Backend Obslab Portal (FastAPI)

Hiện thực [openapi.yaml](../../docs/02-thiet-ke/api/openapi.yaml) theo [kiến trúc](../../docs/02-thiet-ke/kien-truc-portal.md)
và [ERD](../../docs/02-thiet-ke/erd.md). Phát triển và test trên Windows bằng SQLite + bản giả của Prometheus/SSH; chạy thật
bằng PostgreSQL trong Compose của VM monitor.

## Chạy trên Windows

```powershell
cd portal/backend
python -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt
.venv\Scripts\python -m pytest                     # test tự động, CSDL trong bộ nhớ
.venv\Scripts\python -m app.db.migrate             # tạo portal-dev.db (SQLite)
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
start http://127.0.0.1:8000/api/docs               # tài liệu API tương tác
```

Cấu hình bằng biến môi trường cùng tên với `.env.example` ở gốc repo (`DATABASE_URL`, `PORTAL_JWT_SECRET`, ...);
mặc định đủ để chạy thử. Không dùng mật khẩu thật. Lần khởi động đầu tự tạo admin (`PORTAL_BOOTSTRAP_ADMIN_*`) và 3 VM mẫu
(`PORTAL_SEED_INVENTORY=false` để tắt). Xem thử giao diện không cần lab: `PORTAL_FAKE_PROMETHEUS=true` (Prometheus giả sinh
số) và `python -m app.dev_seed` (sự cố mẫu); hướng dẫn đầy đủ trong [frontend/README.md](../frontend/README.md).

## Cấu trúc

| Đường dẫn | Vai trò |
|---|---|
| `app/main.py` | `create_app()`: tạo app, gắn router, xử lý lỗi, `/metrics` |
| `app/core/config.py` | Đọc cấu hình từ biến môi trường |
| `app/core/errors.py` | `ApiError` và định dạng lỗi `{"error": {code, message, details}}` |
| `app/core/clock.py` | Đồng hồ (UTC, mili-giây); `FakeClock` cho test |
| `app/db/base.py` | Engine, session, kiểu `UTCDateTime` |
| `app/db/models.py` | 11 bảng và ràng buộc theo quy tắc nghiệp vụ |
| `app/db/migrate.py`, `migrations/` | Alembic: tạo và nâng cấp CSDL |
| `app/core/security.py` | bcrypt, tạo/kiểm JWT (hạn kiểm theo `Clock`) |
| `app/api/` | Router theo nhóm API; `deps.py`: phiên CSDL, người dùng hiện tại, `require_operator` / `require_admin` |
| `app/schemas/` | Pydantic cho request/response; `common.py`: phân trang |
| `app/services/` | Nghiệp vụ: `users.py` (admin đầu tiên, quy tắc sửa tài khoản), `audit.py` (nhật ký thao tác), `inventory.py` (3 VM mẫu, link Grafana), `alert_ingest.py` (webhook → đợt → sự cố), `incidents.py` (xác nhận, ghi chú, báo giả, đóng), `runbooks.py` (nạp `runbooks/*.md`), `prometheus.py` (client chỉ đọc, cache 15 s, timeout 5 s), `monitoring.py` (danh mục PromQL, tổng quan, metric, ngưỡng), `fault_catalog.py` (kịch bản, tham số, cảnh báo mong đợi), `fault_ssh.py` (gọi `obslab-fault`), `lab_checks.py` (điều kiện đo), `fault_runner.py` (vòng đời lần chạy, thời gian phát hiện), `reports.py` (CSV, Markdown) |
| `tests/` | pytest; `conftest.py` dựng app với SQLite trong bộ nhớ, đồng hồ giả, sẵn token admin/operator; `test_hop_dong.py` đối chiếu mọi endpoint với openapi.yaml; `fakes.py`: Prometheus, SSH và bộ kiểm điều kiện giả (test không bao giờ gọi lab thật) |

Sửa `app/db/models.py` thì sinh migration mới: `.venv\Scripts\alembic revision --autogenerate -m "mo ta"`.
Test `test_migration_khop_models_va_ha_cap_duoc` báo lỗi nếu quên.

## Luồng cảnh báo và sự cố

```
Alertmanager ──(webhook + token)──► Backend
   1. Ghi giờ nhận (dùng tính thời gian phát hiện)
   2. Bỏ qua nếu là bản gửi trùng
   3. Đợt cảnh báo mới → gắn vào sự cố chưa đóng cùng (tên cảnh báo, instance)
                         (chưa có thì mở sự cố mới; sự cố đã đóng không mở lại)
      Alertmanager nhắc lại đợt đang firing → chỉ cập nhật giờ nhận
      Cảnh báo hết (resolved) → đóng đợt đó

Operator: xác nhận → ghi chú → đóng sự cố (kèm kết luận)
   • Còn đang cảnh báo thì không cho đóng, trừ khi đánh dấu báo giả (bắt buộc có lý do)
   • Mọi thao tác ghi lại ai làm, lúc nào
```

Chi tiết: [sơ đồ tuần tự](../../docs/02-thiet-ke/so-do-tuan-tu.md) luồng 2 và 3; mã: `app/services/alert_ingest.py`,
`app/services/incidents.py`.

## Tiến độ GĐ5

| Phần | Nội dung | Trạng thái |
|---|---|---|
| 1 | Khung dự án, CSDL, migration, `/api/health`, `/metrics` | ✅ |
| 2 | Đăng nhập, phân quyền, người dùng, audit | ✅ |
| 3 | Host/service, dữ liệu mẫu 3 VM | ✅ |
| 4 | Webhook Alertmanager, sự cố, lịch sử cảnh báo | ✅ |
| 5 | Runbook | ✅ |
| 6 | Tổng quan, metric, ngưỡng (client Prometheus) | ✅ |
| 7 | Kịch bản lỗi, thời gian phát hiện, báo cáo (client SSH) | ✅ |
