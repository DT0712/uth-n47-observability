// Danh sách sự cố (UC05, FR-P09): bộ lọc trên URL, một thẻ bảng rộng, phân trang (giao-dien.md mục 5).
import { useMemo } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import * as ep from "../api/endpoints";
import { IncidentStatusBadge, SeverityBadge, TestBadge } from "../components/Badges";
import { Card, Empty, ErrorBox } from "../components/Card";
import { SkeletonTable } from "../components/Skeleton";
import { Pagination } from "../components/Pagination";
import { ago, time } from "../format";
import { usePolling } from "../hooks/usePolling";
import { useTitle } from "../hooks/useTitle";

const PAGE_SIZE = 25;
const STATUS_OPTIONS = [
  { value: "open,acknowledged", label: "Chưa đóng" },
  { value: "open", label: "Mở" },
  { value: "acknowledged", label: "Đã xác nhận" },
  { value: "closed", label: "Đã đóng" },
  { value: "all", label: "Tất cả" },
];

export function IncidentListPage() {
  useTitle("Sự cố");
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const get = (k: string) => params.get(k) ?? undefined;
  const status = get("status") ?? "open,acknowledged";
  const page = Number(get("page") ?? 1);
  const query = useMemo<ep.IncidentQuery>(() => ({
    status: status === "all" ? undefined : status, severity: get("severity"), host: get("host"), alertname: get("alertname"),
    firing: get("firing"), false_positive: get("false_positive"), test: get("test"), sort: get("sort") ?? "-opened_at", page, page_size: PAGE_SIZE,
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }), [params.toString()]);

  const list = usePolling(() => ep.listIncidents(query), [JSON.stringify(query)]);
  const hosts = usePolling(() => ep.listHosts(), [], 300000);
  const runbooks = usePolling(() => ep.listRunbooks(), [], 300000);

  const update = (next: Record<string, string | undefined>) => {
    const p = new URLSearchParams(params);
    for (const [k, v] of Object.entries(next)) (v ? p.set(k, v) : p.delete(k));
    if (!("page" in next)) p.delete("page"); // đổi bộ lọc thì về trang 1
    setParams(p, { replace: true });
  };
  const open = (id: number) => navigate(`/su-co/${id}`);

  return (
    <div className="page">
      <div className="toolbar">
        <div className="breadcrumb"><strong>Sự cố</strong></div>
        <div className="spacer" />
        <select className="range-select" aria-label="Sắp xếp" value={get("sort") ?? "-opened_at"}
                onChange={(e) => update({ sort: e.target.value })}>
          <option value="-opened_at">Mới nhất trước</option>
          <option value="opened_at">Cũ nhất trước</option>
          <option value="severity">Mức độ cao trước</option>
        </select>
      </div>
      <div className="chips" aria-label="Bộ lọc">
        <select className="filter-select" aria-label="Trạng thái xử lý" value={status} onChange={(e) => update({ status: e.target.value })}>
          {STATUS_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
        <select className="filter-select" aria-label="Mức độ" value={get("severity") ?? ""} onChange={(e) => update({ severity: e.target.value })}>
          <option value="">Mọi mức độ</option>
          <option value="critical">Nghiêm trọng</option>
          <option value="warning">Cao</option>
          <option value="info">Thấp</option>
        </select>
        <select className="filter-select" aria-label="Máy" value={get("host") ?? ""} onChange={(e) => update({ host: e.target.value })}>
          <option value="">Mọi máy</option>
          {(hosts.data ?? []).map((h) => <option key={h.id} value={h.name}>{h.name}</option>)}
        </select>
        <select className="filter-select" aria-label="Cảnh báo" value={get("alertname") ?? ""} onChange={(e) => update({ alertname: e.target.value })}>
          <option value="">Mọi cảnh báo</option>
          {(runbooks.data ?? []).map((r) => <option key={r.alertname} value={r.alertname}>{r.alertname}</option>)}
        </select>
        <label className="check">
          <input type="checkbox" checked={get("firing") === "true"} onChange={(e) => update({ firing: e.target.checked ? "true" : undefined })} />
          Đang firing
        </label>
        <label className="check">
          <input type="checkbox" checked={get("false_positive") === "true"}
                 onChange={(e) => update({ false_positive: e.target.checked ? "true" : undefined })} />
          Báo giả
        </label>
        <label className="check" title="Sự cố do kịch bản lỗi gây ra (phát hiện đúng, không phải báo giả)">
          <input type="checkbox" checked={get("test") === "false"}
                 onChange={(e) => update({ test: e.target.checked ? "false" : undefined })} />
          Ẩn sự cố thử nghiệm
        </label>
      </div>

      <Card title="Danh sách sự cố" sub={list.data ? `${list.data.total} sự cố` : " "}>
        {list.error && <ErrorBox>Không tải được danh sách: {list.error.message}</ErrorBox>}
        {!list.data && !list.error && <SkeletonTable rows={6} cols={7} label="Đang tải danh sách sự cố" />}
        {list.data && list.data.items.length === 0 && <Empty>Không có sự cố nào khớp bộ lọc.</Empty>}
        {list.data && list.data.items.length > 0 && (
          <table className="table">
            <thead>
              <tr><th>Mức độ</th><th>Cảnh báo</th><th>Máy / instance</th><th>Trạng thái</th><th className="num">Số đợt</th>
                  <th>Tóm tắt</th><th>Mở lúc</th></tr>
            </thead>
            <tbody>
              {list.data.items.map((i) => (
                <tr key={i.id} className="link" tabIndex={0} onClick={() => open(i.id)} onKeyDown={(e) => e.key === "Enter" && open(i.id)}>
                  <td><SeverityBadge severity={i.severity} /></td>
                  <td><b>{i.alertname}</b>{i.is_false_positive && <span className="badge-sm st-firing" style={{ marginLeft: 6 }}>báo giả</span>}
                    <TestBadge runId={i.fault_run_id} inline /></td>
                  <td>{i.host ?? "—"}<div className="muted">{i.instance}</div></td>
                  <td><IncidentStatusBadge status={i.status} firing={i.firing} /></td>
                  <td className="num">{i.episode_count}</td>
                  <td className="muted">{i.summary ?? "—"}</td>
                  <td className="nowrap" title={time(i.opened_at)}>{ago(i.opened_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {list.data && <Pagination page={page} pageSize={PAGE_SIZE} total={list.data.total} onPage={(p) => update({ page: String(p) })} />}
      </Card>
    </div>
  );
}
