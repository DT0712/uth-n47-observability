// Ngưỡng hiện hành (UC11, FR-P12): đọc lab:threshold:* từ Prometheus. Portal chỉ hiển thị; sửa ngưỡng trong
// monitor/prometheus/rules/thresholds.yml (ADR-0004).
import * as ep from "../api/endpoints";
import { Card, Empty, ErrorBox } from "../components/Card";
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
    </div>
  );
}
