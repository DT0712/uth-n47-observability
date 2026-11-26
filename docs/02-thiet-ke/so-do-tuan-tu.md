# Sơ đồ tuần tự portal (GĐ4, phần 3)

Các luồng chính giữa trình duyệt, backend (`portal-api`), CSDL (`portal-db`), Prometheus, Alertmanager và VM lab. Tên API
theo [openapi.yaml](api/openapi.yaml); bảng và ràng buộc theo [erd.md](erd.md); quyết định theo [kiến trúc](kien-truc-portal.md).

| # | Luồng | Use case / quy tắc |
|---|---|---|
| 1 | [Đăng nhập và gọi API có phân quyền](#1-đăng-nhập-và-gọi-api-có-phân-quyền) | UC01, FR-P01–02, NFR-02–03 |
| 2 | [Nhận webhook cảnh báo](#2-nhận-webhook-cảnh-báo) | UC12, FR-P08, BR-03, BR-08, NFR-05–06 |
| 3 | [Operator xử lý sự cố](#3-operator-xử-lý-sự-cố) | UC05–UC10, BR-01, BR-02, BR-04 |
| 4 | [Trang tổng quan](#4-trang-tổng-quan) | UC02, UC11, FR-P03 |
| 5 | [Admin chạy kịch bản lỗi và tính thời gian phát hiện](#5-admin-chạy-kịch-bản-lỗi-và-tính-thời-gian-phát-hiện) | UC16–UC17, BR-05–07, NFR-07–08 |
| 6 | [Backend khởi động lại khi đang chạy kịch bản](#6-backend-khởi-động-lại-khi-đang-chạy-kịch-bản) | NFR-07 |

## 1. Đăng nhập và gọi API có phân quyền

```mermaid
sequenceDiagram
  autonumber
  actor U as Operator/Admin
  participant FE as Trình duyệt (React)
  participant API as portal-api
  participant DB as portal-db

  U->>FE: Nhập tên đăng nhập, mật khẩu
  FE->>API: POST /api/auth/login
  API->>DB: Tìm user theo username
  alt Sai mật khẩu, không có user hoặc bị khóa
    API->>DB: audit_log login_failed
    API-->>FE: 401 invalid_credentials (chờ 1 s, thông báo chung)
  else Đúng
    API->>DB: Cập nhật last_login_at, audit_log login
    API-->>FE: 200 access_token (JWT, hạn 60 phút), user, vai trò
    FE->>FE: Lưu token trong bộ nhớ và sessionStorage
  end

  U->>FE: Mở một trang
  FE->>API: GET /api/... (Authorization Bearer)
  API->>API: Kiểm chữ ký và hạn JWT
  API->>DB: Đọc user (is_active, role hiện tại)
  alt Token sai/hết hạn hoặc user bị khóa
    API-->>FE: 401
    FE->>U: Về trang đăng nhập
  else Vai trò thấp hơn x-min-role
    API-->>FE: 403 forbidden
  else Đủ quyền
    API-->>FE: 200 dữ liệu
  end
```

Vai trò và trạng thái khóa đọc lại từ CSDL ở **mỗi** request, nên khóa tài khoản hay hạ vai trò có hiệu lực ngay dù JWT còn hạn.

## 2. Nhận webhook cảnh báo

```mermaid
sequenceDiagram
  autonumber
  participant AM as Alertmanager
  participant API as portal-api
  participant DB as portal-db
  participant DET as detection (trong portal-api)
  participant REC as alert-recorder

  par Hai receiver song song (ADR-0006)
    AM->>REC: POST /alerts (ghi JSONL, đối chứng)
  and
    AM->>API: POST /api/webhooks/alertmanager (Bearer PORTAL_WEBHOOK_TOKEN)
  end
  API->>API: Ghi received_at = đồng hồ monitor (T1)
  alt Sai hoặc thiếu token
    API-->>AM: 401
  end
  API->>DB: BEGIN, INSERT webhook_receipts (payload_sha256 unique)
  alt Payload trùng hoàn toàn
    API->>DB: ROLLBACK
    API-->>AM: 200 duplicate=true
  end
  loop Mỗi alert trong payload
    API->>DB: Tìm alert_episodes theo (fingerprint, startsAt)
    alt status firing, đợt mới (BR-03)
      API->>DB: INSERT alert_episodes (first_received_at = T1)
      API->>DB: Tìm incidents chưa đóng cùng (alertname, instance)
      alt Có sự cố đang mở (BR-08)
        API->>DB: Gắn đợt vào sự cố, firing=true, incident_events episode_firing
      else Không có
        API->>DB: INSERT incidents status=open, incident_events opened
      end
      API->>DET: Đợt firing mới (host, alertname, T1)
      DET->>DB: Có fault_runs đang chạy trên host này?
      opt Có lần chạy đang hoạt động
        DET->>DB: INSERT fault_run_alerts (role root/expected/extra, delay_s = T1 - T0)
      end
    else status firing, đợt đã có (Alertmanager gửi lại)
      API->>DB: Chỉ cập nhật last_received_at
    else status resolved
      API->>DB: Đợt resolved, ends_at, resolved_received_at = T1
      API->>DB: Sự cố còn đợt firing nào? Cập nhật incidents.firing, incident_events episode_resolved
    end
  end
  API->>DB: COMMIT
  API-->>AM: 200 số đợt tạo/cập nhật, số sự cố tạo
```

- Hai webhook cùng tới cho một khóa: unique index "một sự cố chưa đóng mỗi `(alertname, instance)`" làm một transaction lỗi;
  transaction đó thử lại một lần và sẽ gắn vào sự cố vừa tạo.
- Lỗi xử lý một alert riêng lẻ được ghi lại nhưng vẫn trả 200, vì payload thô đã lưu và xử lý lại được. Chỉ trả 5xx khi không
  lưu được payload, để Alertmanager gửi lại.

## 3. Operator xử lý sự cố

```mermaid
sequenceDiagram
  autonumber
  actor OP as Operator
  participant FE as Trình duyệt
  participant API as portal-api
  participant DB as portal-db

  OP->>FE: Mở sự cố từ danh sách
  FE->>API: GET /api/incidents/{id}
  API->>DB: Sự cố, các đợt, dòng thời gian, runbook theo alertname
  API-->>FE: IncidentDetail (can_close, runbook, grafana_url)
  FE->>OP: Thông tin + runbook bên cạnh + nút Mở Grafana

  OP->>FE: Xác nhận
  FE->>API: POST /api/incidents/{id}/acknowledge
  alt status khác open
    API-->>FE: 409 incident_not_open
  else
    API->>DB: status=acknowledged, acknowledged_by/at, incident_events, audit_log
    API-->>FE: 200
  end

  OP->>FE: Ghi chú các bước kiểm tra theo runbook
  FE->>API: POST /api/incidents/{id}/notes
  API->>DB: incident_events type=note (người, thời điểm: BR-02)

  alt Không có vấn đề thật
    OP->>FE: Báo giả + lý do
    FE->>API: POST /api/incidents/{id}/false-positive
    API->>DB: is_false_positive=true, reason (BR-04)
  else Có vấn đề, đã xử lý xong
    Note over OP,DB: Chờ webhook resolved (luồng 2) làm incidents.firing=false
  end

  OP->>FE: Đóng + kết luận
  FE->>API: POST /api/incidents/{id}/close
  API->>DB: Đọc lại firing, is_false_positive (khóa dòng)
  alt Còn firing và không phải báo giả (BR-01)
    API-->>FE: 409 incident_still_firing
  else
    API->>DB: status=closed, closed_by/at, conclusion, incident_events, audit_log
    API-->>FE: 200
    Note over API,DB: Lần kích hoạt sau của khóa này tạo sự cố mới (BR-08)
  end
```

## 4. Trang tổng quan

```mermaid
sequenceDiagram
  autonumber
  participant FE as Trình duyệt (OverviewPage)
  participant API as portal-api
  participant C as Cache 15 s
  participant P as Prometheus
  participant DB as portal-db

  loop Mỗi 15 s hoặc khi đổi chip lọc / khoảng thời gian
    par Số liệu hiện tại
      FE->>API: GET /api/overview?host=&service=
      API->>DB: Host, service đang bật, số sự cố mở theo mức độ, 10 sự cố mới nhất, lần chạy đang hoạt động, TB thời gian phát hiện
      API->>C: Có kết quả truy vấn hiện tại trong 15 s?
      alt Chưa có
        API->>P: Vài truy vấn tức thời dựng sẵn (up, CPU, RAM, đĩa, mạng, uptime, probe)
        alt Prometheus trả lời
          P-->>API: Vector
          API->>C: Lưu 15 s
        else Timeout 5 s
          API->>API: metrics_available=false, giá trị null
        end
      end
      API-->>FE: Overview
    and Biểu đồ
      FE->>API: GET /api/overview/series?range=1h
      API->>C: Có trong 15 s?
      opt Chưa có
        API->>P: query_range dựng sẵn, bước để mỗi series khoảng 120 điểm
        API->>C: Lưu 15 s
      end
      API-->>FE: OverviewSeries
    end
    FE->>FE: Vẽ ô KPI, thẻ dịch vụ, đồng hồ, biểu đồ, donut, bảng
  end
```

Nhiều người mở trang cùng lúc vẫn chỉ tạo mỗi truy vấn một lần mỗi 15 s tới Prometheus.

## 5. Admin chạy kịch bản lỗi và tính thời gian phát hiện

```mermaid
sequenceDiagram
  autonumber
  actor AD as Admin
  participant FE as Trình duyệt
  participant API as portal-api
  participant DB as portal-db
  participant P as Prometheus
  participant VM as VM web/db (obslab-fault qua SSH)
  participant AM as Alertmanager

  AD->>FE: Chọn kịch bản, VM, tham số, thời hạn
  FE->>API: GET /api/faults/preflight?host=web
  API->>DB: Có fault_runs đang hoạt động trên VM?
  API->>P: Trễ đánh giá luật, đồng hồ VM ổn định 2 phút, cảnh báo đang firing của VM
  API-->>FE: clean, reasons
  AD->>FE: Chạy
  FE->>API: POST /api/faults/runs
  API->>API: Kiểm tham số theo danh mục (422 nếu ngoài giới hạn)
  API->>DB: INSERT fault_runs status=pending (unique: một lần chạy mỗi VM, BR-06)
  alt VM bận
    API-->>FE: 409 fault_host_busy
  end
  API->>P: Độ lệch đồng hồ VM so với monitor, trễ đánh giá luật
  API->>VM: ssh obslab-fault-ssh: scenario start duration=hold+60 params
  alt VM từ chối hoặc SSH lỗi
    VM-->>API: Lỗi
    API->>DB: status=failed, error
    API-->>FE: 503 vm_unreachable hoặc 409
  else
    VM-->>API: started_ts (đồng hồ VM)
    API->>API: T0 = started_ts - độ lệch đồng hồ
    API->>DB: status=running, injected_at=T0, valid và lý do, audit_log fault_start
    API-->>FE: 202 FaultRun
  end

  loop Trình duyệt hỏi mỗi 2-5 s
    FE->>API: GET /api/faults/runs/{id}
    API-->>FE: Trạng thái, cảnh báo đã khớp, thời gian trôi qua
  end

  Note over P,AM: Prometheus vượt ngưỡng liên tục trong for, Alertmanager chờ group_wait
  AM->>API: Webhook firing (luồng 2)
  API->>DB: fault_run_alerts role=root, delay_s = T1 - T0
  API->>API: Tác vụ theo dõi thấy cảnh báo gốc, chờ thêm linger_s
  API->>VM: ssh: scenario stop
  VM-->>API: OK
  API->>DB: status=recovering, recovered_at, stop_reason=root_alert_received

  AM->>API: Webhook resolved
  API->>DB: root_resolved_s
  API->>DB: status=completed, first_detection_s, root_detection_s, đánh dấu cảnh báo extra/unrelated
  FE->>API: GET /api/faults/runs/{id}
  API-->>FE: Kết quả (BR-07: kèm scrape, eval, for, group_wait)

  alt Hết hold_s mà chưa có cảnh báo gốc
    API->>VM: ssh: scenario stop
    API->>DB: completed, root_detection_s=null (không phát hiện)
  end
```

- T0 và T1 cùng đồng hồ monitor (chrony), giống `tools/fault.py` và alert-recorder, nên kết quả portal đối chiếu được với CLI ở GĐ7.
- VM luôn tự gỡ khi hết `duration` (= `hold_s` + 60 s), kể cả khi backend chết giữa chừng (ADR-0007).

## 6. Backend khởi động lại khi đang chạy kịch bản

```mermaid
sequenceDiagram
  autonumber
  participant API as portal-api (vừa khởi động)
  participant DB as portal-db
  participant VM as VM web/db

  API->>DB: fault_runs status pending, running hoặc recovering
  loop Mỗi lần chạy dở
    API->>VM: ssh: status
    alt VM vẫn đang lỗi
      API->>VM: ssh: scenario stop
      API->>DB: status=completed, valid=false, lý do "backend khởi động lại giữa chừng"
    else VM đã tự gỡ (hết duration)
      API->>DB: status=cancelled, valid=false
    else Không SSH được
      API->>DB: Giữ trạng thái, thử lại sau 30 s (VM vẫn tự gỡ khi hết duration)
    end
  end
```
