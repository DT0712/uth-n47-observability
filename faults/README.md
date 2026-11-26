# faults/ — kịch bản lỗi chạy trên VM

`provision/fault_agent.sh` chép hai script này tới `/opt/obslab/faults/` (thuộc root) trên VM **web** và **db**:

| File | Chạy với quyền | Việc làm |
|---|---|---|
| `obslab-fault-ssh` | user `obslab-fault` | Lệnh cưỡng bức của SSH: lọc `SSH_ORIGINAL_COMMAND`, rồi gọi `obslab-fault` qua sudo |
| `obslab-fault` | root | Kiểm tra kịch bản và tham số theo danh sách cho phép, gây lỗi, hẹn giờ tự khôi phục |

## Lệnh

```
list | status | recover
<kịch bản> start [khóa=giá trị ...]
<kịch bản> stop
```

| Kịch bản | VM | Tham số (mặc định) | Cách gây lỗi | Cảnh báo mong đợi |
|---|---|---|---|---|
| `cpu` | web, db | `duration` (300) | `stress-ng --cpu 0` | HostHighCpu |
| `memory` | web, db | `duration`, `percent` (95; 50–97) | `stress-ng --vm`, không dùng swap, bị OOM kill trước tiên | HostHighMemory |
| `disk` | web, db | `duration`, `percent` (95; 50–99) | `fallocate` vào `/mnt/labdisk`, không đụng ổ hệ thống | HostDiskAlmostFull |
| `service-stop` | web, db | `duration`, `service` (bắt buộc) | `systemctl stop`: `nginx`, `demo-app` (web); `postgresql` (db) | NginxDown / ServiceDown / PostgresDown |
| `latency` | web | `duration`, `latency_ms` (3000; 100–7000) | `/admin/fault` của demo app | ServiceHighLatency, EndpointSlow |
| `errors` | web | `duration`, `error_rate` (50 %; 1–100) | `/admin/fault` của demo app | ServiceHighErrorRate |

`duration` tính bằng giây, từ 30 đến 900. Kết quả là **một dòng JSON**; `ts` là giờ VM ngay sau khi thao tác hoàn tất.
Mã thoát: `0` đạt, `1` lỗi, `2` sai tham số, `3` VM đang có kịch bản khác, `126` bị wrapper từ chối.

## An toàn

- **Tự khôi phục:** timer systemd `obslab-fault-recover` được đặt *trước* khi gây lỗi, nên mất SSH hay tắt máy
  điều khiển thì lỗi vẫn tự gỡ. VM khởi động lại giữa chừng: `obslab-fault-boot-recover.service` dọn phần còn sót.
- **Một kịch bản mỗi VM** tại một thời điểm (BR-06); gây lỗi thất bại giữa chừng thì tự gỡ ngay.
- **`recover`** gỡ mọi loại lỗi, chạy lại nhiều lần vẫn an toàn. Dịch vụ chỉ được bật lại nếu chính kịch bản đã dừng nó.
- **Nhật ký:** `sudo journalctl -t obslab-fault` trên VM (cả lệnh bị từ chối, kèm IP nguồn).

Các lớp giới hạn SSH và hạn chế đã biết: [ADR-0007](../docs/02-thiet-ke/adr/0007-ssh-gioi-han-cho-kich-ban-loi.md).

## Kiểm tra

```powershell
python tools/check_fault_ssh.py               # giới hạn SSH, không gây lỗi nào (~30 giây)
python tools/check_fault_ssh.py --scenarios   # thêm: chạy thật 11 trường hợp 30 giây (~10 phút)
```

## Gây lỗi bằng CLI

```powershell
python tools/fault.py run cpu --vm web                                   # giữ 240 giây rồi gỡ
python tools/fault.py run service-stop --service nginx --stop-on-alert   # gỡ sớm khi cảnh báo gốc đã tới
python tools/fault.py run disk --vm db --repeat 5 --stop-on-alert        # lặp lại, chờ lab sạch giữa các lần
python tools/fault.py suite --id gd3 --rounds 5                          # đo mọi trường hợp, mỗi trường hợp 5 lần (~2,5 giờ)
python tools/fault.py suite --id gd3-x --rounds 5 --cases "dừng nginx" "dừng demo-app"   # chỉ vài trường hợp
python tools/fault.py status
python tools/fault.py recover                                            # gỡ mọi lỗi
```

CLI từ chối chạy khi có lỗi khác đang hoạt động, có cảnh báo pending/firing, hoặc đồng hồ VM lệch monitor quá 0,1 giây
trong 2 phút gần nhất, hoặc Prometheus đánh giá luật trễ quá 1 giây (SC-04) (`--wait-clean` để chờ, `--force` để bỏ qua). Mốc gây lỗi lấy từ đồng hồ VM, đã hiệu chỉnh theo
độ lệch với monitor. Trong lúc chạy, Windows được giữ không ngủ.
