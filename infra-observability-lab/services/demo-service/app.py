"""Dịch vụ demo đóng vai một "máy chủ/dịch vụ lab".

Endpoint:
  GET  /health          kiểm tra sống (bị ảnh hưởng bởi lỗi giả lập latency / health_fail)
  GET  /metrics         metric Prometheus
  GET  /api/work        endpoint nghiệp vụ giả lập (bị ảnh hưởng bởi latency / error_rate)
  GET  /admin/fault     xem trạng thái lỗi giả lập
  POST /admin/fault     đặt lỗi giả lập: {"latency_ms": 3000, "error_rate": 0.5, "health_fail": false}
  POST /admin/reset     xoá mọi lỗi giả lập

Endpoint /admin/* chỉ dành cho script kịch bản lỗi trong lab (cổng chỉ bind 127.0.0.1).
"""

from __future__ import annotations

import asyncio
import os
import random
import time

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from pydantic import BaseModel, Field

SERVICE_NAME = os.getenv("SERVICE_NAME", "demo-service")
BASE_LATENCY_MS = float(os.getenv("BASE_LATENCY_MS", "20"))
DATA_DIR = os.getenv("DATA_DIR", "")

app = FastAPI(title=SERVICE_NAME)

REQUESTS = Counter(
    "http_requests_total",
    "Tổng số request HTTP",
    ["service", "method", "path", "status"],
)
LATENCY = Histogram(
    "http_request_duration_seconds",
    "Thời gian xử lý request HTTP",
    ["service", "path"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 3, 5, 8, 13),
)
IN_PROGRESS = Gauge("http_requests_in_progress", "Request đang xử lý", ["service"])
FAULT_ACTIVE = Gauge(
    "lab_fault_active",
    "Lỗi giả lập đang bật (1) hay tắt (0), theo loại",
    ["service", "fault"],
)
FAULT_VALUE = Gauge(
    "lab_fault_value",
    "Tham số lỗi giả lập (latency_ms, error_rate)",
    ["service", "param"],
)
START_TIME = Gauge("lab_service_start_time_seconds", "Thời điểm tiến trình khởi động", ["service"])
START_TIME.labels(SERVICE_NAME).set_to_current_time()


class FaultConfig(BaseModel):
    latency_ms: float = Field(0, ge=0, le=60000)
    error_rate: float = Field(0, ge=0, le=1)
    health_fail: bool = False


fault = FaultConfig()


def _publish_fault_metrics() -> None:
    FAULT_ACTIVE.labels(SERVICE_NAME, "latency").set(1 if fault.latency_ms > 0 else 0)
    FAULT_ACTIVE.labels(SERVICE_NAME, "errors").set(1 if fault.error_rate > 0 else 0)
    FAULT_ACTIVE.labels(SERVICE_NAME, "health_fail").set(1 if fault.health_fail else 0)
    FAULT_VALUE.labels(SERVICE_NAME, "latency_ms").set(fault.latency_ms)
    FAULT_VALUE.labels(SERVICE_NAME, "error_rate").set(fault.error_rate)


_publish_fault_metrics()

UNTRACKED = {"/metrics"}


@app.middleware("http")
async def observe(request: Request, call_next):
    path = request.url.path
    if path in UNTRACKED or path.startswith("/admin"):
        return await call_next(request)
    # Gom path lạ vào một nhãn để tránh bùng nổ cardinality.
    label_path = path if path in {"/", "/health", "/api/work"} else "other"
    IN_PROGRESS.labels(SERVICE_NAME).inc()
    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        LATENCY.labels(SERVICE_NAME, label_path).observe(time.perf_counter() - start)
        REQUESTS.labels(SERVICE_NAME, request.method, label_path, str(status)).inc()
        IN_PROGRESS.labels(SERVICE_NAME).dec()


async def _simulated_delay(base_ms: float) -> None:
    jitter = random.uniform(0.5, 1.5) * base_ms
    await asyncio.sleep((jitter + fault.latency_ms) / 1000.0)


@app.get("/")
async def root():
    return {"service": SERVICE_NAME, "endpoints": ["/health", "/metrics", "/api/work"]}


@app.get("/health")
async def health():
    if fault.latency_ms > 0:
        await asyncio.sleep(fault.latency_ms / 1000.0)
    if fault.health_fail:
        return JSONResponse({"status": "fail", "service": SERVICE_NAME}, status_code=503)
    return {"status": "ok", "service": SERVICE_NAME}


@app.get("/api/work")
async def work():
    await _simulated_delay(BASE_LATENCY_MS)
    if fault.error_rate > 0 and random.random() < fault.error_rate:
        return JSONResponse({"error": "simulated failure", "service": SERVICE_NAME}, status_code=500)
    return {"service": SERVICE_NAME, "result": random.randint(1, 1000)}


@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/admin/fault")
async def get_fault():
    return {"service": SERVICE_NAME, "fault": fault.model_dump(), "data_dir": DATA_DIR or None}


@app.post("/admin/fault")
async def set_fault(cfg: FaultConfig):
    global fault
    fault = cfg
    _publish_fault_metrics()
    return {"service": SERVICE_NAME, "fault": fault.model_dump(), "set_at": time.time()}


@app.post("/admin/reset")
async def reset_fault():
    global fault
    fault = FaultConfig()
    _publish_fault_metrics()
    return {"service": SERVICE_NAME, "fault": fault.model_dump(), "reset_at": time.time()}
