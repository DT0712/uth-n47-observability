# Dữ liệu thô các đợt đo thời gian phát hiện

Bản sao từ `data/` và `results/` (không đưa vào git) của từng đợt `python tools/fault.py suite --id <đợt>`.

| File | Nội dung |
|---|---|
| `<đợt>-su-kien.jsonl` | Sự kiện gây lỗi (mỗi lần đo một dòng, trạng thái cuối cùng) |
| `<đợt>-canh-bao.jsonl` | Cảnh báo alert-recorder nhận trong đợt |
| `<đợt>.csv` | Kết quả của `tools/detection_time.py` |

| Đợt | Thời gian | Monitor | Số lần | Dùng được? |
|---|---|---|---|---|
| `gd3-dot1` | 2026-11-24, 14:47–17:31 | 4 GB | 40/40 | **Không.** Prometheus đánh giá luật trễ 10,44 s ([SC-04](../../04-trien-khai/xu-ly-su-co.md)); chỉ giữ làm bằng chứng |
| `gd3-dot2` | 2026-11-24, 17:46–18:11 | 4 GB | 7/40 | Từng lần hợp lệ, nhưng đợt dở dang: Windows khởi động lại đột ngột lúc 18:12 |
| `gd3-dot3` | 2026-11-26, 00:39–03:02 | 2 GB | 40/40 | **Có.** Báo cáo: [thoi-gian-phat-hien.md](../thoi-gian-phat-hien.md) |
