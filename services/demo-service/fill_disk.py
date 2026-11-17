"""Làm đầy ổ đĩa lab giới hạn tới một tỉ lệ phần trăm (kịch bản disk-full).

  python fill_disk.py --path /data --percent 95
  python fill_disk.py --path /data --clean
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys

FILLER = "lab-filler.bin"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default=os.getenv("DATA_DIR", "/data"))
    ap.add_argument("--percent", type=float, default=95.0)
    ap.add_argument("--clean", action="store_true")
    args = ap.parse_args()

    target = os.path.join(args.path, FILLER)
    if args.clean:
        if os.path.exists(target):
            os.remove(target)
        u = shutil.disk_usage(args.path)
        print(f"clean: used={100 * u.used / u.total:.1f}%")
        return

    u = shutil.disk_usage(args.path)
    want_used = u.total * args.percent / 100.0
    to_write = int(want_used - u.used)
    if to_write <= 0:
        print(f"đã đạt {100 * u.used / u.total:.1f}% >= {args.percent}%, không ghi thêm")
        return
    block = b"\0" * (1024 * 1024)
    written = 0
    try:
        with open(target, "ab") as f:
            while written < to_write:
                n = min(len(block), to_write - written)
                f.write(block[:n])
                written += n
            f.flush()
            os.fsync(f.fileno())
    except OSError as e:  # ổ đầy hẳn: vẫn là trạng thái mong muốn của kịch bản
        print(f"cảnh báo: {e}", file=sys.stderr)
    u = shutil.disk_usage(args.path)
    print(f"filled: wrote={written / 1048576:.0f}MiB used={100 * u.used / u.total:.1f}%")


if __name__ == "__main__":
    main()
