#!/usr/bin/env bash
# VM web: demo app (FastAPI, systemd, chỉ nghe 127.0.0.1:8000) sau Nginx :80; tải nền nhẹ.
# GĐ2 sẽ thêm nginx-exporter.
set -euo pipefail
LOG_TAG=web
source /vagrant/provision/lib.sh

: "${VM_MONITOR_IP:?}" "${LAB_DB_NAME:?}" "${LAB_DB_USER:?}" "${LAB_DB_PASSWORD:?}"

app_dir=/opt/obslab/demo-web
venv=${app_dir}/.venv

log "Gói"
apt_install nginx python3-venv

id demoapp &>/dev/null || useradd --system --home-dir "$app_dir" --shell /usr/sbin/nologin demoapp

log "Chép demo app vào ${app_dir}"
install -d -o root -g root -m 0755 /opt/obslab "$app_dir"
changed=0
for f in app.py loadgen.py requirements.txt; do
  if ! cmp -s "/vagrant/apps/demo-web/${f}" "${app_dir}/${f}"; then
    install -m 0644 "/vagrant/apps/demo-web/${f}" "${app_dir}/${f}"
    changed=1
  fi
done

req_hash=$(sha256sum "${app_dir}/requirements.txt" | cut -d' ' -f1)
if [[ ! -x ${venv}/bin/python ]] || [[ $(cat "${venv}/.req-hash" 2>/dev/null) != "$req_hash" ]]; then
  log "Tạo venv + cài thư viện"
  python3 -m venv "$venv"
  "${venv}/bin/pip" install -q --disable-pip-version-check -r "${app_dir}/requirements.txt"
  echo "$req_hash" >"${venv}/.req-hash"
  changed=1
fi

# Mật khẩu CSDL nằm ở file riêng chỉ root/demoapp đọc được, không nằm trong unit.
if write_if_changed /etc/obslab/demo-app.env 0640 <<EOF
SERVICE_NAME=demo-app
DATABASE_URL=postgresql://${LAB_DB_USER}:${LAB_DB_PASSWORD}@db:5432/${LAB_DB_NAME}
EOF
then changed=1; fi
chgrp demoapp /etc/obslab/demo-app.env

if write_if_changed /etc/systemd/system/demo-app.service <<EOF
[Unit]
Description=Lab demo app (FastAPI)
After=network-online.target
Wants=network-online.target

[Service]
User=demoapp
Group=demoapp
WorkingDirectory=${app_dir}
EnvironmentFile=/etc/obslab/demo-app.env
ExecStart=${venv}/bin/uvicorn app:app --host 127.0.0.1 --port 8000 --no-access-log
Restart=on-failure
RestartSec=2
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true

[Install]
WantedBy=multi-user.target
EOF
then changed=1; fi

if write_if_changed /etc/systemd/system/demo-loadgen.service <<EOF
[Unit]
Description=Lab demo load generator (tải nền nhẹ qua Nginx)
After=demo-app.service nginx.service

[Service]
User=demoapp
Group=demoapp
WorkingDirectory=${app_dir}
Environment=TARGETS=http://127.0.0.1
Environment=RPS=2
ExecStart=${venv}/bin/python loadgen.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
then changed=1; fi

systemctl daemon-reload
systemctl enable demo-app demo-loadgen >/dev/null
if ((changed)); then systemctl restart demo-app demo-loadgen; else systemctl start demo-app demo-loadgen; fi

log "Nginx"
# /admin/* chỉ gọi được trực tiếp trên VM (127.0.0.1:8000); /metrics và stub_status chỉ cho VM monitor.
if write_if_changed /etc/nginx/sites-available/obslab <<EOF
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    location /admin/ { return 403; }

    location = /metrics {
        allow 127.0.0.1;
        allow ${VM_MONITOR_IP};
        deny all;
        proxy_pass http://127.0.0.1:8000;
    }

    location = /nginx_status {
        stub_status;
        allow 127.0.0.1;
        allow ${VM_MONITOR_IP};
        deny all;
        access_log off;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_read_timeout 70s;
    }
}
EOF
then nginx_changed=1; fi
ln -sf /etc/nginx/sites-available/obslab /etc/nginx/sites-enabled/obslab
if [[ -e /etc/nginx/sites-enabled/default ]]; then rm -f /etc/nginx/sites-enabled/default; nginx_changed=1; fi
nginx -t -q
systemctl enable nginx >/dev/null
if [[ ${nginx_changed:-0} == 1 ]]; then systemctl reload-or-restart nginx; else systemctl start nginx; fi

for _ in {1..20}; do curl -fs -o /dev/null http://127.0.0.1/health && break; sleep 1; done
curl -fsS http://127.0.0.1/health
echo
log "Xong"
