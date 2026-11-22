# Hàm dùng chung cho các script provision. Được `source`, không chạy trực tiếp.
# shellcheck shell=bash

export DEBIAN_FRONTEND=noninteractive
PROVISION_DIR="${PROVISION_DIR:-/vagrant/provision}"
# shellcheck source=versions.env
source "${PROVISION_DIR}/versions.env"

# Vagrant chạy bản sao script trong /tmp nên $0 vô nghĩa; mỗi script tự đặt LOG_TAG trước khi source.
log() { printf '[%s] %s\n' "${LOG_TAG:-provision}" "$*"; }

# Chạy apt-get update tối đa một lần mỗi giờ.
apt_update() {
  local stamp=/var/lib/apt/periodic/obslab-update-stamp
  if [[ ! -f $stamp ]] || [[ -n $(find "$stamp" -mmin +60) ]]; then
    apt-get update -q
    mkdir -p "$(dirname "$stamp")" && touch "$stamp"
  fi
}

# Cài gói nếu chưa có.
apt_install() {
  local missing=()
  for pkg in "$@"; do
    dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -q "install ok installed" || missing+=("$pkg")
  done
  if ((${#missing[@]})); then
    apt_update
    apt-get install -y -q --no-install-recommends "${missing[@]}"
  fi
}

# Ghi file chỉ khi nội dung thay đổi; trả về 0 nếu có thay đổi.
write_if_changed() {
  local dest=$1 mode=${2:-0644} tmp
  tmp=$(mktemp)
  cat >"$tmp"
  if [[ -f $dest ]] && cmp -s "$tmp" "$dest"; then
    rm -f "$tmp"
    return 1
  fi
  install -D -m "$mode" "$tmp" "$dest"
  rm -f "$tmp"
  return 0
}

# Tải bản phát hành GitHub và kiểm tra sha256 với sha256sums.txt của bản đó.
# download_release <base_url> <file> <dest_dir>
download_release() {
  local base=$1 file=$2 dest=$3
  mkdir -p "$dest"
  curl -fsSL --retry 3 -o "${dest}/${file}" "${base}/${file}"
  curl -fsSL --retry 3 -o "${dest}/sha256sums.txt" "${base}/sha256sums.txt"
  (cd "$dest" && grep " ${file}\$" sha256sums.txt | sha256sum -c -)
}
