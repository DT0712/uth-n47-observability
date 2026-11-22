#!/usr/bin/env bash
# Mọi VM: gói cơ bản, múi giờ, chrony, /etc/hosts cho 3 VM, ổ giả lập /mnt/labdisk.
set -euo pipefail
LOG_TAG=common
source /vagrant/provision/lib.sh

: "${VM_MONITOR_IP:?}" "${VM_WEB_IP:?}" "${VM_DB_IP:?}" "${LAB_DISK_SIZE_MB:?}"

log "Gói cơ bản"
apt_install ca-certificates curl jq chrony stress-ng e2fsprogs

log "Múi giờ + đồng bộ đồng hồ (chrony)"
timedatectl set-timezone Asia/Ho_Chi_Minh
systemctl enable --now chrony >/dev/null

log "/etc/hosts cho 3 VM"
hosts_block=$(cat <<EOF
# BEGIN obslab
${VM_MONITOR_IP} monitor
${VM_WEB_IP} web
${VM_DB_IP} db
# END obslab
EOF
)
# Bỏ khối cũ (nếu có) và dòng 127.0.x.1 <hostname> do Vagrant thêm, để tên VM phân giải ra IP host-only.
sed -i -e '/^# BEGIN obslab$/,/^# END obslab$/d' -e "/^127\.0\.[0-9]\.1[[:space:]]\+$(hostname)\([[:space:]]\|\$\)/d" /etc/hosts
printf '%s\n' "$hosts_block" >>/etc/hosts

log "Ổ giả lập /mnt/labdisk (${LAB_DISK_SIZE_MB} MB, file loop)"
img=/var/lib/obslab/labdisk.img
mkdir -p /var/lib/obslab /mnt/labdisk
want_bytes=$((LAB_DISK_SIZE_MB * 1024 * 1024))
if [[ -f $img ]] && [[ $(stat -c %s "$img") -ne $want_bytes ]]; then
  log "  Kích thước thay đổi -> tạo lại ổ"
  umount /mnt/labdisk 2>/dev/null || true
  rm -f "$img"
fi
if [[ ! -f $img ]]; then
  fallocate -l "$want_bytes" "$img"
  mkfs.ext4 -q -L labdisk "$img"
fi
grep -q "^${img} " /etc/fstab || echo "${img} /mnt/labdisk ext4 loop,nofail 0 2" >>/etc/fstab
mountpoint -q /mnt/labdisk || mount /mnt/labdisk
chmod 1777 /mnt/labdisk

log "Xong"
