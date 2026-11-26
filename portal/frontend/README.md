# Frontend Obslab Portal (React + Vite)

Giao diện tiếng Việt theo [định hướng giao diện](../../docs/02-thiet-ke/giao-dien.md), gọi API của
[backend](../backend/README.md) theo [openapi.yaml](../../docs/02-thiet-ke/api/openapi.yaml). Biểu đồ: Apache ECharts.
Font Inter đóng gói kèm (chạy được không cần Internet).

## Xem thử trên Windows (backend cục bộ, SQLite, dữ liệu mẫu)

Mở **hai** cửa sổ PowerShell.

```powershell
# Cửa sổ 1 — backend (cổng 8000)
cd portal/backend
$env:PORTAL_PROMETHEUS_URL = "http://127.0.0.1:9"   # cổng đóng: KHÔNG trỏ vào Prometheus của lab
$env:PORTAL_FAULT_BACKGROUND = "false"
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
không thấy menu Quản trị). Không có Prometheus nên các biểu đồ và chỉ số máy hiện "Không đọc được Prometheus"; sự cố,
cảnh báo và thời gian phát hiện TB có dữ liệu mẫu. Nạp lại dữ liệu mẫu: xóa `portal/backend/portal-dev.db` rồi chạy lại
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
| `src/pages/PlaceholderPage.tsx` | component | Trang chưa làm |
| `src/components/*.tsx` | component | Mảnh giao diện dùng lại: menu, thanh công cụ, thẻ, ô KPI, badge, biểu đồ |
| `src/styles/tokens.css` | CSS | Bộ màu, cỡ chữ (biến CSS); nơi duy nhất ghi mã màu |
| `src/styles/app.css` | CSS | Kiểu dùng chung: khung trang, lưới 3 cột, thẻ, bảng, badge |
| `src/format.ts`, `src/types.ts` | TypeScript | Định dạng số/giờ tiếng Việt; kiểu dữ liệu khớp API |
| `src/test/` | test | Vitest + Testing Library; `mockApi.ts` giả backend |

## Tiến độ GĐ6

| Phần | Nội dung | Trạng thái |
|---|---|---|
| 1 | Khung frontend, đăng nhập, tổng quan | ✅ |
| 2 | Sự cố (danh sách, chi tiết, thao tác, runbook) | |
| 3 | Máy & dịch vụ (chi tiết, biểu đồ, Grafana), ngưỡng | |
| 4 | Kịch bản lỗi, báo cáo | |
| 5 | Quản trị (host/service, người dùng, nhật ký) | |
