# Yêu cầu chức năng và phi chức năng

> Trạng thái: **bản nháp GĐ0**. Mỗi yêu cầu có mã để truy vết tới thiết kế (GĐ4), mã nguồn và ca kiểm thử (GĐ8).
> Ưu tiên theo MoSCoW (M/S/C). Các con số mục tiêu đánh dấu ⏳ sẽ được **đo rồi mới chốt**, không đặt tuỳ ý.

## 1. Yêu cầu chức năng

### 1.1 Hạ tầng giám sát (lõi — GĐ1–3)

| Mã | Yêu cầu | Ưu tiên |
|---|---|---|
| FR-M01 | Thu thập CPU, RAM, disk, network, uptime của cả 3 VM (Node Exporter) | M |
| FR-M02 | Thu thập metric Nginx (nginx-exporter) và PostgreSQL (postgres-exporter) | M |
| FR-M03 | Kiểm tra endpoint HTTP/TCP từ góc nhìn bên ngoài (Blackbox) | M |
| FR-M04 | Lưu lịch sử metric tối thiểu theo `PROM_RETENTION` (mặc định 15 ngày) | M |
| FR-M05 | Luật cảnh báo: CPU cao, RAM cao, disk gần đầy, service down, endpoint lỗi/chậm, Nginx/PostgreSQL down | M |
| FR-M06 | Ngưỡng tách riêng, có trạng thái provisional/baselined, đổi không cần sửa luật (ADR-0004) | M |
| FR-M07 | Dashboard Grafana: tổng quan, theo host, theo service, Nginx, PostgreSQL — provisioning từ file trong git | M |
| FR-M08 | Kịch bản lỗi trên VM: CPU cao, disk đầy giả lập, dừng service; có thời hạn tự khôi phục | M |
| FR-M09 | Kịch bản bổ sung: endpoint chậm/lỗi, RAM cao | S |
| FR-M10 | Đo baseline N phút và xuất thống kê + giá trị ứng viên ngưỡng | M |
| FR-M11 | Tính thời gian phát hiện từ log alert-recorder, xuất CSV/Markdown (độc lập với portal) | M |
| FR-M12 | Script kiểm tra nhanh toàn bộ lab (target UP, Grafana có dữ liệu) | S |

### 1.2 Web portal (GĐ5–7) — truy vết tới [use case](use-case.md)

| Mã | Yêu cầu | UC | Ưu tiên |
|---|---|---|---|
| FR-P01 | Đăng nhập bằng tài khoản/mật khẩu; phiên dùng JWT có hạn | UC01 | M |
| FR-P02 | Hai vai trò admin/operator; kiểm tra quyền ở **backend** cho mọi API | UC01, UC14 | M |
| FR-P03 | Trang tổng quan: danh sách host/service, UP/DOWN, CPU/RAM/disk/network hiện tại, số cảnh báo đang mở | UC02 | M |
| FR-P04 | Trang chi tiết: biểu đồ lịch sử với khoảng thời gian chọn được (15m, 1h, 6h, 24h, 7d, tuỳ chọn) | UC03 | M |
| FR-P05 | Nút mở dashboard Grafana tương ứng (kèm biến + khoảng thời gian) | UC04 | M |
| FR-P06 | Nhúng panel Grafana trong trang chi tiết | UC04 | S |
| FR-P07 | CRUD host/service được giám sát (tên, loại, ánh xạ nhãn Prometheus, link dashboard) | UC13 | M |
| FR-P08 | Endpoint nhận webhook Alertmanager, lưu bản ghi thô + cập nhật cảnh báo theo fingerprint, idempotent; gắn đợt vào sự cố đang mở cùng (alertname, instance) hoặc tạo sự cố mới (BR-08) | UC12 | M |
| FR-P09 | Danh sách cảnh báo/sự cố có lọc và phân trang; lịch sử đầy đủ | UC05 | M |
| FR-P10 | Xác nhận, ghi chú, đánh dấu báo giả (bắt buộc lý do), đóng sự cố; lưu người và thời điểm | UC06–09 | M |
| FR-P11 | Runbook gắn theo `alertname`, nạp từ `runbooks/*.md`, hiển thị ngay trong màn hình cảnh báo | UC10 | M |
| FR-P12 | Hiển thị ngưỡng hiện hành và trạng thái (đọc từ Prometheus) | UC11 | S |
| FR-P13 | Admin chạy kịch bản lỗi (chọn kịch bản, VM, tham số trong giới hạn); ghi thời điểm gây lỗi/khôi phục | UC16 | M |
| FR-P14 | Tự khớp cảnh báo về với lần chạy kịch bản và tính thời gian phát hiện | UC17 | M |
| FR-P15 | Xuất báo cáo kết quả các lần chạy (CSV, Markdown) | UC18 | S |
| FR-P16 | Quản lý người dùng (tạo, khoá, đổi vai trò) | UC14 | S |
| FR-P17 | Nhật ký thao tác (audit log) cho các hành động thay đổi dữ liệu và chạy kịch bản | — | S |
| FR-P18 | Sửa runbook trên giao diện | UC15 | C |

