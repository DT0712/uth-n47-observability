# apps/demo-web — ứng dụng web demo (VM web)

FastAPI chạy bằng systemd sau Nginx trên VM web (GĐ1). Chuyển từ bản Docker một máy.

| Endpoint | Mục đích |
|---|---|
| `GET /health` | Kiểm tra sống (Blackbox probe qua Nginx) |
| `GET /metrics` | Metric Prometheus: request, latency histogram, trạng thái lỗi giả lập |
| `GET /api/work` | Endpoint nghiệp vụ giả lập |
| `POST /admin/fault`, `POST /admin/reset` | Tiêm độ trễ / tỉ lệ lỗi (chỉ nghe trên localhost của VM, gọi qua `faults/`) |

`loadgen.py` sinh tải nền nhẹ để metric luôn có dữ liệu.

GĐ1 sẽ thêm: unit systemd, kết nối PostgreSQL trên VM db (truy vấn thật để có tải CSDL), giới hạn `/admin/*` chỉ
cho localhost.
