"""Gọi obslab-fault trên VM web/db qua SSH bị giới hạn (ADR-0007), bằng OpenSSH client như tools/lib/faultssh.py.

Khóa và known_hosts nằm trong .lab-keys/ (container: mount chỉ đọc vào /lab-keys). Mỗi kết nối chỉ chạy được wrapper với
danh sách lệnh cho phép; backend vẫn kiểm tham số trước (fault_catalog) để báo lỗi sớm và rõ.
Test dùng bản giả (tests/fakes.py: FakeFaultSSH) cùng giao diện `call(host, command) -> dict`.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Protocol

REPO_KEYS = Path(__file__).resolve().parents[4] / ".lab-keys"


class FaultSSHError(Exception):
    """code: mã thoát của obslab-fault (1 điều kiện không đạt, 2 tham số sai, 3 VM đang bận); None: không kết nối được."""

    def __init__(self, message: str, code: int | None = None) -> None:
        super().__init__(message)
        self.code = code

    @property
    def unreachable(self) -> bool:
        return self.code is None or self.code == 255


class FaultSSH(Protocol):
    def call(self, host: str, command: str) -> dict[str, Any]: ...


class OpenSSHFaultClient:
    def __init__(self, keys_dir: str, vm_ips: dict[str, str], timeout: float = 15.0) -> None:
        d = Path(keys_dir)
        self.keys = d if d.is_dir() else REPO_KEYS
        self.vm_ips, self.timeout = vm_ips, timeout

    def _argv(self, host: str, command: str) -> list[str]:
        exe = shutil.which("ssh") or "ssh"
        return [exe, "-F", "none", "-T", "-i", str(self.keys / "obslab_fault_ed25519"),
                "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes", "-o", "IdentityAgent=none",
                "-o", "StrictHostKeyChecking=yes", "-o", f"UserKnownHostsFile={(self.keys / 'known_hosts').as_posix()}",
                "-o", "ConnectTimeout=8", "-o", "LogLevel=ERROR", f"obslab-fault@{self.vm_ips[host]}", "--", command]

    def call(self, host: str, command: str) -> dict[str, Any]:
        if host not in self.vm_ips:
            raise FaultSSHError(f"VM không hợp lệ: {host}", 2)
        try:
            cp = subprocess.run(self._argv(host, command), stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=self.timeout)
        except subprocess.TimeoutExpired:
            raise FaultSSHError(f"{host}: quá {self.timeout:.0f} s không phản hồi") from None
        except OSError as e:
            raise FaultSSHError(f"Không chạy được ssh: {e}") from None
        if cp.returncode != 0:
            raise FaultSSHError(f"{host}: {(cp.stderr or cp.stdout).strip() or 'lỗi không rõ'}", cp.returncode)
        try:
            return json.loads(cp.stdout)
        except json.JSONDecodeError:
            raise FaultSSHError(f"{host}: kết quả không đọc được: {cp.stdout.strip()[:200]}") from None
