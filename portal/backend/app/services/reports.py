"""Báo cáo các lần chạy kịch bản lỗi (UC18, FR-P15): CSV và Markdown.

Cột CSV theo tools/detection_time.py để đối chiếu portal ↔ CLI ở GĐ7. Markdown có thống kê theo trường hợp và ghi cấu
hình ảnh hưởng thời gian phát hiện (BR-07).
"""

from __future__ import annotations

import csv
import io
import statistics
from collections import defaultdict
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models as m
from app.services.fault_catalog import LAB_CONFIG

COLUMNS = ["run_id", "case", "scenario", "target", "params", "injected_at", "valid", "invalid_reason", "detected",
           "first_alert", "first_s", "root_alert", "root_s", "extra_alerts", "recover_noise", "unrelated_alerts",
           "recovered_at", "root_resolved_s", "stop_reason", "vm_clock_offset_s", "eval_lag_s"]


def case_name(run: m.FaultRun) -> str:
    if run.scenario == "service-stop":
        return f"dừng {run.params.get('service')}"
    return f"{run.scenario} {run.target_host}"


def rows(db: Session, start: datetime | None, end: datetime | None, scenario: str | None, valid_only: bool) -> list[dict]:
    stmt = select(m.FaultRun).where(m.FaultRun.status == "completed").order_by(m.FaultRun.injected_at, m.FaultRun.id)
    if start:
        stmt = stmt.where(m.FaultRun.injected_at >= start)
    if end:
        stmt = stmt.where(m.FaultRun.injected_at < end)
    if scenario:
        stmt = stmt.where(m.FaultRun.scenario == scenario)
    if valid_only:
        stmt = stmt.where(m.FaultRun.valid)
    out = []
    for run in db.scalars(stmt):
        matched = db.execute(select(m.FaultRunAlert, m.AlertEpisode.alertname).join(m.AlertEpisode).where(
            m.FaultRunAlert.fault_run_id == run.id).order_by(m.FaultRunAlert.delay_s)).all()

        def names(roles: tuple[str, ...]) -> str:
            return "; ".join(f"{name}@{a.delay_s:.1f}s" for a, name in matched if a.role in roles)

        detections = [(a, name) for a, name in matched if a.role in ("root", "expected")]
        out.append({
            "run_id": run.id, "case": case_name(run), "scenario": run.scenario, "target": run.target_host,
            "params": ";".join(f"{k}={v}" for k, v in run.params.items()),
            "injected_at": run.injected_at.isoformat(timespec="milliseconds") if run.injected_at else "",
            "valid": "yes" if run.valid else "no", "invalid_reason": "; ".join(run.invalid_reasons),
            "detected": "yes" if detections else "no",
            "first_alert": detections[0][1] if detections else "", "first_s": run.first_detection_s,
            "root_alert": run.root_alert, "root_s": run.root_detection_s,
            "extra_alerts": names(("expected",)), "recover_noise": names(("extra",)),
            "unrelated_alerts": names(("unrelated",)),
            "recovered_at": run.recovered_at.isoformat(timespec="milliseconds") if run.recovered_at else "",
            "root_resolved_s": run.root_resolved_s, "stop_reason": run.stop_reason or "",
            "vm_clock_offset_s": run.vm_clock_offset_s, "eval_lag_s": run.eval_lag_s,
        })
    return out


def to_csv(data: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLUMNS, lineterminator="\n")
    w.writeheader()
    w.writerows(data)
    return "﻿" + buf.getvalue()  # BOM để Excel đọc đúng tiếng Việt


def _fmt(v: float | None) -> str:
    return "" if v is None else f"{v:.1f}".replace(".", ",")


def to_markdown(data: list[dict], generated_at: datetime) -> str:
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in data:
        groups[r["case"]].append(r)
    table = ["| Trường hợp | Cảnh báo gốc | Số lần | Phát hiện | Min (s) | TB (s) | Trung vị (s) | Max (s) | Độ lệch chuẩn |",
             "|---|---|---|---|---|---|---|---|---|"]
    for case, rs in sorted(groups.items()):
        vals = [r["root_s"] for r in rs if r["root_s"] is not None]
        table.append(f"| {case} | {rs[0]['root_alert']} | {len(rs)} | {sum(r['detected'] == 'yes' for r in rs)} | "
                     f"{_fmt(min(vals)) if vals else ''} | {_fmt(statistics.mean(vals)) if vals else ''} | "
                     f"{_fmt(statistics.median(vals)) if vals else ''} | {_fmt(max(vals)) if vals else ''} | "
                     f"{_fmt(statistics.stdev(vals)) if len(vals) > 1 else ''} |")
    noisy = [r for r in data if r["extra_alerts"] or r["recover_noise"]]
    lines = [
        "# Báo cáo thời gian phát hiện (Obslab Portal)", "",
        f"- Tạo lúc: {generated_at.isoformat(timespec='seconds')} (UTC); {len(data)} lần chạy đã hoàn tất.",
        f"- Cấu hình (BR-07): scrape {LAB_CONFIG['scrape_interval_s']} s, đánh giá luật {LAB_CONFIG['evaluation_interval_s']} s, "
        f"group_wait {LAB_CONFIG['group_wait_s']} s; `for` theo từng cảnh báo gốc.",
        "- Thời gian phát hiện = lúc portal nhận cảnh báo gốc − lúc gây lỗi (T0 hiệu chỉnh theo đồng hồ monitor).",
        "", "## Theo trường hợp", "", *table, "",
        f"## Cảnh báo kèm theo: {len(noisy)}/{len(data)} lần", "",
    ]
    lines += [f"- #{r['run_id']} {r['case']}: kèm {r['extra_alerts'] or '—'}; sau khi gỡ {r['recover_noise'] or '—'}"
              for r in noisy] or ["Không có."]
    return "\n".join(lines) + "\n"
