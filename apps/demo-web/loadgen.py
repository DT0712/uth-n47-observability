"""Sinh tải nhẹ và đều tới các dịch vụ demo để metric luôn có dữ liệu.

Biến môi trường:
  TARGETS  danh sách base URL, phân tách bởi dấu phẩy
  RPS      tổng số request/giây (mặc định 5)
"""

from __future__ import annotations

import os
import random
import threading
import time
import urllib.error
import urllib.request

TARGETS = [t.strip().rstrip("/") for t in os.getenv("TARGETS", "").split(",") if t.strip()]
RPS = max(0.1, float(os.getenv("RPS", "5")))
TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "15"))


def hit(url: str) -> None:
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as resp:
            resp.read()
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
        pass  # lỗi đã được dịch vụ đích ghi nhận vào metric; loadgen chỉ việc tiếp tục


def main() -> None:
    if not TARGETS:
        raise SystemExit("TARGETS trống")
    print(f"loadgen: {RPS} rps -> {TARGETS}", flush=True)
    interval = 1.0 / RPS
    while True:
        base = random.choice(TARGETS)
        r = random.random()
        path = "/api/work" if r < 0.8 else "/api/db" if r < 0.9 else "/"
        # Chạy trong thread để một request chậm không chặn cả vòng lặp.
        threading.Thread(target=hit, args=(base + path,), daemon=True).start()
        time.sleep(interval)


if __name__ == "__main__":
    main()
