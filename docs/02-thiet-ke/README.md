# Thiết kế (GĐ4): Obslab Portal

Bộ thiết kế web portal gửi giảng viên/mentor duyệt (tiêu chí hoàn thành GĐ4 trong [lộ trình](../lo-trinh.md)). Lõi giám sát
(GĐ1–GĐ3) đã chạy và được mô tả trong các ADR; portal là phần nhóm tự phát triển ở GĐ5–GĐ7.

## Đọc theo thứ tự

| # | Tài liệu | Nội dung |
|---|---|---|
| 1 | [kien-truc-portal.md](kien-truc-portal.md) | Bối cảnh, 3 container (`portal-web`, `portal-api`, `portal-db`), mô-đun backend, các quyết định chính, luồng dữ liệu, danh sách màn hình, cấu hình, cách phát triển và kiểm thử trên Windows, bảo mật và hạn chế |
| 2 | [erd.md](erd.md) | 11 bảng, ràng buộc theo quy tắc nghiệp vụ, máy trạng thái sự cố và lần chạy kịch bản lỗi |
| 3 | [api/README.md](api/README.md), [api/openapi.yaml](api/openapi.yaml) | OpenAPI 3.1: 35 đường dẫn, 42 thao tác; quy ước, mã lỗi, ma trận quyền, truy vết yêu cầu |
| 4 | [so-do-tuan-tu.md](so-do-tuan-tu.md) | 6 sơ đồ tuần tự: đăng nhập và phân quyền, nhận webhook, xử lý sự cố, trang tổng quan, chạy kịch bản lỗi, khôi phục khi backend khởi động lại |
| 5 | [giao-dien.md](giao-dien.md) | Định hướng giao diện: phong cách, bộ màu và chữ, khung trang, bố cục màn hình tổng quan và các màn hình khác |
| 6 | [adr/](adr/README.md) | 9 quyết định kiến trúc; liên quan trực tiếp portal: 0005 (CSDL riêng), 0006 (alert-recorder song song), 0007 (SSH giới hạn), 0008 (nhúng Grafana), 0009 (bỏ wireframe) |

Đầu vào: [nghiệp vụ](../01-phan-tich/nghiep-vu.md) (quy tắc BR-01…BR-08), [use case](../01-phan-tich/use-case.md) (UC01–UC18),
[yêu cầu](../01-phan-tich/yeu-cau.md) (FR-P01–FR-P18, NFR-01–NFR-15).

## Tóm tắt thiết kế

- **Vai trò của portal:** công cụ **xử lý cảnh báo** (tiếp nhận, xác nhận, ghi chú, báo giả, đóng sự cố, kèm runbook) và
  **chạy thử nghiệm** (gây lỗi có kiểm soát, tự tính thời gian phát hiện, xuất báo cáo). Không thay Prometheus, Alertmanager
  hay Grafana: metric và ngưỡng vẫn ở Prometheus, portal chỉ đọc.
- **Triển khai:** 3 container trong Docker Compose của VM monitor, cạnh stack giám sát. Cổng chỉ mở cho `127.0.0.1` của máy host.
- **Công nghệ:** FastAPI, SQLAlchemy, Alembic, PostgreSQL 16; React + Vite (TypeScript); Nginx phục vụ giao diện.
- **Bảo mật:** JWT có hạn, bcrypt, 2 vai trò kiểm ở backend cho từng API; webhook dùng token riêng; trình duyệt không gửi
  PromQL; kịch bản lỗi chỉ admin chạy được, qua SSH bị giới hạn chỉ chạy được danh sách lệnh cho phép, mọi thao tác ghi audit.
- **Tin cậy:** webhook idempotent; ràng buộc CSDL chặn sự cố trùng và hai kịch bản trên cùng VM; VM tự gỡ lỗi khi hết hạn;
  backend khởi động lại thì tự kiểm tra và gỡ các lần chạy dở; trang tổng quan vẫn dùng được khi Prometheus lỗi.
- **Đo lường:** thời gian phát hiện tính bằng cùng đồng hồ với alert-recorder và cùng thuật toán với công cụ dòng lệnh đã
  kiểm chứng ở GĐ3, nên đối chiếu được ở GĐ7.
- **Không làm ở phiên bản này:** wireframe (ADR-0009), sửa ngưỡng và sửa runbook trên giao diện, gộp các cảnh báo khác loại
  vào một sự cố, gửi thông báo ra ngoài.

## Điểm cần mentor góp ý

1. Mô hình sự cố: một sự cố cho mỗi `(alertname, instance)`, gộp các đợt lặp lại khi chưa đóng (BR-08) — đủ cho đề tài chưa?
2. Không có wireframe; bố cục chốt trên giao diện thật ở GĐ6 theo [giao-dien.md](giao-dien.md).
3. Portal được phép chạy kịch bản lỗi trực tiếp lên VM (chỉ admin, SSH giới hạn): chấp nhận được về an toàn trong lab chưa?
4. Phạm vi GĐ5–GĐ7 theo ưu tiên M/S/C trong [yêu cầu](../01-phan-tich/yeu-cau.md): có cần cắt bớt không?
