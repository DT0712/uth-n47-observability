"""Kiểm tra đường SSH bị giới hạn và các kịch bản lỗi trên VM web, db (ADR-0007).

  python tools/check_fault_ssh.py              # giới hạn SSH + kiểm tra tham số (không gây lỗi nào, ~20 giây)
  python tools/check_fault_ssh.py --scenarios  # thêm: chạy thật từng kịch bản 30 giây và chờ tự khôi phục (~10 phút)

Phần 1 khẳng định khóa của lab KHÔNG làm được gì ngoài các lệnh cho phép.
Phần 2 khẳng định mỗi kịch bản thật sự tác động, và tự gỡ khi hết hạn (không ai gọi stop).
Thoát mã 1 nếu có mục thất bại.
"""

from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.common import http, vm_exec  # noqa: E402
from lib.faultssh import VM_IPS, fault_ssh, private_key, ssh_base  # noqa: E402

failures = 0


def report(ok: bool, desc: str, detail: str = "") -> None:
    global failures
    if not ok:
        failures += 1
    print(f"  [{'OK' if ok else 'LỖI'}] {desc}" + (f"  <- {detail}" if detail and not ok else ""), flush=True)


def expect_reject(vm: str, command: str, codes: tuple, desc: str) -> None:
    cp = fault_ssh(vm, command)
    leaked = "uid=" in cp.stdout or "root:" in cp.stdout
    report(cp.returncode in codes and not leaked, f"{vm}: {desc}", f"mã {cp.returncode}: {cp.stdout}{cp.stderr}".strip())


def expect_json(vm: str, command: str) -> dict:
    cp = fault_ssh(vm, command)
    try:
        d = json.loads(cp.stdout)
    except json.JSONDecodeError:
        d = {}
    report(cp.returncode == 0 and d.get("ok") is True, f"{vm}: {command}", f"mã {cp.returncode}: {cp.stdout}{cp.stderr}".strip())
    return d


def check_restrictions() -> None:
    for vm in VM_IPS:
        print(f"== {vm}: lệnh hợp lệ")
        # Không kết nối được thì mọi mục "bị từ chối" bên dưới sẽ đạt giả -> dừng ngay.
        if not expect_json(vm, "list"):
            sys.exit(f"Không gọi được obslab-fault trên {vm}; kiểm tra VM đang chạy và đã provision fault_agent.")
        st = expect_json(vm, "status")
        if st.get("active"):
            sys.exit(f"VM {vm} đang có kịch bản {st.get('scenario')} chạy; gỡ trước rồi kiểm tra lại.")

        print(f"== {vm}: lệnh bị chặn ở wrapper (mã 126)")
        for cmd, desc in [
            ("", "không có lệnh (xin shell)"),
            ("id; cat /etc/shadow", "nối lệnh bằng ;"),
            ("status && id", "nối lệnh bằng &&"),
            ("status | id", "pipe"),
            ("status $(id)", "thế lệnh $( )"),
            ("status `id`", "thế lệnh backtick"),
            ("status\nid", "xuống dòng"),
            ("status > /tmp/x", "chuyển hướng"),
            ("/bin/bash", "đường dẫn tuyệt đối"),
            ("cpu start ../../x=1", "đường dẫn tương đối"),
            ("--help", "tham số kiểu tùy chọn"),
            ("status " + "a" * 300, "lệnh quá dài"),
        ]:
            expect_reject(vm, cmd, (126,), desc)

        print(f"== {vm}: lệnh bị chặn ở obslab-fault (mã 2)")
        for cmd in ["bash", "reboot start", "cpu", "cpu restart", "cpu start duration=5", "cpu start duration=99999",
                    "cpu start duration=abc", "cpu start service=nginx", "disk start percent=100",
                    "service-stop start", "service-stop start service=ssh", "status now"]:
            expect_reject(vm, cmd, (2,), cmd)
        if vm == "db":
            expect_reject(vm, "latency start", (2,), "latency start (chỉ có trên web)")
            expect_reject(vm, "service-stop start service=nginx", (2,), "service-stop nginx (không có trên db)")

        print(f"== {vm}: kênh SSH")
        base = ssh_base(vm)
        verbose = [x if x != "LogLevel=ERROR" else "LogLevel=INFO" for x in base]
        cp = subprocess.run([*verbose[:-1], "-tt", verbose[-1], "status"], stdin=subprocess.DEVNULL, capture_output=True,
                            text=True, errors="replace", timeout=30)
        report("PTY allocation request failed" in cp.stderr, f"{vm}: không cấp PTY", cp.stderr.strip())

        # Chuyển tiếp cổng: ssh -W yêu cầu server mở kết nối tới 127.0.0.1:22 -> phải bị từ chối.
        cp = subprocess.run([*base[:-1], "-W", "127.0.0.1:22", base[-1]], stdin=subprocess.DEVNULL,
                            capture_output=True, text=True, errors="replace", timeout=30)
        report(cp.returncode != 0 and "SSH-2.0" not in cp.stdout, f"{vm}: không chuyển tiếp cổng", cp.stdout + cp.stderr)

        cp = subprocess.run([*base[:-1], "-s", base[-1], "sftp"], stdin=subprocess.DEVNULL, capture_output=True,
                            text=True, errors="replace", timeout=30)
        report(cp.returncode == 126, f"{vm}: không có SFTP (bị wrapper chặn)", f"mã {cp.returncode}: {cp.stderr}")

        for user in ("root", "vagrant"):
            cp = subprocess.run([*ssh_base(vm, user), "id"], stdin=subprocess.DEVNULL, capture_output=True,
                                text=True, errors="replace", timeout=30)
            report(cp.returncode == 255 and "uid=" not in cp.stdout, f"{vm}: khóa lab không đăng nhập được user {user}",
                   cp.stdout + cp.stderr)


