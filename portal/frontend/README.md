# Frontend Obslab Portal (React + Vite)

Giao diện tiếng Việt theo [định hướng giao diện](../../docs/02-thiet-ke/giao-dien.md), gọi API của
[backend](../backend/README.md) theo [openapi.yaml](../../docs/02-thiet-ke/api/openapi.yaml). Biểu đồ: Apache ECharts.
Font Inter đóng gói kèm (chạy được không cần Internet).

## Xem thử trên Windows (backend cục bộ, SQLite, dữ liệu mẫu)

Mở **hai** cửa sổ PowerShell.

```powershell
# Cửa sổ 1 — backend (cổng 8000)
cd portal/backend
$env:PORTAL_FAKE_PROMETHEUS = "true"               # chế độ xem thử: Prometheus, SSH, cảnh báo đều giả, không đụng lab
Remove-Item Env:PORTAL_FAULT_BACKGROUND -ErrorAction SilentlyContinue  # cần luồng nền để lần chạy kịch bản tiến triển
.venv\Scripts\python -m app.db.migrate
.venv\Scripts\python -m app.dev_seed               # sự cố mẫu, tài khoản op1 / op1-pass-123
.venv\Scripts\python -m uvicorn app.main:app --port 8000

# Cửa sổ 2 — frontend (cổng 5173, tự chuyển /api sang backend)
cd portal/frontend
npm install                                        # lần đầu
npm run dev
start http://localhost:5173
```

Đăng nhập: `admin` / `change-me-lab-only` (mặc định của `.env.example`) hoặc `op1` / `op1-pass-123` (vai trò operator,
không thấy menu Quản trị). `PORTAL_FAKE_PROMETHEUS=true` cho biểu đồ, chỉ số máy và đồng hồ độ trễ số liệu dao động giống
lab (`app/services/fake_prometheus.py`); sự cố, cảnh báo và thời gian phát hiện TB lấy từ dữ liệu mẫu của `app.dev_seed`.
Cùng biến này, trang Kịch bản lỗi chạy **giả lập** (`app/services/fake_faults.py`): không gọi VM, cảnh báo gốc tự tới sau
khoảng thời gian phát hiện đo được ở GĐ3 (vd. dừng nginx ~39 s, CPU ~114 s). Trang hiện nhãn "Chế độ xem thử".
**Không** chạy backend cục bộ mà thiếu biến này rồi bấm Chạy: khi đó backend gọi SSH thật tới VM (trang hiện nhãn đỏ
"Lab thật" và đòi xác nhận).
Muốn xem giao diện khi mất Prometheus: bỏ biến này và đặt `$env:PORTAL_PROMETHEUS_URL = "http://127.0.0.1:9"` (cổng đóng;
không trỏ vào Prometheus của lab). Nạp lại dữ liệu mẫu: xóa `portal/backend/portal-dev.db` rồi chạy lại
hai lệnh migrate và dev_seed. Dừng: `Ctrl+C` ở mỗi cửa sổ.

## Lệnh khác

```powershell
npm test            # test giao diện (Vitest, dữ liệu giả, không cần backend)
npm run build       # kiểm kiểu TypeScript + đóng gói vào dist/
```

## Cấu trúc

| Đường dẫn | Loại | Vai trò |
|---|---|---|
| `index.html` | HTML | Trang duy nhất; React vẽ vào `<div id="root">` |
| `src/main.tsx` | khởi động | Nạp font, CSS, gắn `<App />` |
| `src/App.tsx` | component | Bộ định tuyến + `AuthProvider` |
| `src/routes/index.tsx` | component | Bảng đường dẫn → trang; chặn người chưa đăng nhập, ẩn trang admin |
| `src/auth/AuthContext.tsx` | component | Giữ token (bộ nhớ + sessionStorage) và người đang đăng nhập |
| `src/api/client.ts` | TypeScript | Hàm gọi API chung: gắn token, đổi lỗi JSON thành `ApiError`, 401 thì đăng xuất |
| `src/api/endpoints.ts` | TypeScript | Hàm gọi từng API (`getOverview`, `login`, ...) |
| `src/hooks/usePolling.ts` | hook | Tự gọi lại API mỗi 15 s |
| `src/pages/LoginPage.tsx`, `OverviewPage.tsx` | component | Trang đăng nhập, trang tổng quan |
| `src/pages/FaultsPage.tsx` | component | Kịch bản lỗi: form chạy (admin), lần chạy đang hoạt động, lịch sử, chi tiết lần chạy, xuất CSV/Markdown |
| `src/pages/HostsPage.tsx`, `ThresholdsPage.tsx` | component | Danh sách máy, chi tiết máy, chi tiết dịch vụ (biểu đồ, Grafana, sự cố liên quan); ngưỡng hiện hành |
| `src/pages/IncidentListPage.tsx`, `IncidentDetailPage.tsx`, `RunbookPage.tsx` | component | Danh sách sự cố (lọc, phân trang), chi tiết sự cố (xác nhận, ghi chú, báo giả, đóng, runbook), trang runbook |
| `src/pages/AdminPage.tsx`, `ChangePasswordPage.tsx` | component | Quản trị: máy & dịch vụ (thêm/sửa/xóa), người dùng (thêm, vai trò, khóa, đặt lại mật khẩu), nhật ký thao tác; đổi mật khẩu |
| `src/components/*.tsx` | component | Mảnh giao diện dùng lại: menu, thanh công cụ, thẻ, ô KPI, badge, biểu đồ, hộp thoại (`Dialog`, `Modal`), phân trang, runbook |
| `src/styles/tokens.css` | CSS | Bộ màu, cỡ chữ (biến CSS); nơi duy nhất ghi mã màu |
| `src/styles/app.css` | CSS | Kiểu dùng chung: khung trang, lưới 3 cột, thẻ, bảng, badge |
| `src/styles/incidents.css` | CSS | Nút, hộp thoại, phân trang, dòng thời gian, hiển thị Markdown runbook |
| `src/styles/pages.css` | CSS | Lưới máy, lưới biểu đồ, hàng chỉ số (phần 3–5) |
| `src/format.ts`, `src/types.ts` | TypeScript | Định dạng số/giờ tiếng Việt; kiểu dữ liệu khớp API |
| `src/test/` | test | Vitest + Testing Library; `mockApi.ts` giả backend |

## Tiến độ GĐ6

| Phần | Nội dung | Trạng thái |
|---|---|---|
| 1 | Khung frontend, đăng nhập, tổng quan | ✅ |
| 2 | Sự cố (danh sách, chi tiết, thao tác, runbook) | ✅ |
| 3 | Máy & dịch vụ (chi tiết, biểu đồ, Grafana), ngưỡng | ✅ |
| 4 | Kịch bản lỗi, báo cáo | ✅ |
| 5 | Quản trị (host/service, người dùng, nhật ký), đổi mật khẩu | ✅ |
| bổ sung | Sự cố thử nghiệm (BR-09): nhãn, link tới lần chạy, ô "Ẩn sự cố thử nghiệm"; thẻ tỉ lệ báo giả ở trang Ngưỡng | ✅ |
| GĐ7 | Link Grafana theo khoảng thời gian đang chọn; thẻ "Panel Grafana" nhúng `d-solo` ở chi tiết máy/dịch vụ (`src/grafana.ts`) | ✅ |
