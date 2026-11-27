# Mô hình dữ liệu portal (ERD)

> GĐ4, phần 1. CSDL: PostgreSQL riêng của portal (ADR-0005); test trên Windows dùng SQLite cùng mô hình.
> Kiến trúc: [kien-truc-portal.md](kien-truc-portal.md). Mọi cột thời gian là `timestamptz` UTC, độ chính xác mili-giây (NFR-08).

```mermaid
erDiagram
  users ||--o{ incident_events : "thực hiện"
  users ||--o{ fault_runs : "yêu cầu"
  users ||--o{ audit_log : "thực hiện"
  hosts ||--o{ services : "có"
  webhook_receipts ||--o{ alert_episodes : "cập nhật"
  incidents ||--|{ alert_episodes : "gồm các đợt"
  incidents ||--o{ incident_events : "dòng thời gian"
  runbooks |o--o{ incidents : "theo alertname"
  fault_runs ||--o{ fault_run_alerts : "khớp"
  alert_episodes ||--o{ fault_run_alerts : "được khớp"
  fault_runs |o--o{ incidents : "gây ra (sự cố thử nghiệm)"

  users {
    int id PK
    string username UK
    string password_hash "bcrypt"
    string role "admin | operator"
    bool is_active
    timestamptz created_at
    timestamptz last_login_at
  }
  hosts {
    int id PK
    string name UK "monitor | web | db"
    string address "192.168.56.11"
    string prom_instance "nhãn instance của node exporter"
    string grafana_dashboard_uid
    string description
    bool enabled
  }
  services {
    int id PK
    int host_id FK
    string name "nginx | demo-app | postgresql"
    string kind "web | app | database | other"
    json prom_labels "vd. {job: nginx, service: nginx}"
    string probe_instance "nhãn instance của blackbox, có thể rỗng"
    string grafana_dashboard_uid
    bool enabled
  }
  webhook_receipts {
    int id PK
    timestamptz received_at
    string payload_sha256 UK
    string group_key
    string status "firing | resolved"
    int alert_count
    json payload "bản ghi thô"
  }
  alert_episodes {
    int id PK
    string fingerprint
    timestamptz starts_at "UK cùng fingerprint (BR-03)"
    timestamptz ends_at
    string status "firing | resolved"
    string alertname
    string instance
    string host
    string service
    string severity
    json labels
    json annotations
    timestamptz first_received_at "T1 khi firing"
    timestamptz resolved_received_at
    timestamptz last_received_at
    int incident_id FK
    int last_receipt_id FK
  }
  incidents {
    int id PK
    string alertname "khóa gộp (BR-08)"
    string instance "khóa gộp (BR-08)"
    string host
    string service
    string severity "cao nhất trong các đợt"
    string status "open | acknowledged | closed"
    bool firing "còn đợt nào firing (dẫn xuất, lưu để lọc nhanh)"
    bool is_false_positive
    string false_positive_reason
    string conclusion
    timestamptz opened_at
    timestamptz acknowledged_at
    int acknowledged_by FK
    timestamptz closed_at
    int closed_by FK
    int fault_run_id FK "khác rỗng: sự cố thử nghiệm (BR-09)"
  }
  incident_events {
    int id PK
    int incident_id FK
    timestamptz at
    int user_id FK "rỗng nếu do hệ thống"
    string type "opened | episode_firing | episode_resolved | acknowledged | note | false_positive | closed | fault_run"
    string content
    json data
  }
  runbooks {
    int id PK
    string alertname UK
    string title
    string severity
    string category
    string status "draft | reviewed"
    string body_md
    string source_path
    string source_sha256
    timestamptz loaded_at
  }
  fault_runs {
    int id PK
    string scenario "cpu | memory | disk | service-stop | latency | errors"
    string target_host
    json params
    int hold_s
    bool stop_on_alert
    string root_alert
    json expected_alerts
    string status "pending | running | recovering | completed | failed | cancelled"
    bool valid
    json invalid_reasons
    int requested_by FK
    timestamptz requested_at
    timestamptz injected_at "T0, đồng hồ monitor"
    timestamptz injected_at_vm
    float vm_clock_offset_s
    float eval_lag_s
    timestamptz recovered_at
    string stop_reason
    string error
    float first_detection_s
    float root_detection_s
    float root_resolved_s
  }
  fault_run_alerts {
    int id PK
    int fault_run_id FK
    int alert_episode_id FK
    string role "root | expected | extra | unrelated"
    float delay_s "first_received_at - injected_at"
  }
  audit_log {
    int id PK
    timestamptz at
    int user_id FK
    string action "login | login_failed | login_locked | create | update | delete | acknowledge | fault_start | fault_stop ..."
    string object_type
    string object_id
    json detail
    string client_ip
  }
```

## Ràng buộc và chỉ mục