def check_source_limit() -> None:
    """Cùng khóa, cùng lệnh: gọi từ VM monitor được, gọi từ VM db sang web bị từ chối (from= trong authorized_keys)."""
    print("== Giới hạn nguồn kết nối")
    remote = ("k=$(mktemp) && cat /vagrant/.lab-keys/obslab_fault_ed25519 > $k && "
              "ssh -F none -T -i $k -o BatchMode=yes -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes "
              "-o UserKnownHostsFile=/vagrant/.lab-keys/known_hosts -o ConnectTimeout=8 "
              f"obslab-fault@{VM_IPS['web']} status; echo rc=$?; rm -f $k")
    for src, want in (("monitor", "rc=0"), ("db", "rc=255")):
        out = vm_check(src, remote)
        ok = want in out and ('"ok":true' in out) == (want == "rc=0")
        report(ok, f"{src} → web: {'được phép' if want == 'rc=0' else 'bị từ chối'}", out)


def vm_check(vm: str, command: str) -> str:
    return vm_exec(vm, command, check=False, timeout=60).stdout.strip()


def http_ok(url: str, timeout: float = 4) -> bool:
    try:
        http("GET", url, timeout=timeout)
        return True
    except Exception:
        return False


def tcp_ok(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=3):
            return True
    except OSError:
        return False


def latency() -> float:
    t = time.time()
    http("GET", f"http://{VM_IPS['web']}/api/work", timeout=15)
    return time.time() - t


def error_share(n: int = 20) -> float:
    return sum(not http_ok(f"http://{VM_IPS['web']}/api/work") for _ in range(n)) / n


def labdisk_pct(vm: str) -> float:
    a, s = vm_check(vm, "df -B1 --output=avail,size /mnt/labdisk | tail -1").split()
    return 100 * (1 - int(a) / int(s))


def check_scenarios() -> None:
    web, db = VM_IPS["web"], VM_IPS["db"]
    stress = "systemctl is-active obslab-fault-stress"
    # (vm, lệnh start, mô tả, hàm trả True khi lỗi đang tác động)
    cases = [
        ("web", "cpu start duration=30", lambda: vm_check("web", stress) == "active"),
        ("web", "disk start duration=30", lambda: labdisk_pct("web") > 93),
        ("web", "memory start duration=30 percent=90", lambda: vm_check("web", stress) == "active"),
        ("web", "service-stop start duration=30 service=nginx", lambda: not tcp_ok(web, 80)),
        ("web", "service-stop start duration=30 service=demo-app", lambda: not http_ok(f"http://{web}/health")),
        ("web", "latency start duration=30", lambda: latency() > 2.5),
        ("web", "errors start duration=30", lambda: error_share() > 0.2),
        ("db", "cpu start duration=30", lambda: vm_check("db", stress) == "active"),
        ("db", "memory start duration=30 percent=90", lambda: vm_check("db", stress) == "active"),
        ("db", "disk start duration=30", lambda: labdisk_pct("db") > 93),
        ("db", "service-stop start duration=30 service=postgresql", lambda: not tcp_ok(db, 5432)),
    ]
    for vm, cmd, active in cases:
        print(f"== {vm}: {cmd}")
        d = expect_json(vm, cmd)
        if not d:
            continue
        expect_reject(vm, "disk start", (3,), "kịch bản thứ hai cùng lúc bị từ chối (mã 3)")
        report(active(), f"{vm}: lỗi đang tác động")
        deadline = d["until_ts"] + 20
        st = {"active": True}
        # đồng hồ VM và Windows có thể lệch vài giây -> chờ theo trạng thái, không theo giờ
        limit = time.time() + 70
        while st.get("active", True) and time.time() < limit:
            time.sleep(3)
            cp = fault_ssh(vm, "status")
            st = json.loads(cp.stdout) if cp.returncode == 0 else {"active": True}
        report(st.get("active") is False and st["ts"] <= deadline, f"{vm}: tự khôi phục khi hết hạn", str(st))
        report(not active(), f"{vm}: lỗi đã được gỡ")
    print("== Sau tất cả")
    report(http_ok(f"http://{web}/health"), "http://web/health trả 2xx")
    report(http_ok(f"http://{web}/api/db", 6), "http://web/api/db trả 2xx (web → db)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scenarios", action="store_true", help="chạy thật từng kịch bản 30 giây")
    a = ap.parse_args()
    private_key()
    check_restrictions()
    check_source_limit()
    if a.scenarios:
        check_scenarios()
    print("\nTẤT CẢ ĐẠT ✓" if not failures else f"\nCÓ {failures} MỤC LỖI")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
