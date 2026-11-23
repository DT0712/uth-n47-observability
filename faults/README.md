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

Gây lỗi bằng tay (CLI `tools/fault.py` sẽ thay bước này):

```powershell
ssh -F none -i .lab-keys\obslab_fault_ed25519 -o UserKnownHostsFile=.lab-keys\known_hosts obslab-fault@192.168.56.11 status
```

`check_fault_ssh.py` tự siết quyền file khóa trên Windows; chạy nó một lần trước khi dùng `ssh` bằng tay.
