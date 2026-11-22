#!/usr/bin/env bash
# VM db: PostgreSQL cho demo app, chỉ nhận kết nối từ VM web (và monitor cho kiểm tra);
# postgres-exporter :9187 dùng role chỉ-đọc pg_monitor.
set -euo pipefail
LOG_TAG=db
source /vagrant/provision/lib.sh

: "${VM_WEB_IP:?}" "${VM_MONITOR_IP:?}" "${LAB_DB_NAME:?}" "${LAB_DB_USER:?}" "${LAB_DB_PASSWORD:?}" "${POSTGRES_EXPORTER_PASSWORD:?}"

pgver=${POSTGRES_MAJOR}
conf_dir=/etc/postgresql/${pgver}/main

log "PostgreSQL ${pgver}"
apt_install "postgresql-${pgver}" postgresql-client-common

restart=0
if write_if_changed "${conf_dir}/conf.d/obslab.conf" <<'EOF'
# Quản lý bởi provision/db.sh
listen_addresses = '*'
password_encryption = scram-sha-256
EOF
then restart=1; fi

# Khối pg_hba riêng của lab: app từ VM web, kiểm tra kết nối từ VM monitor.
hba=${conf_dir}/pg_hba.conf
block=$(cat <<EOF
# BEGIN obslab
host  ${LAB_DB_NAME}  ${LAB_DB_USER}  ${VM_WEB_IP}/32      scram-sha-256
host  ${LAB_DB_NAME}  ${LAB_DB_USER}  ${VM_MONITOR_IP}/32  scram-sha-256
host  postgres        postgres_exporter  127.0.0.1/32     scram-sha-256
# END obslab
EOF
)
current=$(sed -n '/^# BEGIN obslab$/,/^# END obslab$/p' "$hba")
if [[ $current != "$block" ]]; then
  sed -i '/^# BEGIN obslab$/,/^# END obslab$/d' "$hba"
  printf '%s\n' "$block" >>"$hba"
  restart=1
fi
chown postgres:postgres "${conf_dir}/conf.d/obslab.conf"

systemctl enable "postgresql@${pgver}-main" >/dev/null
if ((restart)); then systemctl restart "postgresql@${pgver}-main"; else systemctl start "postgresql@${pgver}-main"; fi
for _ in {1..20}; do pg_isready -q && break; sleep 1; done

log "Role, CSDL, bảng của demo app"
# Truyền qua biến psql (:'x') để không phải tự escape; mật khẩu không xuất hiện trên dòng lệnh.
sudo -u postgres psql -v ON_ERROR_STOP=1 -q \
  -v db="$LAB_DB_NAME" -v usr="$LAB_DB_USER" -v pwd="$LAB_DB_PASSWORD" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN', :'usr')
 WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'usr') \gexec
SELECT format('ALTER ROLE %I WITH LOGIN PASSWORD %L', :'usr', :'pwd') \gexec
SELECT format('CREATE DATABASE %I OWNER %I', :'db', :'usr')
 WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'db') \gexec
SQL

sudo -u postgres psql -v ON_ERROR_STOP=1 -q -d "$LAB_DB_NAME" -v usr="$LAB_DB_USER" <<'SQL'
CREATE TABLE IF NOT EXISTS work_items (
  id         bigserial PRIMARY KEY,
  payload    integer     NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
SELECT format('ALTER TABLE work_items OWNER TO %I', :'usr') \gexec
SELECT format('ALTER SEQUENCE work_items_id_seq OWNER TO %I', :'usr') \gexec
SQL

log "Role chỉ-đọc cho postgres-exporter"
sudo -u postgres psql -v ON_ERROR_STOP=1 -q -v pwd="$POSTGRES_EXPORTER_PASSWORD" <<'SQL'
SELECT 'CREATE ROLE postgres_exporter LOGIN'
 WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'postgres_exporter') \gexec
SELECT format('ALTER ROLE postgres_exporter WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD %L', :'pwd') \gexec
GRANT pg_monitor TO postgres_exporter;
SQL

log "postgres-exporter"
v=${POSTGRES_EXPORTER_VERSION}
exp_restart=0
if install_exporter postgres_exporter "$v" \
    "https://github.com/prometheus-community/postgres_exporter/releases/download/v${v}" \
    "postgres_exporter-${v}.linux-amd64.tar.gz" "postgres_exporter-${v}.linux-amd64"; then
  exp_restart=1
fi
id postgres_exporter &>/dev/null || useradd --system --no-create-home --shell /usr/sbin/nologin postgres_exporter
# Mật khẩu chỉ nằm trong file 0640; giá trị lab không được chứa ký tự đặc biệt của URL (@ : / ?).
if write_if_changed /etc/obslab/postgres-exporter.env 0640 <<EOF
DATA_SOURCE_NAME=postgresql://postgres_exporter:${POSTGRES_EXPORTER_PASSWORD}@127.0.0.1:5432/postgres?sslmode=disable
EOF
then exp_restart=1; fi
chgrp postgres_exporter /etc/obslab/postgres-exporter.env
if write_if_changed /etc/systemd/system/postgres-exporter.service <<'EOF'
[Unit]
Description=Prometheus PostgreSQL exporter
After=network-online.target postgresql.service
Wants=network-online.target

[Service]
User=postgres_exporter
Group=postgres_exporter
EnvironmentFile=/etc/obslab/postgres-exporter.env
ExecStart=/usr/local/bin/postgres_exporter --web.listen-address=:9187
Restart=on-failure
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true

[Install]
WantedBy=multi-user.target
EOF
then exp_restart=1; fi
systemctl daemon-reload
systemctl enable postgres-exporter >/dev/null
if ((exp_restart)); then systemctl restart postgres-exporter; else systemctl start postgres-exporter; fi
for _ in {1..10}; do curl -fs -o /dev/null http://127.0.0.1:9187/metrics && break; sleep 1; done
curl -fs http://127.0.0.1:9187/metrics | grep -E '^pg_up '

sudo -u postgres psql -tAc "SELECT version()"
log "Xong"
