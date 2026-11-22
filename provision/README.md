# provision/ — script dựng VM

Shell script được `Vagrantfile` gọi theo thứ tự (ADR-0003). Đã kiểm thử với Vagrant 2.4.9 + VirtualBox 7.2.22,
box `bento/ubuntu-24.04`.

| Script | Chạy trên | Việc làm | GĐ |
|---|---|---|---|
| `versions.env` | — | Ghim phiên bản Node Exporter, Docker, PostgreSQL | 1 |
| `lib.sh` | — | Hàm dùng chung: `apt_install`, `write_if_changed`, tải bản phát hành + kiểm tra sha256 | 1 |
| `common.sh` | mọi VM | Gói cơ bản, múi giờ, chrony, `/etc/hosts` cho 3 VM, ổ giả lập `/mnt/labdisk` (file loop `LAB_DISK_SIZE_MB`), stress-ng | 1 |
| `node_exporter.sh` | mọi VM | Node Exporter (systemd, :9100) có collector systemd cho các unit của lab | 1 |
| `monitor.sh` | monitor | Docker Engine + Compose plugin (ghim phiên bản), `postgresql-client` để kiểm tra | 1 |
| `web.sh` | web | Demo app (systemd, `127.0.0.1:8000`) sau Nginx :80, tải nền `demo-loadgen` | 1 |
| `db.sh` | db | PostgreSQL 16, role/CSDL/bảng của demo app, `pg_hba` chỉ cho web và monitor | 1 |
| `verify.sh` | monitor | Kiểm tra sau khi dựng: mạng, exporter, web → db, quyền truy cập | 1 |
| `fault_agent.sh` | web, db | User `obslab-fault`, wrapper + sudoers giới hạn (ADR-0007) | 3 |
| *(bổ sung)* | monitor/web/db | Stack Compose giám sát, nginx-exporter, postgres-exporter | 2 |

Quy ước: `set -euo pipefail`, idempotent (chạy lại `vagrant provision` không đổi gì nếu cấu hình không đổi), LF,
không hard-code mật khẩu (lấy từ `.env`/`.env.example` qua Vagrantfile).

## Dựng và kiểm tra (PowerShell hoặc WSL, tại thư mục gốc repo)

```powershell
vagrant up                                               # ~5 phút (chưa tính tải box lần đầu)
vagrant ssh monitor -c "bash /vagrant/provision/verify.sh"
vagrant destroy -f; vagrant up                           # dựng lại sạch từ đầu
vagrant provision web                                    # áp lại cấu hình sau khi sửa script
vagrant halt                                             # tắt cả 3 VM (giải phóng RAM)
```

Bên trong mạng host-only, các VM gọi nhau bằng tên `monitor`, `web`, `db`. Từ Windows truy cập trực tiếp
`http://192.168.56.11/health` (web) hoặc qua cổng forward `127.0.0.1:<HOST_PORT_*>` của monitor (từ GĐ2).

## Ghi chú

- Lab cần ~6.5 GB RAM cho 3 VM. Đóng bớt ứng dụng trước khi `vagrant up` nếu RAM trống ít hơn mức đó.
- Không chạy Docker Desktop/Hyper-V cùng lúc với VirtualBox (xem rủi ro trong [lộ trình](../docs/lo-trinh.md)).
- `/admin/*` của demo app chỉ gọi được trên chính VM web (`curl -X POST 127.0.0.1:8000/admin/reset`); Nginx trả
  403 cho mọi truy cập từ ngoài. `/metrics` và `/nginx_status` chỉ mở cho VM monitor.
