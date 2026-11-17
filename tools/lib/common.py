"""Tiện ích dùng chung cho các script của lab. Chỉ dùng thư viện chuẩn của Python (>= 3.9).

Chạy được trên Windows (PowerShell) lẫn WSL/Linux, miễn là lệnh `docker` dùng được từ shell đó.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
ALERT_LOG = DATA_DIR / "alerts" / "alerts.jsonl"
EVENT_LOG = DATA_DIR / "events" / "faults.jsonl"
RESULTS_DIR = ROOT / "results"

# Tránh lỗi in tiếng Việt trên console Windows dùng code page cũ.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass

DEFAULTS = {
    "PROMETHEUS_PORT": "9090",
    "ALERTMANAGER_PORT": "9093",
    "GRAFANA_PORT": "3000",
    "WEBHOOK_PORT": "5001",
    "SVC_API_PORT": "8001",
    "SVC_ORDERS_PORT": "8002",
    "SVC_PAYMENTS_PORT": "8003",
    "GRAFANA_ADMIN_USER": "admin",
    "GRAFANA_ADMIN_PASSWORD": "admin-lab-only",
}


def load_env() -> dict:
    """Đọc .env (nếu có) giống cách docker compose làm, trả về dict đã gộp giá trị mặc định."""
    env = dict(DEFAULTS)
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    for k in DEFAULTS:
        if k in os.environ:
            env[k] = os.environ[k]
    return env


ENV = load_env()
PROM_URL = os.getenv("PROM_URL", f"http://localhost:{ENV['PROMETHEUS_PORT']}")
AM_URL = os.getenv("AM_URL", f"http://localhost:{ENV['ALERTMANAGER_PORT']}")
GRAFANA_URL = os.getenv("GRAFANA_URL", f"http://localhost:{ENV['GRAFANA_PORT']}")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", f"http://localhost:{ENV['WEBHOOK_PORT']}")
SERVICE_PORTS = {
    "svc-api": ENV["SVC_API_PORT"],
    "svc-orders": ENV["SVC_ORDERS_PORT"],
    "svc-payments": ENV["SVC_PAYMENTS_PORT"],
}


# ----------------------------------------------------------------------------- thời gian
def now_ts() -> float:
    return time.time()


def iso(ts: Optional[float]) -> str:
    if ts is None:
        return ""
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(timespec="milliseconds")


def parse_iso(value: Optional[str]) -> Optional[float]:
    """Parse ISO-8601 (kể cả dạng nano giây của Prometheus/Alertmanager) -> epoch giây."""
    if not value:
        return None
    v = value.strip().replace("Z", "+00:00")
    if "." in v:
        head, rest = v.split(".", 1)
        frac = ""
        i = 0
        while i < len(rest) and rest[i].isdigit():
            frac += rest[i]
            i += 1
        v = f"{head}.{frac[:6].ljust(6, '0')}{rest[i:]}"
    try:
        dt = datetime.fromisoformat(v)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    if dt.year < 1970:  # "0001-01-01T00:00:00Z" = chưa kết thúc
        return None
    return dt.timestamp()


def stamp() -> str:
    """Chuỗi thời gian an toàn cho tên file (giờ địa phương)."""
    return datetime.now().strftime("%Y%m%d-%H%M%S")


# ----------------------------------------------------------------------------- HTTP
def http(method: str, url: str, body: Any = None, timeout: float = 10, auth: Optional[tuple] = None) -> Any:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if auth:
        token = base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
        headers["Authorization"] = f"Basic {token}"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw.decode(errors="replace")


def prom_query(expr: str, at: Optional[float] = None) -> list:
    params = {"query": expr}
    if at is not None:
        params["time"] = str(at)
    res = http("GET", f"{PROM_URL}/api/v1/query?{urllib.parse.urlencode(params)}")
    if res.get("status") != "success":
        raise RuntimeError(f"Prometheus lỗi: {res}")
    return res["data"]["result"]


def prom_scalar(expr: str, default: Optional[float] = None) -> Optional[float]:
    try:
        r = prom_query(expr)
    except Exception:
        return default
    if not r:
        return default
    try:
        return float(r[0]["value"][1])
    except (KeyError, IndexError, ValueError):
        return default


def prom_query_range(expr: str, start: float, end: float, step: float) -> list:
    """query_range có chia nhỏ để không vượt giới hạn 11.000 điểm/series của Prometheus."""
    merged: dict = {}
    chunk = step * 10000
    t = start
    while t < end:
        t_end = min(end, t + chunk)
        params = {"query": expr, "start": str(t), "end": str(t_end), "step": str(step)}
        res = http("GET", f"{PROM_URL}/api/v1/query_range?{urllib.parse.urlencode(params)}", timeout=60)
        if res.get("status") != "success":
            raise RuntimeError(f"Prometheus lỗi: {res}")
        for s in res["data"]["result"]:
            key = json.dumps(s["metric"], sort_keys=True)
            merged.setdefault(key, {"metric": s["metric"], "values": []})["values"].extend(s["values"])
        t = t_end + step
    return list(merged.values())


def receiver_clock_offset() -> Optional[float]:
    """Độ lệch đồng hồ (giây) giữa webhook-receiver (trong Docker) và máy chạy script.

    offset = đồng hồ receiver - đồng hồ local. Dùng để quy đổi thời điểm gây lỗi sang cùng
    hệ quy chiếu với thời điểm nhận cảnh báo, tránh sai số do đồng hồ WSL2 trôi.
    """
    best = None
    for _ in range(3):
        try:
            t0 = time.time()
            r = http("GET", f"{WEBHOOK_URL}/now", timeout=3)
            t1 = time.time()
        except Exception:
            continue
        rtt = t1 - t0
        off = float(r["ts"]) - (t0 + t1) / 2
        if best is None or rtt < best[0]:
            best = (rtt, off)
    return None if best is None else round(best[1], 3)


# ----------------------------------------------------------------------------- docker
def run(cmd: list, check: bool = True, capture: bool = True, timeout: Optional[float] = 120) -> subprocess.CompletedProcess:
    print("  $ " + " ".join(cmd), flush=True)
    try:
        cp = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=capture, timeout=timeout,
                            encoding="utf-8", errors="replace")
    except FileNotFoundError:
        sys.exit(f"Không tìm thấy lệnh '{cmd[0]}'. Hãy cài Docker Desktop và đảm bảo 'docker' có trong PATH.")
    if capture and cp.stdout.strip():
        print("    " + cp.stdout.strip().replace("\n", "\n    "))
    if check and cp.returncode != 0:
        err = (cp.stderr or "").strip()
        raise RuntimeError(f"Lệnh thất bại ({cp.returncode}): {' '.join(cmd)}\n{err}")
    return cp


def compose(*args: str, check: bool = True, timeout: Optional[float] = 120) -> subprocess.CompletedProcess:
    return run(["docker", "compose", *args], check=check, timeout=timeout)


# ----------------------------------------------------------------------------- log
def append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list:
    if not path.exists():
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"bỏ qua dòng hỏng {path.name}:{n}", file=sys.stderr)
    return out


def labels_match(labels: dict, want: dict) -> bool:
    return all(labels.get(k) == v for k, v in want.items())


# ----------------------------------------------------------------------------- thống kê
def percentile(sorted_vals: list, q: float) -> float:
    """Phân vị nội suy tuyến tính (giống numpy 'linear'). sorted_vals phải đã sắp xếp."""
    if not sorted_vals:
        return float("nan")
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = (len(sorted_vals) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def describe(values: Iterable[float]) -> dict:
    vals = sorted(v for v in values if v == v)  # loại NaN
    n = len(vals)
    if n == 0:
        return {"n": 0}
    mean = sum(vals) / n
    var = sum((v - mean) ** 2 for v in vals) / (n - 1) if n > 1 else 0.0
    return {
        "n": n,
        "min": vals[0],
        "mean": mean,
        "std": var ** 0.5,
        "p50": percentile(vals, 0.50),
        "p90": percentile(vals, 0.90),
        "p95": percentile(vals, 0.95),
        "p99": percentile(vals, 0.99),
        "max": vals[-1],
    }


def fmt(v: Any, digits: int = 3) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        if v != v:
            return "NaN"
        return f"{v:.{digits}f}"
    return str(v)


def md_table(headers: list, rows: list) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c).replace("|", "\\|") for c in r) + " |")
    return "\n".join(out)
