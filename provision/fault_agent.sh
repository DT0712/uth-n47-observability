#!/usr/bin/env bash
# VM web, db: user obslab-fault bị giới hạn, script kịch bản lỗi, sudoers, sshd Match (ADR-0007).
set -euo pipefail
LOG_TAG=fault_agent
source /vagrant/provision/lib.sh

: "${VM_MONITOR_IP:?}" "${VM_WEB_IP:?}" "${VM_DB_IP:?}" "${FAULT_SCENARIOS:?}" "${FAULT_SERVICES:?}"

key_dir=/vagrant/.lab-keys
key=${key_dir}/obslab_fault_ed25519
# Chỉ nhận kết nối từ Windows host (.1 của mạng host-only) và VM monitor (portal, GĐ7).
host_ip="${VM_MONITOR_IP%.*}.1"

log "Khóa SSH riêng của lab (.lab-keys/, gitignore)"
mkdir -p "$key_dir"
if [[ ! -s $key || ! -s ${key}.pub ]]; then
  tmp=$(mktemp -d)
  ssh-keygen -q -t ed25519 -N '' -C obslab-fault -f "${tmp}/k"
  cp "${tmp}/k" "$key" && cp "${tmp}/k.pub" "${key}.pub"
  rm -rf "$tmp"
  log "  đã sinh khóa mới"
fi

log "Script kịch bản lỗi"
apt_install sudo stress-ng curl
install -d -o root -g root -m 0755 /opt/obslab /opt/obslab/faults /etc/obslab
# Bản chạy thật là bản chép thuộc root; không chạy từ /vagrant (ai cũng ghi được).
for f in obslab-fault obslab-fault-ssh; do
  write_if_changed "/opt/obslab/faults/${f}" 0755 <"/vagrant/faults/${f}" || true
done
write_if_changed /etc/obslab/fault.conf 0644 <<EOF || true
FAULT_SCENARIOS="${FAULT_SCENARIOS}"
FAULT_SERVICES="${FAULT_SERVICES}"
EOF

log "User obslab-fault + sudoers"
# Cần một shell thật vì sshd chạy ForceCommand qua shell của user; mật khẩu '*' = không đăng nhập bằng mật khẩu.
id obslab-fault &>/dev/null || useradd --system --home-dir / --no-create-home --shell /bin/sh obslab-fault
# Home là / (có sẵn, thuộc root): không cần thư mục riêng, sshd không cảnh báo chdir.
usermod -p '*' -s /bin/sh -d / obslab-fault
tmp=$(mktemp)
cat >"$tmp" <<'EOF'
# Quản lý bởi provision/fault_agent.sh — chỉ đúng một lệnh; tham số do script kiểm tra.
Defaults:obslab-fault !requiretty
obslab-fault ALL=(root) NOPASSWD: /opt/obslab/faults/obslab-fault
EOF
visudo -cqf "$tmp"
write_if_changed /etc/sudoers.d/obslab-fault 0440 <"$tmp" || true
rm -f "$tmp"

log "sshd: chỉ khóa của lab, chỉ lệnh cưỡng bức"
ssh_changed=0
# authorized_keys do root giữ, user không tự thêm khóa được.
if write_if_changed /etc/ssh/obslab_fault_authorized_keys 0644 <<EOF
restrict,from="${host_ip},${VM_MONITOR_IP}",command="/opt/obslab/faults/obslab-fault-ssh" $(cat "${key}.pub")
EOF
then ssh_changed=1; fi
sshd_conf=/etc/ssh/sshd_config.d/60-obslab-fault.conf
if write_if_changed "$sshd_conf" 0644 <<'EOF'
# Quản lý bởi provision/fault_agent.sh
Match User obslab-fault
    AuthenticationMethods publickey
    AuthorizedKeysFile /etc/ssh/obslab_fault_authorized_keys
    ForceCommand /opt/obslab/faults/obslab-fault-ssh
    PermitTTY no
    PermitUserRC no
    DisableForwarding yes
    MaxSessions 2
Match all
EOF
then ssh_changed=1; fi
if ((ssh_changed)); then
  if ! sshd -t; then rm -f "$sshd_conf"; log "LỖI: cấu hình sshd không hợp lệ, đã gỡ"; exit 1; fi
  systemctl reload ssh
fi

log "Dọn lỗi còn sót sau khi VM khởi động lại giữa chừng"
write_if_changed /etc/systemd/system/obslab-fault-boot-recover.service <<'EOF' || true
[Unit]
Description=Gỡ lỗi mô phỏng còn sót (vd. VM reboot giữa kịch bản disk)
RequiresMountsFor=/mnt/labdisk
After=network.target

[Service]
Type=oneshot
ExecStart=/opt/obslab/faults/obslab-fault recover

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable -q obslab-fault-boot-recover.service

log "Ghi host key của VM vào .lab-keys/known_hosts"
name=$(hostname)
case $name in web) ip=$VM_WEB_IP ;; db) ip=$VM_DB_IP ;; *) log "LỖI: VM không hỗ trợ: $name"; exit 1 ;; esac
kh=${key_dir}/known_hosts
line="${name},${ip} $(cut -d' ' -f1,2 /etc/ssh/ssh_host_ed25519_key.pub)"
if ! grep -qxF "$line" "$kh" 2>/dev/null; then
  tmp=$(mktemp)
  { grep -v "^${name}," "$kh" 2>/dev/null || true; echo "$line"; } >"$tmp"
  cat "$tmp" >"$kh"
  rm -f "$tmp"
fi

/opt/obslab/faults/obslab-fault list
log "Xong"
