"""Công cụ gây tải cho kịch bản lỗi (chạy trong container riêng do scripts/fault.py tạo).

  python stress.py cpu --seconds 180 [--workers N]
  python stress.py memory --seconds 180 --mb 1024
"""

from __future__ import annotations

import argparse
import multiprocessing as mp
import os
import time


def _burn(deadline: float) -> None:
    x = 0
    while time.time() < deadline:
        x = (x * 1103515245 + 12345) & 0x7FFFFFFF


def cpu(seconds: float, workers: int) -> None:
    deadline = time.time() + seconds
    print(f"cpu stress: {workers} worker trong {seconds}s", flush=True)
    procs = [mp.Process(target=_burn, args=(deadline,)) for _ in range(workers)]
    for p in procs:
        p.start()
    for p in procs:
        p.join()


def memory(seconds: float, mb: int) -> None:
    print(f"memory stress: giữ {mb} MiB trong {seconds}s", flush=True)
    chunks = []
    for _ in range(mb):
        # bytearray được ghi thật để trang nhớ thực sự được cấp phát
        chunks.append(bytearray(b"\x01" * (1024 * 1024)))
    time.sleep(seconds)


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)
    c = sub.add_parser("cpu")
    c.add_argument("--seconds", type=float, default=180)
    c.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    m = sub.add_parser("memory")
    m.add_argument("--seconds", type=float, default=180)
    m.add_argument("--mb", type=int, default=1024)
    args = ap.parse_args()
    if args.mode == "cpu":
        cpu(args.seconds, args.workers)
    else:
        memory(args.seconds, args.mb)


if __name__ == "__main__":
    main()
