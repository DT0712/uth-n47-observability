// Kịch bản lỗi (UC16–UC18, FR-P13–P15): form chạy (chỉ admin), lần chạy đang hoạt động, lịch sử, xuất báo cáo.
// Form chỉ hiện khi backend cho biết chế độ (trường `simulated`): backend cũ không có trường này -> không cho chạy,
// tránh vô tình gây lỗi thật trên VM. Chế độ lab thật (simulated=false) phải xác nhận thêm một bước.
import { Fragment, useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError } from "../api/client";
import * as ep from "../api/endpoints";
import { useAuth } from "../auth/AuthContext";
import { Card, Empty, ErrorBox } from "../components/Card";
import { Pagination } from "../components/Pagination";
import { ago, dateTime, num1, ROLE_LABEL, RUN_STATUS_LABEL, STOP_REASON_LABEL } from "../format";
import { usePolling } from "../hooks/usePolling";
import type { FaultRun, FaultRunDetail, FaultScenario } from "../types";

const ACTIVE = new Set(["pending", "running", "recovering"]);
const PAGE_SIZE = 20;

function paramText(params: Record<string, string | number>): string {
  const entries = Object.entries(params);
  return entries.length ? entries.map(([k, v]) => `${k}=${v}`).join(", ") : "—";
}

function caseName(r: FaultRun): string {
  return r.scenario === "service-stop" ? `dừng ${r.params.service}` : `${r.scenario} ${r.host}`;
}

function RunStatus({ r }: { r: FaultRun }) {
  const cls = r.status === "completed" ? "st-closed" : r.status === "failed" || r.status === "cancelled" ? "st-open"
    : "st-acknowledged";
  return (
    <span className="status-badges">
      <span className={`badge-sm ${cls}`}>{RUN_STATUS_LABEL[r.status] ?? r.status}</span>
      {!r.valid && <span className="badge-sm st-firing" title={r.invalid_reasons.join("; ")}>không hợp lệ</span>}
    </span>
  );
}

