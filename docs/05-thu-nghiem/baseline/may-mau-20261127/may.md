# Máy đo: máy mẫu (2026-11-26 13:53 → 11-27 13:53)

| Thành phần | Giá trị |
|---|---|
| CPU | Intel Core i7-10750H @ 2,60 GHz (6 nhân, 12 luồng) |
| RAM | 16 GB (Windows báo 15,8 GB) |
| Hệ điều hành | Windows 11 Pro 10.0.22631 |
| VirtualBox / Vagrant | 7.2.22 / 2.4.9 |
| VM | monitor 2 GB, web 1 GB, db 1,5 GB (mặc định của `.env.example`) |
| Tải nền | `loadgen` trên VM web, `RPS=2` (80 % vào `/api/work`) |

Việc bất thường trong lúc đo: không có. Máy không ngủ, không khởi động lại, không chạy kịch bản lỗi. Trong lúc đo có chạy
test và portal giả lập trên Windows, không đụng lab. RAM trống của Windows thấp nhất 1 591 MB (dưới mức khuyến nghị 2 GB),
nhưng Prometheus đánh giá luật trễ tối đa chỉ 0,006 s và không lỡ vòng luật nào (`health.jsonl`, 143 dòng).
