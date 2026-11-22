# apps/demo-web — ứng dụng web demo (VM web)

FastAPI chạy bằng systemd (`demo-app.service`, nghe `127.0.0.1:8000`) sau Nginx :80 trên VM web; cài bởi
[`provision/web.sh`](../../provision/web.sh).

| Endpoint | Mục đích | Truy cập từ ngoài VM |
|---|---|---|
| `GET /health` | Kiểm tra sống (Blackbox probe qua Nginx) | ✅ |
| `GET /api/work` | Endpoint nghiệp vụ giả lập (chịu ảnh hưởng lỗi latency/errors) | ✅ |
| `GET /api/db` | Ghi + đếm bản ghi trong bảng `work_items` trên VM db → tạo tải CSDL thật | ✅ |
| `GET /metrics` | Metric Prometheus: request, latency histogram, lỗi CSDL, trạng thái lỗi giả lập | chỉ VM monitor |
| `GET/POST /admin/fault`, `POST /admin/reset` | Tiêm độ trễ / tỉ lệ lỗi (gọi bởi `faults/` ở GĐ3) | ❌ Nginx trả 403 |

`loadgen.py` (`demo-loadgen.service`) sinh tải nền 2 request/giây qua Nginx: 80% `/api/work`, 10% `/api/db`,
10% `/`.

Cấu hình qua `/etc/obslab/demo-app.env` (quyền 0640, chứa `DATABASE_URL` lấy từ `LAB_DB_*` trong `.env`).