## 2. Yêu cầu phi chức năng

| Mã | Nhóm | Yêu cầu | Cách kiểm chứng |
|---|---|---|---|
| NFR-01 | Bảo mật | Không có credential thật trong repo; chỉ `.env.example`; `.env`, `.lab-keys/` bị gitignore | Rà soát repo, `git log -p` |
| NFR-02 | Bảo mật | Mật khẩu băm bằng thuật toán chậm (bcrypt/argon2); JWT có hạn (`PORTAL_JWT_EXPIRE_MINUTES`) | Kiểm thử đơn vị, xem CSDL |
| NFR-03 | Bảo mật | Phân quyền kiểm tra ở backend; operator gọi API admin nhận 403 | Kiểm thử API |
| NFR-04 | Bảo mật | SSH gây lỗi bị giới hạn theo ADR-0007; portal không thể chạy lệnh tuỳ ý trên VM | Thử gửi lệnh ngoài danh sách → bị từ chối |
| NFR-05 | Bảo mật | Webhook xác thực bằng token chia sẻ; cổng dịch vụ chỉ bind host-only/127.0.0.1 | Gọi webhook không token → 401 |
| NFR-06 | Tin cậy | Nhận webhook idempotent (gửi lặp không tạo bản ghi trùng); portal lỗi không làm mất dữ liệu đo (ADR-0006) | Gửi lặp payload; tắt portal rồi chạy kịch bản |
| NFR-07 | Tin cậy | Kịch bản lỗi luôn tự khôi phục khi hết hạn, kể cả khi mất kết nối portal | Ngắt mạng giữa chừng, kiểm tra VM |
| NFR-08 | Độ chính xác | Mốc thời gian lưu tới mili-giây, cùng nguồn đồng hồ cho T0 và T1; đồng bộ giờ bằng chrony | Đối chiếu portal với CLI ⏳ (sai lệch chấp nhận chốt ở GĐ7) |
| NFR-09 | Hiệu năng | Trang tổng quan tải trong thời gian chấp nhận được với 3 VM ⏳ | Đo ở GĐ8 |
| NFR-10 | Tài nguyên | Tổng RAM cấp cho 3 VM ≤ 6.5 GB trên máy 16 GB; giám sát không làm quá tải VM được giám sát ⏳ | Đo overhead exporter ở GĐ3 |
| NFR-11 | Tái lập | `vagrant destroy -f && vagrant up` dựng lại toàn bộ lab không cần thao tác tay (trừ tạo `.env`) | Chạy thử trên máy sạch; ghi thời gian dựng ⏳ |
| NFR-12 | Bảo trì | Cấu hình (luật, ngưỡng, dashboard, provisioning) là file trong git; script provisioning idempotent | `vagrant provision` lặp lại không lỗi |
| NFR-13 | Quan sát được | Portal backend tự xuất `/metrics` và được Prometheus giám sát | Target `portal` UP |
| NFR-14 | Khả dụng | Giao diện tiếng Việt, dùng được trên màn hình laptop ≥ 1366 px | Kiểm thử thủ công |
| NFR-15 | Tương thích | Script phía host chạy được trên Windows PowerShell và WSL; Python ≥ 3.10 | Chạy thử cả hai |

## 3. Ràng buộc

- Máy host Windows 16 GB RAM; **Vagrant 2.4.9 + VirtualBox 7.2.22** (phiên bản nhóm đã cài và kiểm thử); Ubuntu 24.04 trên VM.
- Công nghệ: Prometheus, Alertmanager, Grafana, Node Exporter, Blackbox, nginx-exporter, postgres-exporter;
  portal FastAPI + PostgreSQL + React (Vite).
- Không kết nối hệ thống thật; không dữ liệu nhạy cảm.
- Ngưỡng cảnh báo và các mục tiêu ⏳ chỉ chốt sau khi đo.
