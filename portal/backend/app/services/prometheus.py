"""Client Prometheus CHỈ ĐỌC, có timeout và bộ nhớ đệm ngắn.

- Chỉ gọi /api/v1/query, /api/v1/query_range và /-/ready. Không có API nào ghi vào Prometheus.
- Timeout 5 s: Prometheus chậm hay chết thì portal trả lỗi nhanh (hoặc metrics_available=false), không treo.
- Cache 15 s (bằng chu kỳ scrape) theo (biểu thức, khoảng thời gian), nhớ cả lỗi: nhiều người mở trang cùng lúc vẫn chỉ tạo mỗi
  truy vấn một lần mỗi 15 s. Khoảng thời gian của query_range được làm tròn theo bước để cache trúng.
- Biểu thức chỉ đến từ danh mục dựng sẵn trong services/monitoring.py, không bao giờ từ người dùng.
"""

from __future__ import annotations

import math
import re
import threading
import time
from typing import Any, Protocol

import httpx


class PrometheusError(Exception):
    pass


class PrometheusAPI(Protocol):
    def query(self, expr: str) -> list[dict[str, Any]]: ...
    def query_range(self, expr: str, start: float, end: float, step: float) -> list[dict[str, Any]]: ...
    def ready(self) -> bool: ...


class PrometheusClient:
    def __init__(self, base_url: str, timeout: float = 5.0, cache_ttl: float = 15.0,
                 transport: httpx.BaseTransport | None = None) -> None:
        self._http = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout, transport=transport)
        self._ttl = cache_ttl
        self._cache: dict[tuple, tuple[float, Any]] = {}
        self._lock = threading.Lock()
        self.requests = 0  # số request thật đã gửi (để test và theo dõi tải)

    def _cached(self, key: tuple, fetch) -> Any:
        now = time.monotonic()
        with self._lock:
            hit = self._cache.get(key)
            if hit and now - hit[0] < self._ttl:
                if isinstance(hit[1], PrometheusError):
                    raise hit[1]
                return hit[1]
        try:
            value = fetch()
        except PrometheusError as e:  # nhớ cả lỗi 15 s: Prometheus chết thì không thử lại mỗi request
            with self._lock:
                self._cache[key] = (now, e)
            raise
        with self._lock:
            self._cache[key] = (now, value)
            if len(self._cache) > 500:  # chặn bộ nhớ: bỏ các mục cũ nhất
                for k, _ in sorted(self._cache.items(), key=lambda kv: kv[1][0])[:250]:
                    self._cache.pop(k, None)
        return value

    def _get(self, path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        self.requests += 1
        try:
            r = self._http.get(path, params=params)
            body = r.json()
        except (httpx.HTTPError, ValueError) as e:
            raise PrometheusError(f"Không truy vấn được Prometheus: {e}") from None
        if r.status_code != 200 or body.get("status") != "success":
            raise PrometheusError(f"Prometheus lỗi {r.status_code}: {body.get('error', '')}")
        return body["data"]["result"]

    def query(self, expr: str, cache: bool = True) -> list[dict[str, Any]]:
        fetch = lambda: self._get("/api/v1/query", {"query": expr})  # noqa: E731
        return self._cached(("q", expr), fetch) if cache else fetch()

    def rule_last_evaluation(self, rule: str) -> float | None:
        """lastEvaluation (epoch giây) của nhóm chứa recording rule `rule`; không cache (dùng đo trễ đánh giá luật)."""
        from app.core.timeutil import parse_am_time
        self.requests += 1
        try:
            body = self._http.get("/api/v1/rules", params={"type": "record"}).json()
        except (httpx.HTTPError, ValueError) as e:
            raise PrometheusError(f"Không truy vấn được Prometheus: {e}") from None
        for g in body.get("data", {}).get("groups", []):
            if any(r.get("name") == rule for r in g.get("rules", [])):
                t = parse_am_time(g.get("lastEvaluation"))
                return t.timestamp() if t else None
        return None

    def query_range(self, expr: str, start: float, end: float, step: float) -> list[dict[str, Any]]:
        start, end = math.floor(start / step) * step, math.ceil(end / step) * step
        return self._cached(("r", expr, start, end, step),
                            lambda: self._get("/api/v1/query_range",
                                              {"query": expr, "start": start, "end": end, "step": step}))

    def ready(self) -> bool:
        def fetch() -> bool:
            try:
                self.requests += 1
                return self._http.get("/-/ready", timeout=2.0).status_code == 200
            except httpx.HTTPError:
                return False
        return self._cached(("ready",), fetch)


# ------------------------------------------------------------------ dựng PromQL an toàn
def quote(value: str) -> str:
    """Chuỗi PromQL trong dấu nháy kép, thoát \\ và \"."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def selector(metric: str, labels: dict[str, str] | None = None, regex: dict[str, list[str]] | None = None) -> str:
    """metric{a="x", b=~"p|q"} — nhãn đã được kiểm ở schema; vẫn thoát ký tự cho chắc."""
    parts = [f"{k}={quote(v)}" for k, v in (labels or {}).items() if re.fullmatch(r"[a-zA-Z_]\w*", k)]
    for k, values in (regex or {}).items():
        if re.fullmatch(r"[a-zA-Z_]\w*", k):
            parts.append(f"{k}=~{quote('|'.join(re.escape(v) for v in values) or '^$')}")
    return f"{metric}{{{', '.join(parts)}}}" if parts else metric


def as_float(value: Any) -> float | None:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) or math.isinf(f) else f
