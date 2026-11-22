#!/usr/bin/env bash
# Kiểm tra lab sau `vagrant up` — chạy trên VM monitor:
#   vagrant ssh monitor -c "bash /vagrant/provision/verify.sh"
# Thoát mã 0 nếu mọi kiểm tra đạt.
set -uo pipefail

# Đọc cấu hình lab giống Vagrantfile: .env ghi đè .env.example.
env_get() {
  local f v result=""
  for f in /vagrant/.env.example /vagrant/.env; do
    [[ -f $f ]] || continue
    v=$(grep -E "^$1=" "$f" | tail -1 | cut -d= -f2- | tr -d '\r')
    [[ -n $v ]] && result=$v
  done
  echo "$result"
}
LAB_DB_NAME=${LAB_DB_NAME:-$(env_get LAB_DB_NAME)}
LAB_DB_USER=${LAB_DB_USER:-$(env_get LAB_DB_USER)}
LAB_DB_PASSWORD=${LAB_DB_PASSWORD:-$(env_get LAB_DB_PASSWORD)}
fail=0

check() {
  local desc=$1; shift
  if out=$("$@" 2>&1); then
    printf '  [OK]   %s\n' "$desc"
  else
    printf '  [LỖI]  %s\n         %s\n' "$desc" "$(echo "$out" | tail -1)"
    fail=1
  fi
}

expect_http() {  # expect_http <mã> <url>
  local code
  code=$(curl -s -o /dev/null -m 5 -w '%{http_code}' "$2")
  [[ $code == "$1" ]] || { echo "HTTP $code (mong đợi $1)"; return 1; }
}

echo "== Phân giải tên + mạng host-only"
for h in monitor web db; do
  check "ping $h ($(getent hosts $h | awk '{print $1}'))" ping -c1 -W2 "$h"
done

echo "== Node Exporter trên 3 VM"
for h in monitor web db; do
  check "http://$h:9100/metrics" curl -fs -m 5 -o /dev/null "http://$h:9100/metrics"
done

echo "== Đồng bộ đồng hồ"
check "chrony đã đồng bộ (monitor)" bash -c "chronyc tracking | grep -q 'Leap status *: Normal'"

echo "== VM web (Nginx + demo app)"
check "GET http://web/health -> 200"   expect_http 200 http://web/health
check "GET http://web/api/work -> 200" expect_http 200 http://web/api/work
check "GET http://web/api/db -> 200 (web -> db)" expect_http 200 http://web/api/db
check "GET http://web/metrics từ monitor -> 200" expect_http 200 http://web/metrics
check "GET http://web/nginx_status từ monitor -> 200" expect_http 200 http://web/nginx_status
check "POST http://web/admin/reset từ ngoài bị chặn -> 403" \
  bash -c "[[ \$(curl -s -o /dev/null -m 5 -w '%{http_code}' -X POST http://web/admin/reset) == 403 ]]"

echo "== VM db (PostgreSQL)"
check "pg_isready -h db" pg_isready -h db -t 5
if [[ -n ${LAB_DB_PASSWORD:-} ]]; then
  check "đăng nhập ${LAB_DB_USER}@db/${LAB_DB_NAME}" \
    env PGPASSWORD="$LAB_DB_PASSWORD" psql -h db -U "$LAB_DB_USER" -d "$LAB_DB_NAME" -tAc "SELECT count(*) FROM work_items"
fi

echo "== VM monitor"
check "Docker chạy" docker info --format '{{.ServerVersion}}'
check "docker compose có sẵn" docker compose version

echo
if ((fail)); then echo "KẾT QUẢ: CÓ LỖI"; else echo "KẾT QUẢ: TẤT CẢ ĐẠT"; fi
exit $fail
