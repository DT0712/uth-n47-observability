"""Tiện ích dùng chung cho các script của lab. Chỉ dùng thư viện chuẩn của Python (>= 3.10).

Chạy trên Windows (PowerShell) hoặc WSL. Gọi stack giám sát qua IP host-only của VM monitor;
lệnh cần chạy trong VM (promtool, docker compose) đi qua `vagrant ssh monitor`.
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

def _read_env_file(path: Path) -> dict:
    out = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def load_env() -> dict:
    """Cấu hình lab giống Vagrantfile: biến môi trường > .env > .env.example."""
    env = _read_env_file(ROOT / ".env.example")
    env.update(_read_env_file(ROOT / ".env"))
    env.update({k: v for k, v in os.environ.items() if k in env})
    return env


ENV = load_env()
MONITOR_IP = ENV.get("VM_MONITOR_IP", "192.168.56.10")
# Gọi thẳng IP host-only của VM monitor (không phụ thuộc cổng forward). Ghi đè được bằng biến môi trường.
PROM_URL = os.getenv("PROM_URL", f"http://{MONITOR_IP}:9090")
AM_URL = os.getenv("AM_URL", f"http://{MONITOR_IP}:9093")
GRAFANA_URL = os.getenv("GRAFANA_URL", f"http://{MONITOR_IP}:3000")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", f"http://{MONITOR_IP}:5001")


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
    """Độ lệch đồng hồ (giây) giữa alert-recorder (trên VM monitor) và máy chạy script.

    offset = đồng hồ alert-recorder - đồng hồ local. Dùng để quy đổi thời điểm gây lỗi sang cùng
    hệ quy chiếu với thời điểm nhận cảnh báo, tránh sai số do đồng hồ Windows và VM lệch nhau.
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


# ----------------------------------------------------------------------------- lệnh ngoài
def run(cmd: list, check: bool = True, capture: bool = True, timeout: Optional[float] = 120) -> subprocess.CompletedProcess:
    print("  $ " + " ".join(cmd), flush=True)
    try:
        cp = subprocess.run(cmd, cwd=ROOT, text=True, stdin=subprocess.DEVNULL, capture_output=capture, timeout=timeout,
                            encoding="utf-8", errors="replace")
    except FileNotFoundError:
        sys.exit(f"Không tìm thấy lệnh '{cmd[0]}'. Hãy cài Vagrant và đảm bảo '{cmd[0]}' có trong PATH.")
    if capture and cp.stdout.strip():
        print("    " + cp.stdout.strip().replace("\n", "\n    "))
    if check and cp.returncode != 0:
        err = (cp.stderr or "").strip()
        raise RuntimeError(f"Lệnh thất bại ({cp.returncode}): {' '.join(cmd)}\n{err}")
    return cp


def vm_exec(vm: str, command: str, check: bool = True, timeout: Optional[float] = 120) -> subprocess.CompletedProcess:
    """Chạy một lệnh shell trong VM qua `vagrant ssh` (thư mục làm việc = gốc repo, nơi có Vagrantfile)."""
    # BatchMode: không bao giờ dừng lại hỏi mật khẩu. stdin rỗng để ssh không đọc bàn phím của người dùng.
    cp = run(["vagrant", "ssh", vm, "-c", command, "--", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15"],
             check=False, timeout=timeout)
    if cp.returncode == 255 and "Permission denied" in (cp.stdout or "") + (cp.stderr or ""):
        sys.exit(f"`vagrant ssh {vm}` bị từ chối khóa. Xem docs/04-trien-khai/xu-ly-su-co.md, mục SC-01.")
    if check and cp.returncode != 0:
        raise RuntimeError(f"Lệnh trên VM {vm} thất bại ({cp.returncode}): {command}\n{(cp.stderr or '').strip()}")
    return cp


def compose(*args: str, check: bool = True, timeout: Optional[float] = 120) -> subprocess.CompletedProcess:
    """docker compose của stack giám sát trên VM monitor (wrapper obslab-compose do provision/monitor.sh tạo)."""
    return vm_exec("monitor", "obslab-compose " + " ".join(args), check=check, timeout=timeout)


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


def load_events(path: Path = EVENT_LOG) -> list:
    """Sự kiện gây lỗi. fault.py ghi 2 dòng cho mỗi fault_id (lúc gây, lúc gỡ): giữ dòng cuối."""
    latest: dict = {}
    for ev in read_jsonl(path):
        latest[ev["fault_id"]] = ev
    return list(latest.values())


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
