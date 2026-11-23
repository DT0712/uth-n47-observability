"""Gọi obslab-fault trên VM web/db qua SSH bị giới hạn (ADR-0007). Dùng chung cho check_fault_ssh.py và fault.py."""

from __future__ import annotations

import atexit
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

from .common import ENV, ROOT

KEY_DIR = ROOT / ".lab-keys"
KEY = KEY_DIR / "obslab_fault_ed25519"
KNOWN_HOSTS = KEY_DIR / "known_hosts"
VM_IPS = {"web": ENV.get("VM_WEB_IP", "192.168.56.11"), "db": ENV.get("VM_DB_IP", "192.168.56.12")}

_key_cache: Path | None = None


def ssh_exe() -> str:
    """Trên Windows luôn dùng OpenSSH của hệ thống (Git Bash có ssh riêng hiểu quyền file khác)."""
    if os.name == "nt":
        p = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "OpenSSH" / "ssh.exe"
        if p.exists():
            return str(p)
    exe = shutil.which("ssh")
    if not exe:
        sys.exit("Không tìm thấy lệnh ssh. Windows: Settings → Optional features → OpenSSH Client.")
    return exe


def private_key() -> Path:
    """Đường dẫn khóa có quyền đủ chặt để ssh chấp nhận."""
    global _key_cache
    if _key_cache:
        return _key_cache
    if not KEY.exists() or not KNOWN_HOSTS.exists():
        sys.exit(f"Chưa có khóa lab trong {KEY_DIR}. Chạy: vagrant provision web db")
    if os.name == "nt":
        # Bỏ quyền thừa kế, chỉ để lại người dùng hiện tại (ssh.exe từ chối khóa mà người khác đọc được).
        user = f"{os.environ['USERDOMAIN']}\\{os.environ['USERNAME']}"
        cp = subprocess.run(["icacls", str(KEY), "/inheritance:r", "/grant:r", f"{user}:F"],
                            capture_output=True, text=True, errors="replace")
        if cp.returncode != 0:
            sys.exit(f"Không đặt được quyền cho khóa lab: {cp.stdout}{cp.stderr}")
        _key_cache = KEY
    elif KEY.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        # WSL: ổ Windows (/mnt/...) hiện quyền 0777 -> dùng bản chép tạm 0600.
        d = Path(tempfile.mkdtemp(prefix="obslab-"))
        atexit.register(shutil.rmtree, d, ignore_errors=True)
        _key_cache = d / "key"
        _key_cache.touch(mode=0o600)
        _key_cache.write_bytes(KEY.read_bytes())
    else:
        _key_cache = KEY
    return _key_cache


def ssh_base(vm: str, user: str = "obslab-fault") -> list:
    return [
        ssh_exe(), "-F", "none", "-T", "-i", str(private_key()),
        "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes", "-o", "IdentityAgent=none",
        "-o", "StrictHostKeyChecking=yes", "-o", f'UserKnownHostsFile="{KNOWN_HOSTS.as_posix()}"',
        "-o", "ConnectTimeout=8", "-o", "LogLevel=ERROR",
        f"{user}@{VM_IPS[vm]}",
    ]


def fault_ssh(vm: str, command: str, timeout: float = 60) -> subprocess.CompletedProcess:
    """Gửi một lệnh tới obslab-fault. Không in, không ném lỗi: người gọi xem returncode/stdout/stderr."""
    # "--": để ssh không hiểu lệnh bắt đầu bằng '-' là tùy chọn của chính nó.
    return subprocess.run([*ssh_base(vm), "--", command], stdin=subprocess.DEVNULL, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)