| Bảng | Ràng buộc | Nguồn |
|---|---|---|
| `alert_episodes` | `UNIQUE (fingerprint, starts_at)` | BR-03, NFR-06 |
| `incidents` | `UNIQUE (alertname, instance) WHERE status <> 'closed'`: tối đa một sự cố chưa đóng mỗi khóa | BR-08 |
| `incidents` | `CHECK (status <> 'closed' OR NOT firing OR is_false_positive)`: không đóng khi còn firing, trừ báo giả | BR-01 |
| `incidents` | `CHECK (NOT is_false_positive OR length(false_positive_reason) > 0)` | BR-04 |
| `incidents` | `fault_run_id` FK `fault_runs`, có chỉ mục: lọc và loại sự cố thử nghiệm | BR-09 |
| `fault_runs` | `UNIQUE (target_host) WHERE status IN ('pending','running','recovering')`: mỗi VM một lần chạy | BR-06 |
| `webhook_receipts` | `UNIQUE (payload_sha256)`: Alertmanager gửi lại y hệt thì bỏ qua | NFR-06 |
| `services` | `UNIQUE (host_id, name)` | UC13 |
| Chỉ mục | `incidents (status, opened_at)`, `alert_episodes (host, first_received_at)`, `audit_log (at)` | lọc, phân trang, khớp kịch bản |

Các kiểm tra trên **cũng** nằm ở tầng service để trả lỗi rõ (409/422); ràng buộc CSDL là lớp chặn cuối khi có tranh chấp
(hai webhook tới cùng lúc, hai admin cùng bấm chạy).

## Máy trạng thái sự cố

```mermaid
stateDiagram-v2
  [*] --> open: đợt firing đầu tiên của (alertname, instance)
  open --> acknowledged: operator xác nhận (UC06)
  open --> closed: đóng (UC09)<br/>khi mọi đợt resolved, hoặc báo giả
  acknowledged --> closed: đóng (UC09)<br/>khi mọi đợt resolved, hoặc báo giả
  closed --> [*]
  note right of open
    Đợt firing mới cùng khóa: gắn vào sự cố, giữ trạng thái (BR-08)
    Ghi chú (UC07), báo giả + lý do (UC08) được ở mọi trạng thái chưa đóng
  end note
```

Trạng thái xử lý (`status`) và trạng thái Alertmanager (`firing`) độc lập (BR-01). Sự cố đã đóng không mở lại; đợt firing
sau đó tạo sự cố mới.

## Vòng đời lần chạy kịch bản lỗi

```mermaid
stateDiagram-v2
  [*] --> pending: admin tạo, kiểm tra điều kiện đo
  pending --> running: SSH start thành công (ghi T0)
  pending --> failed: VM từ chối / SSH lỗi
  running --> recovering: nhận cảnh báo gốc (+ linger) / hết hold_s / admin dừng
  recovering --> completed: SSH stop xong, chờ resolved hoặc hết thời gian chờ
  recovering --> failed: SSH stop lỗi (VM vẫn tự gỡ khi hết duration)
  running --> cancelled: backend khởi động lại và VM báo đã tự gỡ
  completed --> [*]
  failed --> [*]
  cancelled --> [*]
```

## Sự cố thử nghiệm (BR-09)

Khi webhook mang một đợt firing mới và đợt đó khớp một lần chạy đang hoạt động với vai trò `root`, `expected` hoặc `extra`
(xem `fault_run_alerts.role`; `unrelated` không tính), sự cố chứa đợt đó được gắn nhãn thử nghiệm:

- `incidents.fault_run_id` = lần chạy đầu tiên khớp (không ghi đè nếu sau đó lần chạy khác cũng rơi vào sự cố này).
- Thêm một dòng `incident_events` loại `fault_run` (người thực hiện rỗng = hệ thống), nội dung
  "Do kịch bản lỗi #N (…) gây ra lúc T0"; `data` giữ `fault_run_id`, `case`, `scenario`, `target_host`, `injected_at`, `role`,
  `episode_id`. Mỗi (sự cố, lần chạy) chỉ một dòng dù có nhiều đợt.
- **Không** đổi `status` hay `is_false_positive`: đây là phát hiện đúng, operator vẫn xử lý và đóng như sự cố thường.
- Báo cáo tỉ lệ báo giả loại sự cố thử nghiệm khỏi cả tử số và mẫu số.

Nhãn chỉ được gắn khi đợt cảnh báo tới (không quét lại sự cố cũ). Đợt tới trước T0 − 2 s không khớp nên sự cố thật có sẵn
từ trước khi chạy kịch bản không bị gắn nhầm.

Khi backend khởi động, mọi lần chạy ở `pending/running/recovering` được kiểm tra lại bằng SSH `status`: VM vẫn đang lỗi thì
gỡ (`stop`), đã tự gỡ thì đánh dấu `cancelled` và `valid=false` (NFR-07).

## Không lưu trong CSDL

- Metric, ngưỡng (`lab:threshold:*`): đọc trực tiếp từ Prometheus khi cần.
- Payload JSONL của alert-recorder: nguồn đối chứng riêng (ADR-0006).
