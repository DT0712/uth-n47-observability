// Trang runbook (UC10): danh sách bên trái, nội dung Markdown bên phải. Chọn runbook nằm trên URL (?alert=NginxDown).
import { Link, useSearchParams } from "react-router-dom";
import * as ep from "../api/endpoints";
import { SeverityBadge } from "../components/Badges";
import { Card, Empty, ErrorBox } from "../components/Card";
import { RunbookView } from "../components/RunbookView";
import { usePolling } from "../hooks/usePolling";

export function RunbookPage() {
  const [params] = useSearchParams();
  const list = usePolling(() => ep.listRunbooks(), [], 300000);
  const selected = params.get("alert") ?? list.data?.[0]?.alertname;
  const runbook = usePolling(() => (selected ? ep.getRunbook(selected) : Promise.resolve(null)), [selected], 300000);

  return (
    <div className="page">
      <div className="toolbar"><div className="breadcrumb">Runbook{selected ? " › " : ""}<strong>{selected ?? ""}</strong></div></div>
      <div className="runbook-layout">
        <Card title="Loại cảnh báo" sub={list.data ? `${list.data.length} runbook` : "Đang tải…"}>
          {list.error && <ErrorBox>{list.error.message}</ErrorBox>}
          <ul className="runbook-list">
            {(list.data ?? []).map((r) => (
              <li key={r.alertname}>
                <Link to={`/runbook?alert=${r.alertname}`} className={r.alertname === selected ? "active" : undefined}>
                  {r.severity && <SeverityBadge severity={r.severity} />} {r.alertname}
                </Link>
              </li>
            ))}
          </ul>
        </Card>
        <Card title={runbook.data?.title ?? "Runbook"}>
          {runbook.error && <ErrorBox>{runbook.error.message}</ErrorBox>}
          {!runbook.data && !runbook.error && <Empty>{selected ? "Đang tải…" : "Chưa có runbook nào."}</Empty>}
          {runbook.data && <RunbookView runbook={runbook.data} />}
        </Card>
      </div>
    </div>
  );
}
