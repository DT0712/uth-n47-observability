# faults/ — kịch bản lỗi chạy trên VM (GĐ3)

Được chép tới `/opt/obslab/faults/` trên VM web và db. Gọi qua SSH bằng user `obslab-fault` với wrapper chỉ chấp
nhận danh sách lệnh cho phép (ADR-0007):

```
obslab-fault <kịch bản> <start|stop|status> [tham số]
```

| Kịch bản | Cách gây lỗi | Cảnh báo mong đợi |
|---|---|---|
| `cpu` | `stress-ng --cpu 0 --timeout <thời hạn>` | HostHighCpu |
| `disk` | `fallocate` vào `/mnt/labdisk` (file loop, không đụng ổ hệ thống) | HostDiskAlmostFull |
| `service-stop` | `systemctl stop nginx \| demo-app \| postgresql` (danh sách cho phép) | NginxDown / ServiceDown / PostgresDown, EndpointDown |
| `latency`, `errors` | gọi API tiêm lỗi của demo app | EndpointSlow, ServiceHighLatency, ServiceHighErrorRate |
| `memory` (tuỳ chọn) | `stress-ng --vm` | HostHighMemory |

Mọi kịch bản có thời hạn tối đa và tự khôi phục.
