"""Vòng đời một lần chạy kịch bản lỗi và tính thời gian phát hiện (UC16, UC17; BR-05, BR-06, BR-07; NFR-07, NFR-08).

Theo docs/02-thiet-ke/so-do-tuan-tu.md (luồng 5, 6) và cùng cách tính với tools/fault.py + tools/detection_time.py:
  pending    -> kiểm điều kiện đo, gửi "<kịch bản> start duration=hold+60 ..." tới VM
  running    -> T0 = started_ts (đồng hồ VM) − độ lệch đồng hồ VM↔monitor; chờ cảnh báo (hook từ webhook)
  recovering -> đã gửi "stop" (nhận cảnh báo gốc + linger, hết hold_s, hoặc admin dừng); chờ resolved của cảnh báo gốc
  completed  -> tính first/root_detection_s, root_resolved_s; cancelled/failed khi có sự cố
T1 = lúc backend nhận webhook (alert_episodes.first_received_at), cùng đồng hồ monitor với T0.

tick() được gọi định kỳ (luồng nền mỗi 2 s trong container; test gọi tay với đồng hồ giả).
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.errors import ApiError
from app.db import models as m
from app.services import fault_catalog as cat
from app.services import reports
from app.services.fault_ssh import FaultSSH, FaultSSHError
from app.services.lab_checks import EVAL_LAG_LIMIT_S, LabChecksAPI

log = logging.getLogger(__name__)
NOTIFY_DELAY_LIMIT_S = 6.0  # cảnh báo gốc tới Alertmanager->portal chậm hơn group_wait+1 s: luật đánh giá trễ (SC-04)


def _ts(dt: datetime | None) -> float | None:
    return dt.timestamp() if dt else None


def _dt(ts: float) -> datetime:
    t = datetime.fromtimestamp(ts, tz=timezone.utc)
    return t.replace(microsecond=t.microsecond // 1000 * 1000)


class FaultRunner:
    def __init__(self, ssh: FaultSSH, checks: LabChecksAPI, clock: Clock, session_factory, resolve_wait_s: float = 180,
                 tick_s: float = 2.0) -> None:
        self.ssh, self.checks, self.clock, self.Session = ssh, checks, clock, session_factory
        self.resolve_wait_s, self.tick_s = resolve_wait_s, tick_s
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------ kiểm điều kiện đo
    def preflight(self, db: Session, host: str) -> dict[str, Any]:
        reasons: list[str] = []
        active = db.scalar(select(m.FaultRun.id).where(m.FaultRun.target_host == host,
                                                       m.FaultRun.status.in_(m.FAULT_RUN_ACTIVE)))
        if active:
            reasons.append(f"VM {host} đang có lần chạy #{active}")
        lag = self.checks.eval_lag()
        if lag is None or abs(lag) > EVAL_LAG_LIMIT_S:
            reasons.append(f"Prometheus đánh giá luật trễ {'không rõ' if lag is None else f'{lag:.1f}s'} "
                           "(khởi động lại Prometheus, xem SC-04)")
        problem = self.checks.clock_problem(host)
        if problem:
            reasons.append(problem)
        reasons += [f"Cảnh báo đang hoạt động: {a}" for a in self.checks.active_alerts()]
        return {"host": host, "clean": not reasons, "reasons": reasons, "eval_lag_s": lag,
                "vm_clock_offset_s": self.checks.clock_offset(host), "active_run_id": active}

    # ------------------------------------------------------------------ bắt đầu
    def start(self, db: Session, user: m.User, scenario: str, host: str, params: dict, hold_s: int, stop_on_alert: bool,
              linger_s: int, require_clean: bool, note: str | None) -> m.FaultRun:
        p = cat.plan(scenario, host, params, hold_s)
        pre = self.preflight(db, host)
        if pre["active_run_id"]:
            raise ApiError(409, "fault_host_busy", f"VM {host} đang có lần chạy #{pre['active_run_id']} (BR-06)")
        if require_clean and not pre["clean"]:
            raise ApiError(409, "fault_preflight_failed", "Điều kiện đo chưa đạt: " + "; ".join(pre["reasons"]))
        run = m.FaultRun(scenario=scenario, target_host=host, params=p.params, hold_s=hold_s, stop_on_alert=stop_on_alert,
                         linger_s=linger_s, root_alert=p.root_alert, expected_alerts=list(p.expected), status="pending",
                         valid=pre["clean"], invalid_reasons=pre["reasons"], note=note, requested_by=user.id,
                         requested_at=self.clock.now(), eval_lag_s=pre["eval_lag_s"],
                         vm_clock_offset_s=pre["vm_clock_offset_s"],
                         config={**cat.LAB_CONFIG, "for_s": cat.ALERT_FOR_S.get(p.root_alert),
                                 "match_labels": p.match_labels, "vm_duration_s": p.vm_duration})
        db.add(run)
        try:
            db.commit()  # unique index: hai admin cùng bấm thì chỉ một lần chạy được tạo (BR-06)
        except IntegrityError:
            db.rollback()
            raise ApiError(409, "fault_host_busy", f"VM {host} đang có lần chạy khác (BR-06)") from None
        try:
            started = self.ssh.call(host, p.command("start"))
        except FaultSSHError as e:
            run.status, run.error, run.valid = "failed", str(e), False
            if e.unreachable:  # không biết lỗi đã gây chưa: gỡ cho chắc (VM vẫn tự gỡ khi hết duration)
                try:
                    self.ssh.call(host, p.command("stop"))
                except FaultSSHError:
                    pass
            db.commit()
            if e.unreachable:
                raise ApiError(503, "vm_unreachable", f"Không gọi được VM {host}: {e}") from None
            code = "fault_host_busy" if e.code == 3 else "fault_vm_refused"
            raise ApiError(409, code, f"VM {host} từ chối: {e}") from None
        offset = run.vm_clock_offset_s or 0.0
        run.injected_at_vm = _dt(float(started["started_ts"]))
        run.injected_at = _dt(float(started["started_ts"]) - offset)
        run.status = "running"
        db.commit()
        return run

    # ------------------------------------------------------------------ dừng
    def _stop_vm(self, db: Session, run: m.FaultRun, reason: str) -> None:
        p = cat.plan(run.scenario, run.target_host, run.params, run.hold_s)
        res = self.ssh.call(run.target_host, p.command("stop"))
        vm_ts = res.get("ts")
        run.recovered_at = _dt(float(vm_ts) - (run.vm_clock_offset_s or 0.0)) if vm_ts else self.clock.now()
        run.status, run.stop_reason = "recovering", reason

    def stop(self, db: Session, run_id: int) -> m.FaultRun:
        with self._lock:
            run = db.get(m.FaultRun, run_id)
            if run is None:
                raise ApiError(404, "not_found", "Không tìm thấy lần chạy")
            if run.status != "running":
                raise ApiError(409, "fault_not_running", "Chỉ dừng được lần chạy đang ở trạng thái running")
            try:
                self._stop_vm(db, run, "admin_stopped")
            except FaultSSHError as e:
                raise ApiError(503, "vm_unreachable", f"Không gỡ được lỗi trên {run.target_host}: {e}") from None
            db.commit()
            return run

    # ------------------------------------------------------------------ khớp cảnh báo (hook của webhook)
    def on_firing(self, db: Session, ep: m.AlertEpisode) -> None:
        """Đợt firing mới: gắn vào các lần chạy đang hoạt động với vai trò root/expected/extra/unrelated."""
        runs = db.scalars(select(m.FaultRun).where(m.FaultRun.status.in_(("running", "recovering")))).all()
        for run in runs:
            if run.injected_at is None or ep.first_received_at < run.injected_at - timedelta(seconds=2):
                continue
            match = (run.config or {}).get("match_labels", {"host": run.target_host})
            mine = ep.alertname in run.expected_alerts and all(ep.labels.get(k) == v for k, v in match.items())
            if not mine:
                role = "unrelated"
            elif run.recovered_at is not None and ep.first_received_at > run.recovered_at:
                role = "extra"  # tới sau khi đã gỡ lỗi: nhiễu lúc khôi phục, không phải phát hiện
            else:
                role = "root" if ep.alertname == run.root_alert else "expected"
            if db.scalar(select(m.FaultRunAlert.id).where(m.FaultRunAlert.fault_run_id == run.id,
                                                          m.FaultRunAlert.alert_episode_id == ep.id)):
                continue
            db.add(m.FaultRunAlert(fault_run_id=run.id, alert_episode_id=ep.id, role=role,
                                   delay_s=round((ep.first_received_at - run.injected_at).total_seconds(), 3)))
            if role != "unrelated":
                self._tag_incident(db, run, ep, role)

    @staticmethod
    def _tag_incident(db: Session, run: m.FaultRun, ep: m.AlertEpisode, role: str) -> None:
        """BR-09: sự cố chứa cảnh báo do kịch bản lỗi gây ra là sự cố thử nghiệm. Đây là phát hiện đúng, không phải báo
        giả: chỉ gắn nhãn + một dòng thời gian, không đổi trạng thái hay is_false_positive."""
        inc = db.get(m.Incident, ep.incident_id) if ep.incident_id else None
        if inc is None:
            return
        if inc.fault_run_id is None:
            inc.fault_run_id = run.id  # giữ lần chạy đầu tiên nếu sự cố gom đợt của nhiều lần chạy
        db.flush()  # truy vấn thẳng (không qua inc.events) để thấy cả dòng vừa thêm trong cùng webhook
        seen = db.scalars(select(m.IncidentEvent.data).where(m.IncidentEvent.incident_id == inc.id,
                                                              m.IncidentEvent.type == "fault_run")).all()
        if any((d or {}).get("fault_run_id") == run.id for d in seen):
            return  # mỗi lần chạy một dòng, dù có nhiều đợt cảnh báo
        injected = run.injected_at.isoformat(timespec="seconds").replace("+00:00", "Z")
        case = reports.case_name(run)
        db.add(m.IncidentEvent(
            incident_id=inc.id, at=ep.first_received_at, user_id=None, type="fault_run",
            content=f"Do kịch bản lỗi #{run.id} ({case}) gây ra lúc {injected}",
            data={"fault_run_id": run.id, "case": case, "scenario": run.scenario, "target_host": run.target_host,
                  "injected_at": injected, "role": role, "episode_id": ep.id}))

    # ------------------------------------------------------------------ theo dõi định kỳ
    def _root(self, db: Session, run: m.FaultRun) -> tuple[m.FaultRunAlert, m.AlertEpisode] | None:
        row = db.execute(select(m.FaultRunAlert, m.AlertEpisode).join(m.AlertEpisode).where(
            m.FaultRunAlert.fault_run_id == run.id, m.FaultRunAlert.role == "root")
            .order_by(m.FaultRunAlert.delay_s)).first()
        return (row[0], row[1]) if row else None

    def _finish(self, db: Session, run: m.FaultRun) -> None:
        matched = db.scalars(select(m.FaultRunAlert).where(m.FaultRunAlert.fault_run_id == run.id)).all()
        detections = [a.delay_s for a in matched if a.role in ("root", "expected")]
        run.first_detection_s = min(detections) if detections else None
        root = self._root(db, run)
        run.root_detection_s = root[0].delay_s if root else None
        if root and root[1].resolved_received_at and run.recovered_at:
            run.root_resolved_s = round((root[1].resolved_received_at - run.recovered_at).total_seconds(), 3)
        if root:
            notify = (root[1].first_received_at - root[1].starts_at).total_seconds()
            if notify > NOTIFY_DELAY_LIMIT_S and run.valid:
                run.valid = False
                run.invalid_reasons = [*run.invalid_reasons,
                                       f"Cảnh báo gốc tới chậm {notify:.1f}s sau khi Prometheus bắn (luật đánh giá trễ, SC-04)"]
        run.status = "completed"

    def tick(self) -> None:
        with self._lock, self.Session() as db:
            now = self.clock.now()
            for run in db.scalars(select(m.FaultRun).where(m.FaultRun.status.in_(("running", "recovering")))).all():
                try:
                    if run.status == "running":
                        root = self._root(db, run)
                        elapsed = (now - run.injected_at).total_seconds()
                        if run.stop_on_alert and root and (now - root[1].first_received_at).total_seconds() >= run.linger_s:
                            self._stop_vm(db, run, "root_alert_received")
                        elif elapsed >= run.hold_s:
                            self._stop_vm(db, run, "hold_expired" if root else "not_detected")
                    elif run.status == "recovering":
                        root = self._root(db, run)
                        waited = (now - run.recovered_at).total_seconds()
                        if (root and root[1].resolved_received_at) or waited >= self.resolve_wait_s or root is None:
                            self._finish(db, run)
                    db.commit()
                except FaultSSHError as e:
                    db.rollback()
                    log.warning("Lần chạy #%s: không gỡ được lỗi (%s), thử lại sau; VM tự gỡ khi hết duration", run.id, e)

    # ------------------------------------------------------------------ khởi động lại backend (luồng 6)
    def recover_on_startup(self) -> None:
        with self._lock, self.Session() as db:
            for run in db.scalars(select(m.FaultRun).where(m.FaultRun.status.in_(m.FAULT_RUN_ACTIVE))).all():
                reason = "backend khởi động lại giữa chừng"
                try:
                    status = self.ssh.call(run.target_host, "status")
                except FaultSSHError as e:
                    log.warning("Lần chạy #%s: chưa kiểm được VM (%s), thử lại ở tick sau", run.id, e)
                    continue
                if status.get("active") and status.get("scenario") == run.scenario:
                    try:
                        self._stop_vm(db, run, "backend_restarted")
                    except FaultSSHError:
                        continue
                    run.status = "completed"
                else:
                    run.status = "cancelled"
                    run.recovered_at = run.recovered_at or self.clock.now()
                run.valid = False
                run.invalid_reasons = [*run.invalid_reasons, reason]
                db.commit()

    # ------------------------------------------------------------------ luồng nền
    def start_background(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._loop, name="fault-runner", daemon=True)
            self._thread.start()

    def stop_background(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _loop(self) -> None:
        while not self._stop.wait(self.tick_s):
            try:
                self.tick()
            except Exception:
                log.exception("fault-runner tick lỗi")
