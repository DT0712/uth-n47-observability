# tools/ — CLI chạy trên máy Windows host

Chỉ dùng thư viện chuẩn Python (≥ 3.10); chạy được trên PowerShell và WSL. Gọi stack qua `http://<VM_MONITOR_IP>:<cổng>`
(mặc định `192.168.56.10`); ghi đè bằng biến môi trường `PROM_URL`, `AM_URL`, `GRAFANA_URL`, `WEBHOOK_URL`.

| Script | Việc làm | Trạng thái |
|---|---|---|
| `check_lab.py` | Mọi target UP (đủ 3 VM), đủ ngưỡng/luật, Grafana có dữ liệu + đủ 5 dashboard; `--test-alert` gửi cảnh báo thử tới alert-recorder | ✅ |
| `baseline.py` | Đo baseline N phút, xuất thống kê + giá trị ứng viên ngưỡng | ✅ thêm chỉ số Nginx/PostgreSQL ở GĐ3 |
| `detection_time.py` | Tính thời gian phát hiện từ `data/events/faults.jsonl` + `data/alerts/alerts.jsonl`; loại lần bị ngắt, mất dữ liệu, luật đánh giá trễ. Test: `python -m unittest discover -s tools/tests` | ✅ |
| `reload.py` | promtool/amtool + unit test luật `monitor/prometheus/tests/` (qua `vagrant ssh monitor`) rồi reload Prometheus/Alertmanager | ✅ |
| `check_fault_ssh.py` | Kiểm tra giới hạn SSH của user `obslab-fault`; `--scenarios` chạy thật từng kịch bản | ✅ |
| `fault.py` | Gây lỗi trên VM qua SSH giới hạn, ghi sự kiện vào `data/events/faults.jsonl`; `list`, `status`, `run`, `suite` (`--cases` để chọn trường hợp), `recover` | ✅ |
| `lib/faultssh.py` | Gọi `obslab-fault` qua SSH bị giới hạn (khóa, known_hosts, quyền file trên Windows/WSL) | ✅ |
| `lib/common.py` | Hàm dùng chung: gọi Prometheus, thống kê, đồng hồ alert-recorder | ✅ |
