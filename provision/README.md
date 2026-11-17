# provision/ — script dựng VM (GĐ1)

Shell script được `Vagrantfile` gọi theo thứ tự (ADR-0003):

| Script | Chạy trên | Việc làm |
|---|---|---|
| `versions.env` | — | Ghim phiên bản Node Exporter, nginx-exporter, postgres-exporter, Docker, ... |
| `common.sh` | mọi VM | apt, múi giờ, chrony, `/etc/hosts` cho 3 VM, ổ giả lập `/mnt/labdisk` (file loop `LAB_DISK_SIZE_MB`), stress-ng |
| `node_exporter.sh` | mọi VM | Cài Node Exporter (systemd) |
| `fault_agent.sh` | web, db | User `obslab-fault`, wrapper + sudoers giới hạn, nạp public key từ `.lab-keys/` (ADR-0007) |
| `monitor.sh` | monitor | Docker Engine, chép `monitor/`, `docker compose up -d` |
| `web.sh` | web | Nginx (stub_status), demo app (systemd), nginx-exporter, tải nền nhẹ |
| `db.sh` | db | PostgreSQL, user chỉ-đọc cho exporter, postgres-exporter, tải nền nhẹ |

Quy ước: `set -euo pipefail`, idempotent, LF, không hard-code mật khẩu.
