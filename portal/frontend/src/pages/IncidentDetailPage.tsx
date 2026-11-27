// Chi tiết sự cố (UC06–UC10, FR-P10–P11): trái là thông tin + thao tác + các đợt + dòng thời gian; phải là runbook.
// Quy tắc nghiệp vụ được backend kiểm (BR-01, BR-04); giao diện chỉ bật/tắt nút theo `status` và `can_close`
// và hiện nguyên thông báo lỗi của backend nếu thao tác bị từ chối.
import { ExternalLink } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "../api/client";
import * as ep from "../api/endpoints";
import { IncidentStatusBadge, SeverityBadge, TestBadge } from "../components/Badges";
import { Card, Empty, ErrorBox } from "../components/Card";
import { SkeletonTable, SkeletonText } from "../components/Skeleton";
import { LoadFailed } from "../components/StatusPanel";
import { TextDialog } from "../components/Dialog";
import { useToast } from "../components/Toast";
import { RunbookView } from "../components/RunbookView";
import { ago, dateTime, EVENT_LABEL, time } from "../format";
import { usePolling } from "../hooks/usePolling";
import type { IncidentDetail, IncidentEvent } from "../types";
import { useTitle } from "../hooks/useTitle";

type DialogKind = "false_positive" | "close" | null;