const sec = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${num1(v)} s`);

// ------------------------------------------------------------------ trang chính
export function FaultsPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [page, setPage] = useState(1);
  const scenarios = usePolling(() => ep.getScenarios(), [], 300000);
  const runs = usePolling(() => ep.listRuns({ page, page_size: PAGE_SIZE }), [page], 3000);
  const active = (runs.data?.items ?? []).filter((r) => ACTIVE.has(r.status));
  const simulated = scenarios.data?.[0]?.simulated;
  const [reportError, setReportError] = useState<string | null>(null);

  async function report(format: "csv" | "md") {
    setReportError(null);
    try {
      await ep.downloadReport(format, true);
    } catch (e) {
      setReportError(e instanceof Error ? e.message : "Không tải được báo cáo");
    }
  }

  return (
    <div className="page">
      <div className="toolbar">
        <div className="breadcrumb"><strong>Kịch bản lỗi</strong></div>
        <div className="spacer" />
        {simulated === true && <span className="badge-sm st-closed">Chế độ xem thử: giả lập, không đụng VM</span>}
        {simulated === false && <span className="badge-sm st-open">Lab thật: gây lỗi trên VM</span>}
      </div>
      <div className="grid-2">
        <div className="col">
          {isAdmin && <RunForm scenarios={scenarios.data} onStarted={runs.refresh} />}
          <ActiveRuns runs={active} isAdmin={isAdmin} onChange={runs.refresh} />
        </div>
        <div className="col">
          <Card title="Lịch sử lần chạy" sub={runs.data ? `${runs.data.total} lần` : "Đang tải…"}
                actions={isAdmin ? (
                  <div className="actions">
                    <button className="btn" onClick={() => void report("csv")}>Xuất CSV</button>
                    <button className="btn" onClick={() => void report("md")}>Xuất Markdown</button>
                  </div>
                ) : undefined}>
            {reportError && <ErrorBox>{reportError}</ErrorBox>}
            {runs.data && runs.data.items.length === 0 && <Empty>Chưa có lần chạy nào.</Empty>}
            {runs.data && runs.data.items.length > 0 && <RunTable runs={runs.data.items} />}
            {runs.data && <Pagination page={page} pageSize={PAGE_SIZE} total={runs.data.total} onPage={setPage} />}
          </Card>
        </div>
      </div>
    </div>
  );
}

function RunTable({ runs }: { runs: FaultRun[] }) {
  const navigate = useNavigate();
  return (
    <table className="table">
      <thead><tr><th>#</th><th>Trường hợp</th><th>Trạng thái</th><th className="num">Phát hiện</th><th>Lúc</th></tr></thead>
      <tbody>
        {runs.map((r) => (
          <tr key={r.id} className="link" tabIndex={0} onClick={() => navigate(`/kich-ban-loi/${r.id}`)}
              onKeyDown={(e) => e.key === "Enter" && navigate(`/kich-ban-loi/${r.id}`)}>
            <td>{r.id}</td>
            <td><b>{caseName(r)}</b><div className="muted">{r.root_alert}</div></td>
            <td><RunStatus r={r} /></td>
            <td className="num">{r.status === "completed" ? (r.root_detection_s === null ? "Không phát hiện" : sec(r.root_detection_s)) : "—"}</td>
            <td className="muted">{ago(r.requested_at)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// ------------------------------------------------------------------ form chạy (admin)
function RunForm({ scenarios, onStarted }: { scenarios: FaultScenario[] | null; onStarted: () => void }) {
  const [scenario, setScenario] = useState("cpu");
  const [host, setHost] = useState("web");
  const [params, setParams] = useState<Record<string, string>>({});
  const [hold, setHold] = useState(240);
  const [stopOnAlert, setStopOnAlert] = useState(true);
  const [linger, setLinger] = useState(30);
  const [requireClean, setRequireClean] = useState(false);
  const [note, setNote] = useState("");
  const [confirmReal, setConfirmReal] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [started, setStarted] = useState<number | null>(null);

  const sc = scenarios?.find((s) => s.scenario === scenario);
  const simulated = scenarios?.[0]?.simulated;
  const preflight = usePolling(() => ep.getPreflight(host), [host], 10000);

  useEffect(() => {  // đổi kịch bản: chọn VM hợp lệ đầu tiên và điền giá trị mặc định
    if (!sc) return;
    if (!sc.hosts.includes(host)) setHost(sc.hosts[0]);
    setParams(Object.fromEntries(sc.params.map((p) => [p.name, String(p.default ?? p.choices[0] ?? "")])));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scenario, sc?.scenario]);

  const hostsAllowed = useMemo(() => {
    if (!sc) return [];
    if (scenario === "service-stop") return params.service === "postgresql" ? ["db"] : params.service ? ["web"] : sc.hosts;
    return sc.hosts;
  }, [sc, scenario, params.service]);
  useEffect(() => {
    if (hostsAllowed.length && !hostsAllowed.includes(host)) setHost(hostsAllowed[0]);
  }, [hostsAllowed, host]);

  if (!scenarios) return <Card title="Chạy kịch bản lỗi"><Empty>Đang tải…</Empty></Card>;
  if (simulated === undefined) {
    return (
      <Card title="Chạy kịch bản lỗi">
        <ErrorBox>Backend chưa cho biết chế độ chạy (bản cũ). Khởi động lại backend theo hướng dẫn rồi tải lại trang.
          Form bị ẩn để tránh vô tình gây lỗi thật trên VM.</ErrorBox>
      </Card>
    );
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (simulated === false && !confirmReal) {
      setError("Lab thật: đánh dấu ô xác nhận trước khi chạy.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const body: ep.FaultRunCreate = {
        scenario, host, hold_s: hold, stop_on_alert: stopOnAlert, linger_s: linger, require_clean: requireClean,
        params: Object.fromEntries((sc?.params ?? []).map((p) => [p.name, p.type === "integer" ? Number(params[p.name]) : params[p.name]])),
        ...(note.trim() ? { note: note.trim() } : {}),
      };
      const run = await ep.startRun(body);
      setStarted(run.id);
      setConfirmReal(false);
      onStarted();
      preflight.refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không chạy được");
    } finally {
      setBusy(false);
    }
  }

  const pf = preflight.data;
  return (
    <section className="card" aria-label="Chạy kịch bản lỗi">
      <h2>Chạy kịch bản lỗi</h2>
      <p className="sub">Chỉ admin. Lỗi có thời hạn, VM tự gỡ khi hết hạn (ADR-0007). Mỗi VM một lần chạy (BR-06).</p>
      <form onSubmit={submit} className="run-form">
        <div className="form-row">
          <div className="field">
            <label htmlFor="f-scenario">Kịch bản</label>
            <select id="f-scenario" className="range-select" value={scenario} onChange={(e) => setScenario(e.target.value)}>
              {scenarios.map((s) => <option key={s.scenario} value={s.scenario}>{s.title}</option>)}
            </select>
          </div>
          {sc?.params.map((p) => (
            <div className="field" key={p.name}>
              <label htmlFor={`f-${p.name}`}>{p.name}{p.type === "integer" ? ` (${p.min}–${p.max})` : ""}</label>
              {p.type === "enum" ? (
                <select id={`f-${p.name}`} className="range-select" value={params[p.name] ?? ""}
                        onChange={(e) => setParams({ ...params, [p.name]: e.target.value })}>
                  {p.choices.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              ) : (
                <input id={`f-${p.name}`} type="number" min={p.min ?? undefined} max={p.max ?? undefined} value={params[p.name] ?? ""}
                       onChange={(e) => setParams({ ...params, [p.name]: e.target.value })} />
              )}
            </div>
          ))}
          <div className="field">
            <label htmlFor="f-host">Máy</label>
            <select id="f-host" className="range-select" value={host} onChange={(e) => setHost(e.target.value)}>
              {hostsAllowed.map((h) => <option key={h} value={h}>{h}</option>)}
            </select>
          </div>
        </div>
        <div className="form-row">
          <div className="field">
            <label htmlFor="f-hold">Giữ lỗi tối đa (giây, 30–{sc?.max_hold_s ?? 840})</label>
            <input id="f-hold" type="number" min={30} max={sc?.max_hold_s ?? 840} value={hold} onChange={(e) => setHold(Number(e.target.value))} />
          </div>
          <div className="field">
            <label htmlFor="f-linger">Giữ thêm sau cảnh báo gốc (giây)</label>
            <input id="f-linger" type="number" min={0} max={120} value={linger} onChange={(e) => setLinger(Number(e.target.value))} />
          </div>
        </div>
        <div className="actions" style={{ marginBottom: 10 }}>
          <label className="check"><input type="checkbox" checked={stopOnAlert} onChange={(e) => setStopOnAlert(e.target.checked)} /> Gỡ sớm khi đã nhận cảnh báo gốc</label>
          <label className="check"><input type="checkbox" checked={requireClean} onChange={(e) => setRequireClean(e.target.checked)} /> Chỉ chạy khi điều kiện đo đạt</label>
        </div>
        <div className="field">
          <label htmlFor="f-note">Ghi chú (tùy chọn)</label>
          <input id="f-note" value={note} maxLength={500} onChange={(e) => setNote(e.target.value)} />
        </div>
        <p className="muted" style={{ fontSize: 13, margin: "0 0 10px" }}>
          Cảnh báo gốc mong đợi: <b>{scenario === "service-stop" ? ({ nginx: "NginxDown", "demo-app": "ServiceDown", postgresql: "PostgresDown" } as Record<string, string>)[params.service] ?? "—" : sc?.root_alert}</b>
        </p>

        <div className={`notice ${pf?.clean ? "info" : "warn"}`} aria-label="Điều kiện đo">
          {!pf ? "Đang kiểm điều kiện đo…" : pf.clean ? `Điều kiện đo trên ${host}: đạt (trễ đánh giá luật ${num1(pf.eval_lag_s)} s).` : (
            <>Điều kiện đo trên {host} chưa đạt, lần chạy sẽ bị đánh dấu không hợp lệ:
              <ul style={{ margin: "4px 0 0", paddingLeft: 18 }}>{pf.reasons.map((r) => <li key={r}>{r}</li>)}</ul></>
          )}
        </div>
        {simulated === false && (
          <label className="check notice warn" style={{ display: "flex" }}>
            <input type="checkbox" checked={confirmReal} onChange={(e) => setConfirmReal(e.target.checked)} />
            Tôi hiểu lệnh này gây lỗi THẬT trên VM {host} (không chạy khi đang đo baseline).
          </label>
        )}
        {error && <ErrorBox>{error}</ErrorBox>}
        {started && !error && <p className="notice info">Đã bắt đầu lần chạy <Link to={`/kich-ban-loi/${started}`}>#{started}</Link>.</p>}
        <div className="actions" style={{ marginTop: 12 }}>
          <button className="btn btn-dark" type="submit" disabled={busy || !!pf?.active_run_id}>
            {busy ? "Đang gây lỗi…" : pf?.active_run_id ? `Máy ${host} đang bận (#${pf.active_run_id})` : "Chạy"}
          </button>
        </div>
      </form>
    </section>
  );
}

