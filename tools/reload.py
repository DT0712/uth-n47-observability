"""Kiểm tra cú pháp cấu hình rồi nạp lại Prometheus và Alertmanager (không cần restart container).

  python tools/reload.py              # kiểm tra + reload
  python tools/reload.py --check-only # chỉ kiểm tra

Dùng sau khi sửa monitor/prometheus/prometheus.yml, monitor/prometheus/rules/*.yml (vd. chốt ngưỡng) hoặc
monitor/alertmanager/alertmanager.yml. Chạy cả unit test luật (monitor/prometheus/tests/*.test.yml). Container đọc thẳng các file này từ thư mục chia sẻ /vagrant nên
không cần provision lại; promtool/amtool chạy trong container qua `vagrant ssh monitor`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.common import AM_URL, PROM_URL, compose, http  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-only", action="store_true")
    a = ap.parse_args()

    ok = True
    for args in (
        ["exec", "-T", "prometheus", "promtool", "check", "config", "/etc/prometheus/prometheus.yml"],
        ["exec", "-T", "alertmanager", "amtool", "check-config", "/etc/alertmanager/alertmanager.yml"],
        ["exec", "-T", "prometheus", "sh", "-c", "'promtool test rules /etc/prometheus/tests/*.test.yml'"],
    ):
        cp = compose(*args, check=False)
        if cp.returncode != 0:
            ok = False
            print(cp.stderr)
    if not ok:
        sys.exit("Cấu hình có lỗi — KHÔNG reload.")
    print("Cấu hình hợp lệ.")
    if a.check_only:
        return
    for name, url in (("Prometheus", f"{PROM_URL}/-/reload"), ("Alertmanager", f"{AM_URL}/-/reload")):
        http("POST", url)
        print(f"Đã reload {name}.")
    print(f"Kiểm tra ngưỡng đang dùng: {PROM_URL}/graph?g0.expr=%7B__name__%3D~%22lab%3Athreshold%3A.*%22%7D")


if __name__ == "__main__":
    main()
