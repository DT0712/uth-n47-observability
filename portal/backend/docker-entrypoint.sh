#!/bin/sh
# Khởi động portal-api: chép khóa SSH của lab với quyền 600, nâng CSDL, rồi chạy lệnh chính (uvicorn).
set -eu

# /vagrant là thư mục chia sẻ của VirtualBox, mọi file đều có quyền rộng; ssh từ chối khóa riêng như vậy
# ("UNPROTECTED PRIVATE KEY FILE"), nên chép sang thư mục riêng trong container.
if [ -d /lab-keys-src ]; then
  mkdir -p /lab-keys
  for f in obslab_fault_ed25519 known_hosts; do
    [ -f "/lab-keys-src/$f" ] && cp "/lab-keys-src/$f" "/lab-keys/$f"
  done
  chmod 700 /lab-keys
  chmod 600 /lab-keys/* 2>/dev/null || true
fi

# PostgreSQL đã healthy (depends_on) nhưng vẫn thử lại vài lần cho chắc
i=0
until python -m app.db.migrate; do
  i=$((i + 1))
  [ "$i" -ge 10 ] && { echo "migrate thất bại 10 lần" >&2; exit 1; }
  sleep 3
done

exec "$@"
