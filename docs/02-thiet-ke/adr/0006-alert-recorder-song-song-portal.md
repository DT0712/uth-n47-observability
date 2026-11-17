# ADR-0006: alert-recorder nhận webhook song song với portal

- **Trạng thái:** Chấp nhận — 2026-11-17

## Bối cảnh
Thời gian phát hiện là KPI chính của báo cáo. Nếu chỉ portal nhận webhook thì khi portal lỗi hoặc đang phát triển
sẽ mất dữ liệu đo, và không có gì để kiểm chứng phép tính của portal.

## Quyết định
Alertmanager gửi mọi cảnh báo tới hai receiver:
1. **portal backend** — lưu vào CSDL, phục vụ vòng đời xử lý cảnh báo.
2. **alert-recorder** — service tối giản ghi mỗi cảnh báo thành một dòng JSONL kèm thời điểm nhận (ms).

`tools/detection_time.py` tính thời gian phát hiện từ JSONL, độc lập với portal; ở GĐ7 hai kết quả được đối chiếu.

Về mốc thời gian:
- Kịch bản chạy **từ portal**: thời điểm gây lỗi và thời điểm nhận cảnh báo đều do backend ghi bằng cùng một đồng hồ.
- Kịch bản chạy **từ CLI trên Windows**: CLI hỏi đồng hồ của alert-recorder (`/now`) để quy đổi, loại bỏ lệch giờ
  Windows ↔ VM. Mọi VM chạy chrony.

## Hệ quả
- (+) Dữ liệu đo bền vững, có đối chứng.
- (−) Hai nơi lưu cảnh báo; JSONL chỉ dùng cho đo lường, không phải nguồn sự thật cho xử lý sự cố.
