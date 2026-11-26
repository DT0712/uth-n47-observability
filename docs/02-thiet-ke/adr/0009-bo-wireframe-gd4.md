# ADR-0009: Bỏ wireframe khỏi thiết kế portal GĐ4

- **Trạng thái:** Chấp nhận — 2026-11-26

## Bối cảnh
Lộ trình GĐ4 gồm kiến trúc, ERD, API (OpenAPI), sơ đồ tuần tự và wireframe. Thời gian còn lại bị nén: phần portal
(GĐ4–GĐ7) chiếm khoảng một nửa khối lượng đề tài và nhóm muốn bắt đầu code trong lúc chờ baseline 24 giờ.

## Quyết định
- Không làm wireframe. Thiết kế GĐ4 gồm: [kiến trúc](../kien-truc-portal.md), [ERD](../erd.md), API OpenAPI và sơ đồ tuần tự.
- Thay wireframe bằng **bảng màn hình** trong tài liệu kiến trúc (mục 5): mỗi màn hình có vai trò được dùng, nội dung
  chính và use case/yêu cầu truy vết. Bố cục chi tiết quyết định khi code frontend (GĐ6) và được duyệt trên giao diện thật.

## Hệ quả
- (+) Bắt đầu code sớm hơn; không duy trì hai bản giao diện (wireframe và code) lệch nhau.
- (−) Mentor duyệt bố cục muộn hơn, trên giao diện thật; sửa bố cục lúc đó tốn công hơn sửa wireframe.
- (−) Báo cáo không có hình wireframe; thay bằng ảnh chụp màn hình portal ở GĐ6–GĐ8.

## Phương án đã cân nhắc
- Wireframe HTML tĩnh bấm được: dễ trình bày nhưng tốn thời gian và phải làm lại khi code React.
- Phác thảo ASCII trong Markdown: nhanh nhưng khó đọc, giá trị trình bày thấp.
