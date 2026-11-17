# Web portal giám sát

Phần nhóm tự phát triển (trọng tâm báo cáo). **Chưa bắt đầu hiện thực** — theo [lộ trình](../docs/lo-trinh.md):
thiết kế ở GĐ4 (tuần 9), backend GĐ5, frontend GĐ6, kịch bản lỗi trong portal GĐ7.

| Thư mục | Công nghệ | Vai trò |
|---|---|---|
| `backend/` | FastAPI, SQLAlchemy + Alembic, PostgreSQL riêng (ADR-0005) | API, xác thực JWT + phân quyền admin/operator, nhận webhook Alertmanager, truy vấn Prometheus, chạy kịch bản lỗi qua SSH giới hạn (ADR-0007) |
| `frontend/` | React + Vite | Giao diện tiếng Việt: tổng quan, chi tiết, cảnh báo/sự cố, runbook, kịch bản lỗi, quản trị |

Chạy trong Compose của VM monitor (ADR-0002). Yêu cầu: [docs/01-phan-tich/yeu-cau.md](../docs/01-phan-tich/yeu-cau.md) (nhóm FR-P).

## Cấu trúc dự kiến

```
backend/
  app/
    api/          # router theo tài nguyên: auth, targets, alerts, incidents, runbooks, faults, reports, webhooks
    core/         # cấu hình (.env), bảo mật (băm mật khẩu, JWT), phân quyền
    models/       # SQLAlchemy
    schemas/      # Pydantic
    services/     # prometheus, alert_ingest, detection, fault_runner, report
  migrations/     # Alembic
  tests/
frontend/
  src/
    api/  components/  pages/  routes/  hooks/
```
