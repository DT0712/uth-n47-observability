"""Webhook receiver nhận cảnh báo từ Alertmanager và ghi lại THỜI ĐIỂM NHẬN.

Mỗi alert trong payload được ghi thành một dòng JSON (JSON Lines) vào ALERT_LOG_FILE.
File này được tools/detection_time.py dùng để tính thời gian phát hiện.

Endpoint:
  POST /alerts     Alertmanager gửi webhook vào đây
  GET  /alerts     xem N cảnh báo gần nhất (?limit=50)
  GET  /now        đồng hồ của container (dùng để đồng bộ mốc thời gian với script gây lỗi)
  GET  /health     kiểm tra sống
  GET  /metrics    metric Prometheus
"""

from __future__ import annotations

import json
import os
import threading
import time
from collections import deque
from datetime import datetime, timezone

from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest

LOG_FILE = os.getenv("ALERT_LOG_FILE", "/data/alerts.jsonl")
os.makedirs(os.path.dirname(LOG_FILE) or ".", exist_ok=True)

app = FastAPI(title="alert-webhook-receiver")
_lock = threading.Lock()
_recent: deque = deque(maxlen=500)

RECEIVED = Counter(
    "lab_webhook_alerts_received_total",
    "Số alert nhận được từ Alertmanager",
    ["alertname", "status"],
)
LAST_RECEIVED = Gauge("lab_webhook_last_received_timestamp_seconds", "Thời điểm nhận webhook gần nhất")


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(timespec="milliseconds")


@app.post("/alerts")
async def receive(request: Request):
    received_ts = time.time()  # lấy mốc thời gian NGAY khi nhận, trước khi xử lý
    payload = await request.json()
    records = []
    for alert in payload.get("alerts", []):
        labels = alert.get("labels", {})
        rec = {
            "received_at": _iso(received_ts),
            "received_ts": round(received_ts, 3),
            "status": alert.get("status"),
            "alertname": labels.get("alertname"),
            "severity": labels.get("severity"),
            "labels": labels,
            "annotations": alert.get("annotations", {}),
            "startsAt": alert.get("startsAt"),
            "endsAt": alert.get("endsAt"),
            "fingerprint": alert.get("fingerprint"),
            "groupKey": payload.get("groupKey"),
            "receiver": payload.get("receiver"),
        }
        records.append(rec)
        RECEIVED.labels(rec["alertname"] or "unknown", rec["status"] or "unknown").inc()
    with _lock:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        _recent.extend(records)
    LAST_RECEIVED.set(received_ts)
    for rec in records:
        print(
            f"[{rec['received_at']}] {rec['status']:<8} {rec['alertname']} "
            f"{ {k: v for k, v in rec['labels'].items() if k not in ('alertname',)} }",
            flush=True,
        )
    return {"ok": True, "count": len(records)}


@app.get("/alerts")
async def recent(limit: int = 50):
    with _lock:
        items = list(_recent)[-limit:]
    return {"count": len(items), "alerts": items}


@app.get("/now")
async def now():
    ts = time.time()
    return {"ts": ts, "iso": _iso(ts)}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
