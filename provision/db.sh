#!/usr/bin/env bash
# VM db: PostgreSQL cho demo app, chỉ nhận kết nối từ VM web (và monitor cho kiểm tra).
# GĐ2 sẽ thêm user chỉ-đọc + postgres-exporter.
set -euo pipefail
LOG_TAG=db
source /vagrant/provision/lib.sh

: "${VM_WEB_IP:?}" "${VM_MONITOR_IP:?}" "${LAB_DB_NAME:?}" "${LAB_DB_USER:?}" "${LAB_DB_PASSWORD:?}"

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

sudo -u postgres psql -tAc "SELECT version()"
log "Xong"