export function IncidentDetailPage() {
  const id = Number(useParams().id);
  const detail = usePolling(() => ep.getIncident(id), [id]);
  useTitle(detail.data ? `Sự cố #${id} ${detail.data.alertname}` : `Sự cố #${id}`);
  const alertname = detail.data?.alertname;
  const runbook = usePolling(() => (alertname ? ep.getRunbook(alertname) : Promise.resolve(null)), [alertname], 300000);
  const [dialog, setDialog] = useState<DialogKind>(null);
  const [error, setError] = useState<string | null>(null);
  const toast = useToast();

  // Lỗi hiện tại chỗ (thẻ thông tin hoặc hộp thoại) để người dùng đọc kỹ; thành công báo bằng toast
  async function act(fn: () => Promise<unknown>, ok: string) {
    setError(null);
    try {
      await fn();
      toast.success(ok);
      detail.refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không thực hiện được");
      throw err;
    }
  }

  if (detail.error && !detail.data) {
    return (
      <div className="page">
        <Breadcrumb />
        <LoadFailed error={detail.error} what="sự cố" back="/su-co" backLabel="Về danh sách sự cố" />
      </div>
    );
  }
  const inc = detail.data;
  if (!inc) {
    return (
      <div className="page">
        <Breadcrumb />
        <div className="grid-2">
          <div className="col">
            <section className="card"><SkeletonText lines={6} label="Đang tải sự cố" /></section>
            <section className="card"><SkeletonTable rows={3} cols={4} /></section>
          </div>
          <div className="col"><section className="card"><SkeletonText lines={10} /></section></div>
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <Breadcrumb name={`#${inc.id} ${inc.alertname}`} />
      <div className="grid-2">
        <div className="col">
          <InfoCard inc={inc} error={error} onAck={() => act(() => ep.acknowledge(inc.id), `Đã xác nhận sự cố #${inc.id}`).catch(() => null)}
                    onFalsePositive={() => setDialog("false_positive")} onClose={() => setDialog("close")} />
          <EpisodesCard inc={inc} />
          <TimelineCard inc={inc} onNote={(text) => act(() => ep.addNote(inc.id, text), "Đã thêm ghi chú")} />
        </div>
        <div className="col">
          <Card title="Runbook" sub={inc.runbook ? inc.runbook.title : undefined}
                actions={<Link className="btn" to={`/runbook?alert=${inc.alertname}`}>Mở trang runbook</Link>}>
            {!inc.runbook && <Empty>Chưa có runbook cho {inc.alertname}.</Empty>}
            {inc.runbook && !runbook.data && <SkeletonText lines={8} label="Đang tải runbook" />}
            {runbook.data && <RunbookView runbook={runbook.data} />}
          </Card>
        </div>
      </div>
      {dialog === "false_positive" && (
        <TextDialog title="Đánh dấu báo giả" label="Lý do (bắt buộc)" minLength={5} submitLabel="Đánh dấu báo giả"
                    hint="Ghi rõ vì sao không có vấn đề thật, vd. tải đột biến ngắn hợp lệ, ngưỡng còn tạm thời… Dùng để rà soát ngưỡng."
                    onSubmit={(text) => act(() => ep.markFalsePositive(inc.id, text), `Đã đánh dấu sự cố #${inc.id} là báo giả`)} onClose={() => setDialog(null)} />
      )}
      {dialog === "close" && (
        <TextDialog title="Đóng sự cố" label="Kết luận" minLength={5} submitLabel="Đóng sự cố"
                    hint="Nguyên nhân, cách xử lý, có cần chỉnh ngưỡng/runbook không. Sự cố đã đóng không mở lại được."
                    onSubmit={(text) => act(() => ep.closeIncident(inc.id, text), `Đã đóng sự cố #${inc.id}`)} onClose={() => setDialog(null)} />
      )}
    </div>
  );
}

function Breadcrumb({ name }: { name?: string }) {
  return (
    <div className="toolbar">
      <div className="breadcrumb"><Link to="/su-co">Sự cố</Link> › <strong>{name ?? "Chi tiết"}</strong></div>
    </div>
  );
}

function InfoCard({ inc, error, onAck, onFalsePositive, onClose }: {
  inc: IncidentDetail; error: string | null; onAck: () => void; onFalsePositive: () => void; onClose: () => void;
}) {
  const closed = inc.status === "closed";
  return (
    <section className="card" aria-label="Thông tin sự cố">
      <div className="incident-head">
        <SeverityBadge severity={inc.severity} />
        <h1>{inc.alertname}</h1>
        <IncidentStatusBadge status={inc.status} firing={inc.firing} />
        {inc.is_false_positive && <span className="badge-sm st-firing">báo giả</span>}
        <TestBadge runId={inc.fault_run_id} />
      </div>
      {inc.summary && <p className="muted" style={{ margin: "8px 0 0" }}>{inc.summary}</p>}
      <dl className="kv">
        <dt>Máy / instance</dt><dd>{inc.host ?? "—"} · {inc.instance}{inc.service ? ` · ${inc.service}` : ""}</dd>
        {inc.fault_run_id !== null && (
          <><dt>Nguồn</dt><dd><Link to={`/kich-ban-loi/${inc.fault_run_id}`}>Kịch bản lỗi #{inc.fault_run_id}</Link>
            {" "}<span className="muted">(thử nghiệm: phát hiện đúng, không phải báo giả)</span></dd></>
        )}
        <dt>Mở lúc</dt><dd>{dateTime(inc.opened_at)} ({ago(inc.opened_at)})</dd>
        <dt>Xác nhận</dt><dd>{inc.acknowledged_at ? `${inc.acknowledged_by ?? "—"}, ${dateTime(inc.acknowledged_at)}` : "Chưa"}</dd>
        {inc.is_false_positive && <><dt>Lý do báo giả</dt><dd>{inc.false_positive_reason}</dd></>}
        {closed && <><dt>Đóng</dt><dd>{inc.closed_by ?? "—"}, {dateTime(inc.closed_at)}</dd>
                     <dt>Kết luận</dt><dd>{inc.conclusion}</dd></>}
      </dl>
      {!closed && (
        <div className="actions">
          <button className="btn btn-dark" onClick={onAck} disabled={inc.status !== "open"}>Xác nhận</button>
          <button className="btn" onClick={onFalsePositive} disabled={inc.is_false_positive}>Đánh dấu báo giả</button>
          <button className="btn" onClick={onClose} disabled={!inc.can_close}>Đóng sự cố</button>
          {inc.grafana_url && (
            <a className="btn" href={inc.grafana_url} target="_blank" rel="noreferrer">
              Mở Grafana <ExternalLink size={13} strokeWidth={1.5} style={{ verticalAlign: -2 }} />
            </a>
          )}
        </div>
      )}
      {!closed && !inc.can_close && (
        <p className="notice warn">Cảnh báo vẫn đang firing nên chưa đóng được (BR-01). Chờ cảnh báo hết, hoặc đánh dấu báo giả nếu không có vấn đề thật.</p>
      )}
      {error && <ErrorBox>{error}</ErrorBox>}
    </section>
  );
}

function EpisodesCard({ inc }: { inc: IncidentDetail }) {
  return (
    <Card title="Các đợt cảnh báo" sub="Mỗi lần cảnh báo bắn → hết là một đợt; cùng cảnh báo bắn lại khi sự cố chưa đóng được gộp vào đây">
      <table className="table">
        <thead><tr><th>#</th><th>Trạng thái</th><th>Prometheus bắn</th><th>Portal nhận</th><th>Hết lúc</th></tr></thead>
        <tbody>
          {inc.episodes.map((e, i) => (
            <tr key={e.id}>
              <td>{i + 1}</td>
              <td><span className={`badge-sm ${e.status === "firing" ? "st-firing" : "st-closed"}`}>{e.status === "firing" ? "firing" : "resolved"}</span></td>
              <td>{time(e.starts_at)}</td>
              <td>{time(e.first_received_at)}</td>
              <td>{e.resolved_received_at ? time(e.resolved_received_at) : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

/** "Do kịch bản lỗi #N gây ra lúc …" với giờ theo trình duyệt (backend lưu nội dung kèm giờ UTC làm dự phòng). */
function FaultRunLine({ e }: { e: IncidentEvent }) {
  const d = e.data!;
  return (
    <div className="content">
      Do <Link to={`/kich-ban-loi/${d.fault_run_id}`}>kịch bản lỗi #{d.fault_run_id}</Link> ({d.case})
      {" "}gây ra lúc {dateTime(d.injected_at)}
    </div>
  );
}

function TimelineCard({ inc, onNote }: { inc: IncidentDetail; onNote: (text: string) => Promise<void> }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await onNote(text.trim());
      setText("");
    } catch {
      /* lỗi đã hiện ở thẻ thông tin */
    } finally {
      setBusy(false);
    }
  }
  return (
    <Card title="Dòng thời gian" sub="Mọi thao tác đều ghi người thực hiện và thời điểm">
      <ol className="timeline">
        {inc.events.map((e) => (
          <li key={e.id} className={`ev-${e.type}`}>
            <div><b>{EVENT_LABEL[e.type] ?? e.type}</b> <span className="when">· {e.user ?? "hệ thống"} · {dateTime(e.at)}</span></div>
            {e.type === "fault_run" && e.data ? <FaultRunLine e={e} />
              : e.content && <div className="content">{e.content}</div>}
          </li>
        ))}
      </ol>
      {inc.status !== "closed" && (
        <form className="note-form" onSubmit={submit} aria-label="Thêm ghi chú">
          <textarea aria-label="Ghi chú" rows={3} placeholder="Ghi lại bước kiểm tra, kết quả, lệnh đã chạy…" value={text}
                    onChange={(e) => setText(e.target.value)} maxLength={5000} />
          <div className="actions">
            <button className="btn btn-dark" type="submit" disabled={busy || !text.trim()}>{busy ? "Đang lưu…" : "Thêm ghi chú"}</button>
          </div>
        </form>
      )}
    </Card>
  );
}
