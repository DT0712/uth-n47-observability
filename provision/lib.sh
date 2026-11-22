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

# Tải bản phát hành GitHub và kiểm tra sha256 với file checksum của chính bản đó.
# download_release <base_url> <file> <dest_dir> [tên file checksum, mặc định sha256sums.txt]
download_release() {
  local base=$1 file=$2 dest=$3 sums=${4:-sha256sums.txt}
  mkdir -p "$dest"
  curl -fsSL --retry 3 -o "${dest}/${file}" "${base}/${file}"
  curl -fsSL --retry 3 -o "${dest}/${sums}" "${base}/${sums}"
  (cd "$dest" && grep -E "[ *]${file}\$" "$sums" | sha256sum -c -)
}

# Cài một exporter dạng binary từ tarball GitHub nếu chưa đúng phiên bản. Trả 0 nếu vừa cài.
# install_exporter <tên binary> <phiên bản> <base_url> <tarball> <thư mục trong tarball hoặc ""> [checksum]
install_exporter() {
  local bin=$1 ver=$2 base=$3 tarball=$4 subdir=$5 sums=${6:-sha256sums.txt} tmp
  if [[ -x /usr/local/bin/${bin} ]] && [[ -f /usr/local/lib/obslab/${bin}.version ]] &&
     [[ $(cat "/usr/local/lib/obslab/${bin}.version") == "$ver" ]]; then
    log "${bin} ${ver} đã cài"
    return 1
  fi
  log "Cài ${bin} ${ver}"
  tmp=$(mktemp -d)
  download_release "$base" "$tarball" "$tmp" "$sums"
  tar -xzf "${tmp}/${tarball}" -C "$tmp"
  install -m 0755 "${tmp}/${subdir:+${subdir}/}${bin}" "/usr/local/bin/${bin}"
  install -d /usr/local/lib/obslab && echo "$ver" >"/usr/local/lib/obslab/${bin}.version"
  rm -rf "$tmp"
  return 0
}
