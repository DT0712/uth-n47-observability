#!/usr/bin/env bash
# VM monitor: Docker Engine + Compose plugin; stack giám sát monitor/docker-compose.yml
# (Prometheus, Alertmanager, Grafana, Blackbox, alert-recorder) và web portal (portal-db, portal-api, portal-web).
set -euo pipefail
LOG_TAG=monitor
source /vagrant/provision/lib.sh

log "Kho apt của Docker"
apt_install ca-certificates curl gnupg postgresql-client
if [[ ! -f /etc/apt/keyrings/docker.asc ]]; then
  install -d -m 0755 /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
fi
codename=$(. /etc/os-release && echo "$VERSION_CODENAME")
if write_if_changed /etc/apt/sources.list.d/docker.list <<EOF
deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${codename} stable
EOF
then
  rm -f /var/lib/apt/periodic/obslab-update-stamp
fi

log "Docker Engine ${DOCKER_CE_VERSION}"
installed=$(dpkg-query -W -f='${Version}' docker-ce 2>/dev/null || true)
if [[ $installed != "$DOCKER_CE_VERSION" ]]; then
  apt_update
  apt-get install -y -q --allow-downgrades \
    "docker-ce=${DOCKER_CE_VERSION}" "docker-ce-cli=${DOCKER_CE_VERSION}" containerd.io \
    "docker-compose-plugin=${DOCKER_COMPOSE_PLUGIN_VERSION}" docker-buildx-plugin
fi
# Giữ phiên bản để `apt upgrade` không tự nâng.
apt-mark hold docker-ce docker-ce-cli docker-compose-plugin >/dev/null

if write_if_changed /etc/docker/daemon.json <<'EOF'
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "10m", "max-file": "3" }
}
EOF
then
  systemctl restart docker
fi
systemctl enable --now docker >/dev/null
usermod -aG docker vagrant

: "${VM_MONITOR_IP:?}" "${VM_WEB_IP:?}" "${VM_DB_IP:?}" "${GRAFANA_ADMIN_USER:?}" "${GRAFANA_ADMIN_PASSWORD:?}"
: "${GRAFANA_ANONYMOUS_ENABLED:?}" "${PROM_RETENTION:?}" "${HOST_PORT_GRAFANA:?}"
: "${PORTAL_DB_PASSWORD:?}" "${PORTAL_JWT_SECRET:?}" "${PORTAL_JWT_EXPIRE_MINUTES:?}" "${PORTAL_WEBHOOK_TOKEN:?}"
: "${PORTAL_BOOTSTRAP_ADMIN_USER:?}" "${PORTAL_BOOTSTRAP_ADMIN_PASSWORD:?}"

docker version --format 'Docker {{.Server.Version}}'
docker compose version

log "Stack giám sát (Docker Compose)"
# Biến cho Compose nằm ngoài thư mục chia sẻ, chỉ root đọc được.
write_if_changed /opt/obslab/monitor.env 0600 <<EOF || true
VM_MONITOR_IP=${VM_MONITOR_IP}
VM_WEB_IP=${VM_WEB_IP}
VM_DB_IP=${VM_DB_IP}
PROM_RETENTION=${PROM_RETENTION}
GRAFANA_ADMIN_USER=${GRAFANA_ADMIN_USER}
GRAFANA_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD}
GRAFANA_ANONYMOUS_ENABLED=${GRAFANA_ANONYMOUS_ENABLED}
HOST_PORT_GRAFANA=${HOST_PORT_GRAFANA}
PORTAL_DB_PASSWORD=${PORTAL_DB_PASSWORD}
PORTAL_JWT_SECRET=${PORTAL_JWT_SECRET}
PORTAL_JWT_EXPIRE_MINUTES=${PORTAL_JWT_EXPIRE_MINUTES}
PORTAL_WEBHOOK_TOKEN=${PORTAL_WEBHOOK_TOKEN}
PORTAL_BOOTSTRAP_ADMIN_USER=${PORTAL_BOOTSTRAP_ADMIN_USER}
PORTAL_BOOTSTRAP_ADMIN_PASSWORD=${PORTAL_BOOTSTRAP_ADMIN_PASSWORD}
EOF

# Token webhook cho Alertmanager (credentials_file; Alertmanager không đọc biến môi trường trong file cấu hình).
# Alertmanager chạy với user nobody (65534) nên cho nhóm 65534 đọc.
printf '%s' "$PORTAL_WEBHOOK_TOKEN" | write_if_changed /opt/obslab/portal-webhook-token 0640 || true
chown root:65534 /opt/obslab/portal-webhook-token

# Wrapper để mọi nơi (provision, tools/*.py qua `vagrant ssh`) gọi Compose với cùng tham số.
write_if_changed /usr/local/bin/obslab-compose 0755 <<'EOF' || true
#!/usr/bin/env bash
exec sudo docker compose -p obslab --env-file /opt/obslab/monitor.env -f /vagrant/monitor/docker-compose.yml "$@"
EOF

mkdir -p /vagrant/data/alerts
obslab-compose pull -q --ignore-buildable   # alert-recorder được build tại chỗ, không có trên Docker Hub
# --build chỉ build lại alert-recorder khi Dockerfile/app.py đổi (có cache); --remove-orphans dọn service đã bỏ.
obslab-compose up -d --build --remove-orphans --quiet-pull

log "Chờ các thành phần sẵn sàng"
for url in http://127.0.0.1:9090/-/ready http://127.0.0.1:9093/-/ready \
           http://127.0.0.1:3000/api/health http://127.0.0.1:5001/health http://127.0.0.1:8080/api/health; do
  for _ in {1..90}; do curl -fs -o /dev/null "$url" && break; sleep 2; done
  curl -fs -o /dev/null "$url" || { log "LỖI: $url chưa sẵn sàng"; obslab-compose ps; exit 1; }
done
obslab-compose ps --format 'table {{.Service}}\t{{.Status}}'

log "Xong"