// ------------------------------------------------------------------ lần chạy đang hoạt động
function ActiveRuns({ runs, isAdmin, onChange }: { runs: FaultRun[]; isAdmin: boolean; onChange: () => void }) {
  return (
    <Card title="Đang chạy" sub="Tự làm mới mỗi 3 giây">
      {runs.length === 0 ? <Empty>Không có lần chạy nào đang hoạt động.</Empty>
        : runs.map((r) => <ActiveRun key={r.id} id={r.id} isAdmin={isAdmin} onChange={onChange} />)}
    </Card>
  );
}

function ActiveRun({ id, isAdmin, onChange }: { id: number; isAdmin: boolean; onChange: () => void }) {
  const run = usePolling(() => ep.getRun(id), [id], 3000);
  const [now, setNow] = useState(Date.now());
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, []);
  const r = run.data;
  if (!r) return null;
  const elapsed = r.injected_at ? Math.max(0, (now - new Date(r.injected_at).getTime()) / 1000) : null;
  async function stop() {
    setError(null);
    try {
      await ep.stopRun(id);
      run.refresh();
      onChange();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Không dừng được");
    }
  }
  return (
    <div className="active-run" aria-label={`Lần chạy #${r.id}`}>
      <div className="incident-head">
        <b><Link to={`/kich-ban-loi/${r.id}`}>#{r.id} {caseName(r)}</Link></b>
        <RunStatus r={r} />
        <span className="timer">{elapsed === null ? "—" : `${Math.floor(elapsed)} s`}</span>
        {isAdmin && r.status === "running" && <button className="btn" onClick={() => void stop()}>Dừng</button>}
      </div>
      <div className="muted" style={{ fontSize: 13 }}>Chờ {r.root_alert} · giữ tối đa {r.hold_s} s</div>
      {r.alerts.length > 0 && (
        <ul className="alert-list">
          {r.alerts.map((a) => <li key={a.alert_episode_id}><span className={`role role-${a.role}`}>{ROLE_LABEL[a.role]}</span> {a.alertname} sau {sec(a.delay_s)}</li>)}
        </ul>
      )}
      {error && <ErrorBox>{error}</ErrorBox>}
    </div>
  );
}

