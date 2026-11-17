# tools/ — CLI chạy trên máy Windows host

Chỉ dùng thư viện chuẩn Python (≥ 3.10); chạy được trên PowerShell và WSL.

| Script | Việc làm | Trạng thái |
|---|---|---|
| `check_lab.py` | Kiểm tra mọi target UP, Grafana có dữ liệu, dashboard đủ | ⚠️ đổi URL/target ở GĐ2 |
| `baseline.py` | Đo baseline N phút, xuất thống kê + giá trị ứng viên ngưỡng | ✅ thêm chỉ số Nginx/PostgreSQL ở GĐ3 |
| `detection_time.py` | Tính thời gian phát hiện từ `data/events/faults.jsonl` + `data/alerts/alerts.jsonl` | ✅ |
| `reload.py` | Kiểm tra cú pháp rồi reload Prometheus/Alertmanager | ⚠️ chuyển sang chạy qua `vagrant ssh monitor` ở GĐ2 |
| `fault.py` | Gây lỗi trên VM qua SSH giới hạn | ⏳ viết lại ở GĐ3 (bản Docker đã bỏ) |
| `lib/common.py` | Hàm dùng chung: gọi Prometheus, thống kê, đồng hồ alert-recorder | ✅ |
