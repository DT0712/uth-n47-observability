#!/usr/bin/env bash
# VM monitor: Docker Engine + Compose plugin; công cụ kiểm tra kết nối tới web/db.
# GĐ2 sẽ thêm: chép monitor/ và `docker compose up -d` cho Prometheus/Alertmanager/Grafana/...
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

docker version --format 'Docker {{.Server.Version}}'
docker compose version

log "Xong (stack giám sát sẽ được thêm ở GĐ2)"
