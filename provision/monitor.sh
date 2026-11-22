#!/usr/bin/env bash
# VM monitor: Docker Engine + Compose plugin; stack giám sát monitor/docker-compose.yml
# (Prometheus, Alertmanager, Grafana, Blackbox, alert-recorder).
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
: "${GRAFANA_ANONYMOUS_ENABLED:?}" "${PROM_RETENTION:?}"

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
EOF

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
           http://127.0.0.1:3000/api/health http://127.0.0.1:5001/health; do
  for _ in {1..60}; do curl -fs -o /dev/null "$url" && break; sleep 2; done
  curl -fs -o /dev/null "$url" || { log "LỖI: $url chưa sẵn sàng"; obslab-compose ps; exit 1; }
done
obslab-compose ps --format 'table {{.Service}}\t{{.Status}}'

log "Xong"
