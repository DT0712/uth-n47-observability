// Ngưỡng hiện hành (UC11, FR-P12): đọc lab:threshold:* từ Prometheus. Portal chỉ hiển thị; sửa ngưỡng trong
// monitor/prometheus/rules/thresholds.yml (ADR-0004). Kèm tỉ lệ báo giả theo cảnh báo để rà soát ngưỡng; sự cố thử
// nghiệm (do kịch bản lỗi gây ra, BR-09) không được tính.
import { useState } from "react";
import { Link } from "react-router-dom";
import * as ep from "../api/endpoints";
import { Card, Empty, ErrorBox } from "../components/Card";
import { SkeletonText } from "../components/Skeleton";
import { pct } from "../format";
import { usePolling } from "../hooks/usePolling";

const LABEL: Record<string, [string, string]> = {
  host_cpu_usage_percent: ["CPU của máy", "%"],
  host_memory_usage_percent: ["RAM của máy", "%"],
  filesystem_usage_percent: ["Dung lượng đĩa đã dùng", "%"],
  endpoint_probe_duration_seconds: ["Thời gian probe HTTP", "s"],
  service_latency_p95_seconds: ["Độ trễ p95 của demo app", "s"],
  service_error_ratio: ["Tỉ lệ lỗi 5xx", "tỉ lệ 0–1"],
  service_min_request_rate_rps: ["Lưu lượng tối thiểu để xét tỉ lệ lỗi", "req/s"],
  postgres_connections_usage_percent: ["% kết nối PostgreSQL", "%"],
};

export function ThresholdsPage() {
  const rows = usePolling(() => ep.getThresholds(), [], 60000);
  const provisional = rows.data?.filter((r) => r.status === "provisional").length ?? 0;
  return (
    <div className="page">
      <div className="toolbar"><div className="breadcrumb"><strong>Ngưỡng</strong></div></div>
      <Card title="Ngưỡng cảnh báo hiện hành"
            sub="Đọc từ Prometheus (lab:threshold:*). Sửa trong monitor/prometheus/rules/thresholds.yml rồi chạy tools/reload.py.">
        {rows.error && <ErrorBox>Không đọc được Prometheus nên chưa có ngưỡng để hiển thị.</ErrorBox>}
        {rows.data && rows.data.length === 0 && <Empty>Không có ngưỡng nào.</Empty>}
        {rows.data && rows.data.length > 0 && (
          <>
            {provisional > 0 && (
              <p className="notice warn">{provisional}/{rows.data.length} ngưỡng còn tạm thời (provisional): chưa chốt theo baseline.</p>
            )}
            <table className="table" style={{ marginTop: 10 }}>
              <thead><tr><th>Chỉ số</th><th>Tên</th><th className="num">Giá trị</th><th>Trạng thái</th><th>Cơ sở</th></tr></thead>
              <tbody>
                {rows.data.map((r) => (
                  <tr key={r.name}>
                    <td>{LABEL[r.name]?.[0] ?? r.name}</td>
                    <td><code>{r.name}</code></td>
                    <td className="num">{r.value ?? "—"} {LABEL[r.name]?.[1] ?? ""}</td>
                    <td><span className={`badge-sm ${r.status === "baselined" ? "st-closed" : "st-acknowledged"}`}>
                      {r.status === "baselined" ? "Đã chốt" : "Tạm thời"}</span></td>
                    <td className="muted">{r.basis || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </Card>
      <FalsePositiveCard />
    </div>
  );
}

const RANGES = [
  { value: "7", label: "7 ngày qua" },
  { value: "30", label: "30 ngày qua" },
  { value: "all", label: "Toàn bộ" },
];

const fromFor = (range: string) =>
  range === "all" ? undefined : new Date(Date.now() - Number(range) * 86400000).toISOString();
const rate = (r: number | null) => (r === null ? "—" : pct(r * 100));

function FalsePositiveCard() {
  const [range, setRange] = useState("30");
  const report = usePolling(() => ep.getFalsePositiveReport(fromFor(range)), [range], 60000);
  const r = report.data;
  return (
    <Card title="Tỉ lệ báo giả" sub="Sự cố đánh dấu báo giả / sự cố thật, theo thời điểm mở. Cảnh báo nhiều báo giả là ứng viên chỉnh ngưỡng hoặc for."
          actions={
            <select className="range-select" aria-label="Khoảng thời gian" value={range} onChange={(e) => setRange(e.target.value)}>
              {RANGES.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          }>
      {report.error && <ErrorBox>Không tải được báo cáo: {report.error.message}</ErrorBox>}
      {!r && !report.error && <SkeletonText lines={4} label="Đang tải báo cáo" />}
      {r && (
        <>
          <p style={{ margin: "4px 0 0" }}>
            <b style={{ fontSize: 20 }}>{rate(r.rate)}</b>{" "}
            <span className="muted">({r.false_positive}/{r.total} sự cố thật)</span>
          </p>
          <p className="muted" style={{ margin: "4px 0 0" }}>
            Không tính {r.test_excluded} sự cố thử nghiệm do kịch bản lỗi gây ra (phát hiện đúng).{" "}
            {r.test_excluded > 0 && <Link to="/su-co?status=all&test=true">Xem</Link>}
          </p>
          {r.by_alertname.length === 0 ? <Empty>Chưa có sự cố thật trong khoảng này.</Empty> : (
            <table className="table" style={{ marginTop: 10 }}>
              <thead><tr><th>Cảnh báo</th><th className="num">Sự cố thật</th><th className="num">Báo giả</th><th className="num">Tỉ lệ</th></tr></thead>
              <tbody>
                {r.by_alertname.map((g) => (
                  <tr key={g.alertname}>
                    <td><Link to={`/su-co?status=all&alertname=${g.alertname}&test=false`}>{g.alertname}</Link></td>
                    <td className="num">{g.total}</td>
                    <td className="num">{g.false_positive}</td>
                    <td className="num">{rate(g.rate)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
    </Card>
  );
}