// ------------------------------------------------------------------ chi tiết lần chạy
export function FaultRunPage() {
  const id = Number(useParams().id);
  const run = usePolling(() => ep.getRun(id), [id], 3000);
  if (run.error && !run.data) return <div className="page"><ErrorBox>Không tìm thấy lần chạy.</ErrorBox></div>;
  const r: FaultRunDetail | null = run.data;
  return (
    <div className="page">
      <div className="toolbar">
        <div className="breadcrumb"><Link to="/kich-ban-loi">Kịch bản lỗi</Link> › <strong>{r ? `#${r.id} ${caseName(r)}` : "…"}</strong></div>
      </div>
      {!r ? <Empty>Đang tải…</Empty> : (
        <div className="grid-2">
          <div className="col">
            <section className="card" aria-label="Kết quả">
              <div className="incident-head"><h1>#{r.id} {caseName(r)}</h1><RunStatus r={r} /></div>
              <div className="kpi-grid" style={{ marginTop: 14 }}>
                <div className="kpi peach"><div className="label" style={{ marginTop: 0 }}>Phát hiện (cảnh báo gốc)</div>
                  <div className="value">{r.status === "completed" && r.root_detection_s === null ? "—" : sec(r.root_detection_s)}</div></div>
                <div className="kpi lavender"><div className="label" style={{ marginTop: 0 }}>Cảnh báo đầu tiên</div>
                  <div className="value">{sec(r.first_detection_s)}</div></div>
                <div className="kpi mint"><div className="label" style={{ marginTop: 0 }}>Resolved sau khi gỡ</div>
                  <div className="value">{sec(r.root_resolved_s)}</div></div>
              </div>
              {!r.valid && <p className="notice warn">Không hợp lệ: {r.invalid_reasons.join("; ")}</p>}
              {r.error && <ErrorBox>{r.error}</ErrorBox>}
              <dl className="kv">
                <dt>Máy</dt><dd>{r.host}</dd>
                <dt>Tham số</dt><dd>{paramText(r.params)}</dd>
                <dt>Cảnh báo mong đợi</dt><dd>{r.expected_alerts.join(", ")}</dd>
                <dt>Người chạy</dt><dd>{r.requested_by ?? "—"}, {dateTime(r.requested_at)}</dd>
                <dt>Gây lỗi (T0)</dt><dd>{dateTime(r.injected_at)}</dd>
                <dt>Gỡ lỗi</dt><dd>{dateTime(r.recovered_at)} {r.stop_reason ? `(${STOP_REASON_LABEL[r.stop_reason] ?? r.stop_reason})` : ""}</dd>
                <dt>Lệch đồng hồ VM</dt><dd>{r.vm_clock_offset_s === null ? "—" : `${r.vm_clock_offset_s} s`}</dd>
                <dt>Trễ đánh giá luật</dt><dd>{r.eval_lag_s === null ? "—" : `${r.eval_lag_s} s`}</dd>
                {r.note && <><dt>Ghi chú</dt><dd>{r.note}</dd></>}
              </dl>
            </section>
          </div>
          <div className="col">
            <Card title="Cảnh báo đã khớp" sub="Thời gian = lúc portal nhận cảnh báo − lúc gây lỗi">
              {r.alerts.length === 0 ? <Empty>Chưa có cảnh báo nào.</Empty> : (
                <table className="table">
                  <thead><tr><th>Vai trò</th><th>Cảnh báo</th><th>Instance</th><th className="num">Sau</th></tr></thead>
                  <tbody>
                    {r.alerts.map((a) => (
                      <tr key={a.alert_episode_id}><td><span className={`role role-${a.role}`}>{ROLE_LABEL[a.role]}</span></td>
                        <td>{a.alertname}</td><td className="muted">{a.instance}</td><td className="num">{sec(a.delay_s)}</td></tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Card>
            <Card title="Cấu hình lúc chạy (BR-07)">
              <dl className="kv">
                {Object.entries(r.config ?? {}).filter(([k]) => k !== "match_labels").map(([k, v]) => (
                  <Fragment key={k}><dt>{k}</dt><dd>{String(v)}</dd></Fragment>
                ))}
              </dl>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
