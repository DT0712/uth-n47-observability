#!/usr/bin/env bash
# Mọi VM: Node Exporter chạy bằng systemd, nghe cổng 9100.
set -euo pipefail
LOG_TAG=node_exporter
source /vagrant/provision/lib.sh

ver=${NODE_EXPORTER_VERSION}
bin=/usr/local/bin/node_exporter

if [[ -x $bin ]] && "$bin" --version 2>&1 | grep -q "version ${ver} "; then
  log "Node Exporter ${ver} đã cài"
else
  log "Cài Node Exporter ${ver}"
  name="node_exporter-${ver}.linux-amd64"
  tmp=$(mktemp -d)
  download_release "https://github.com/prometheus/node_exporter/releases/download/v${ver}" "${name}.tar.gz" "$tmp"
  tar -xzf "${tmp}/${name}.tar.gz" -C "$tmp"
  install -m 0755 "${tmp}/${name}/node_exporter" "$bin"
  rm -rf "$tmp"
  restart=1
fi

id node_exporter &>/dev/null || useradd --system --no-create-home --shell /usr/sbin/nologin node_exporter

# Collector systemd chỉ theo dõi các unit của lab -> phát hiện "dừng service" cả từ góc nhìn host.
if write_if_changed /etc/systemd/system/node_exporter.service <<'EOF'
[Unit]
Description=Prometheus Node Exporter
Wants=network-online.target
After=network-online.target

[Service]
User=node_exporter
Group=node_exporter
ExecStart=/usr/local/bin/node_exporter \
  --web.listen-address=:9100 \
  --collector.systemd \
  --collector.systemd.unit-include=(nginx|nginx-exporter|demo-app|demo-loadgen|postgresql@.*|postgres-exporter|docker|chrony)\.service \
  --collector.filesystem.mount-points-exclude=^/(dev|proc|run|sys|vagrant|var/lib/docker/.+)($|/)
Restart=on-failure
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true

[Install]
WantedBy=multi-user.target
EOF
then
  restart=1
fi

systemctl daemon-reload
systemctl enable node_exporter >/dev/null
if [[ ${restart:-0} == 1 ]]; then systemctl restart node_exporter; else systemctl start node_exporter; fi

for _ in {1..10}; do curl -fs -o /dev/null http://127.0.0.1:9100/metrics && break; sleep 1; done
curl -fs -o /dev/null http://127.0.0.1:9100/metrics
log "Node Exporter đang chạy trên :9100"
