// Máy & dịch vụ (UC02–UC04, FR-P04–P06): danh sách máy, chi tiết máy, chi tiết dịch vụ, panel Grafana nhúng.
// Biểu đồ dùng chung LineChartCard (cùng kiểu với trang tổng quan); khoảng thời gian nằm trên URL (?range=6h).
import { ExternalLink } from "lucide-react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import * as ep from "../api/endpoints";
import { IncidentStatusBadge, SeverityBadge, StatusBadge, StatusDot } from "../components/Badges";
import { Card, Empty, ErrorBox } from "../components/Card";
import { SkeletonChart, SkeletonText } from "../components/Skeleton";
import { LoadFailed } from "../components/StatusPanel";
import { LineChartCard } from "../components/charts";
import { ago, bytesPerSec, duration, pct } from "../format";
import { dashboardUid, GRAFANA_PANELS, soloUrl, withRange } from "../grafana";
import { usePolling } from "../hooks/usePolling";
import type { IncidentSummary, MetricSeries, MetricSeriesSet, OverviewHost } from "../types";
import { useTitle } from "../hooks/useTitle";

const RANGES: { value: ep.MetricRange; label: string }[] = [
  { value: "15m", label: "15 phút" }, { value: "1h", label: "1 giờ" }, { value: "6h", label: "6 giờ" },
  { value: "24h", label: "24 giờ" }, { value: "7d", label: "7 ngày" },
];
const METRIC_TITLE: Record<string, [string, string]> = {
  cpu: ["CPU", "%"], memory: ["RAM", "%"], disk: ["Đĩa", "%"], network_rx: ["Mạng nhận", "B/s"], network_tx: ["Mạng gửi", "B/s"],
  up: ["Trạng thái up (1 = up)", "0/1"], probe_success: ["Probe thành công (1 = ok)", "0/1"], probe_duration: ["Thời gian probe", "s"],
  request_rate: ["Request/giây", "rps"], latency_p95: ["Độ trễ p95", "s"], error_ratio: ["Tỉ lệ lỗi 5xx", "ratio"],
  connections_active: ["Kết nối đang mở", "count"], connections_usage: ["% kết nối PostgreSQL", "%"],
  transactions: ["Giao dịch/giây", "rps"],
};

function useRange(): [ep.MetricRange, (r: string) => void] {
  const [params, setParams] = useSearchParams();
  const range = (params.get("range") ?? "1h") as ep.MetricRange;
  return [range, (r) => {
    const p = new URLSearchParams(params);
    p.set("range", r);
    setParams(p, { replace: true });
  }];
}

function RangeSelect({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <select className="range-select" aria-label="Khoảng thời gian" value={value} onChange={(e) => onChange(e.target.value)}>
      {RANGES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
    </select>
  );
}

/** Mở dashboard Grafana với biến của đối tượng và khoảng thời gian đang chọn (FR-P05). */
function GrafanaButton({ url, range }: { url: string | null | undefined; range?: string }) {
  if (!url) return null;
  return (
    <a className="btn" href={range ? withRange(url, range) : url} target="_blank" rel="noreferrer">
      Mở Grafana <ExternalLink size={13} strokeWidth={1.5} style={{ verticalAlign: -2 }} />
    </a>
  );
}

/** Panel Grafana nhúng d-solo (FR-P06, ADR-0008): những biểu đồ portal không tự vẽ, cùng khoảng thời gian với trang. */
function GrafanaPanels({ url, range }: { url: string | null | undefined; range: string }) {
  const panels = url ? GRAFANA_PANELS[dashboardUid(url) ?? ""] : undefined;
  if (!url || !panels) return null;
  return (
    <Card title="Panel Grafana" sub="Nhúng từ Grafana (Viewer ẩn danh). Panel trống thì kiểm Grafana ở cổng 3000 hoặc dùng nút Mở Grafana.">
      <div className="grafana-panels">
        {panels.map((p) => (
          <iframe key={`${p.id}-${range}`} title={`Grafana: ${p.title}`} src={soloUrl(url, p.id, range)} loading="lazy" />
        ))}
      </div>
    </Card>
  );
}

/** Gom các series cùng `metric` thành một biểu đồ (vd. đĩa có nhiều phân vùng). */
function MetricCharts({ set, error }: { set: MetricSeriesSet | null; error: Error | null }) {
  if (error) {
    return <ErrorBox>{/prometheus/i.test(error.message) ? "Không đọc được Prometheus. Biểu đồ sẽ hiện khi portal nối với lab." : error.message}</ErrorBox>;
  }
  if (!set) return <div className="chart-grid">{[0, 1, 2, 3].map((i) => <section className="card" key={i}><SkeletonChart label="Đang tải biểu đồ" /></section>)}</div>;
  const groups = new Map<string, MetricSeries[]>();
  for (const s of set.series) groups.set(s.metric, [...(groups.get(s.metric) ?? []), s]);
  if (groups.size === 0) return <Empty>Không có dữ liệu trong khoảng này.</Empty>;
  return (
    <div className="chart-grid">
      {[...groups.entries()].map(([metric, series]) => {
        const [title, unit] = METRIC_TITLE[metric] ?? [metric, series[0].unit];
        return (
          <Card key={metric} title={title} sub={series.length > 1 ? `${series.length} đường` : undefined}>
            <LineChartCard series={series} unit={unit} label={title} />
          </Card>
        );
      })}
    </div>
  );
}

function IncidentsCard({ items, title = "Sự cố liên quan" }: { items: IncidentSummary[]; title?: string }) {
  return (
    <Card title={title} sub="Chưa đóng">
      {items.length === 0 ? <Empty>Không có sự cố đang mở.</Empty> : (
        <table className="table">
          <tbody>
            {items.map((i) => (
              <tr key={i.id}>
                <td><SeverityBadge severity={i.severity} /></td>
                <td><Link to={`/su-co/${i.id}`}>{i.alertname}</Link></td>
                <td><IncidentStatusBadge status={i.status} firing={i.firing} /></td>
                <td className="muted">{ago(i.opened_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  );
}

// ------------------------------------------------------------------ danh sách máy
export function HostListPage() {
  useTitle("Máy & dịch vụ");
  const overview = usePolling(() => ep.getOverview({}), []);
  const o = overview.data;
  return (
    <div className="page">
      <div className="toolbar"><div className="breadcrumb"><strong>Máy & dịch vụ</strong></div></div>
      {overview.error && !o && <ErrorBox>{overview.error.message}</ErrorBox>}
      {o && !o.metrics_available && <p className="notice info">Không đọc được Prometheus: trạng thái và chỉ số hiện "Không rõ".</p>}
      <div className="host-grid">
        {!o && !overview.error && [0, 1, 2].map((i) => (
          <section className="card host-card" key={i}><SkeletonText lines={7} label="Đang tải máy" /></section>
        ))}
        {(o?.hosts ?? []).map((h) => <HostCard key={h.id} h={h} />)}
      </div>
    </div>
  );
}

function HostCard({ h }: { h: OverviewHost }) {
  return (
    <section className="card host-card" aria-label={`Máy ${h.name}`}>
      <div className="incident-head">
        <h2 style={{ margin: 0 }}><Link to={`/may-dich-vu/${h.id}`}>{h.name}</Link></h2>
        <StatusBadge up={h.up} />
        {h.open_incidents > 0 && <span className="badge-sm st-open">{h.open_incidents} sự cố</span>}
      </div>
      <dl className="kv">
        <dt>CPU</dt><dd>{pct(h.cpu_percent)}</dd>
        <dt>RAM</dt><dd>{pct(h.memory_percent)}</dd>
        <dt>Đĩa /</dt><dd>{pct(h.disk_percent)}</dd>
        <dt>Uptime</dt><dd>{duration(h.uptime_s)}</dd>
      </dl>
      <div className="muted" style={{ fontSize: 13 }}>Dịch vụ</div>
      {h.services.length === 0 ? <p className="muted">Không có dịch vụ được giám sát.</p> : (
        <ul className="svc-list">
          {h.services.map((s) => (
            <li key={s.id}><Link to={`/may-dich-vu/dich-vu/${s.id}`}>{s.name}</Link> <StatusDot up={s.up} /></li>
          ))}
        </ul>
      )}
      <div className="actions" style={{ marginTop: 12 }}>
        <Link className="btn btn-dark" to={`/may-dich-vu/${h.id}`}>Xem chi tiết</Link>
        <GrafanaButton url={h.grafana_url} />
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ chi tiết máy
export function HostDetailPage() {
  const id = Number(useParams().id);
  const [range, setRange] = useRange();
  const host = usePolling(() => ep.getHost(id), [id], 60000);
  useTitle(host.data ? `Máy ${host.data.name}` : "Máy");
  const name = host.data?.name;
  const live = usePolling(() => (name ? ep.getOverview({ host: name }) : Promise.resolve(null)), [name]);
  const metrics = usePolling(() => ep.getHostMetrics(id, range), [id, range]);
  const incidents = usePolling(() => (name ? ep.listIncidents({ host: name, status: "open,acknowledged", page_size: 20 })
                                            : Promise.resolve(null)), [name]);
  if (host.error && !host.data) {
    return <div className="page"><LoadFailed error={host.error} what="máy" back="/may-dich-vu" backLabel="Về danh sách máy" /></div>;
  }
  const h = host.data;
  const now = live.data?.hosts.find((x) => x.name === name);
  return (
    <div className="page">
      <div className="toolbar">
        <div className="breadcrumb"><Link to="/may-dich-vu">Máy & dịch vụ</Link> › <strong>{h?.name ?? "…"}</strong></div>
        <div className="spacer" />
        <GrafanaButton url={h?.grafana_url} range={range} />
        <RangeSelect value={range} onChange={setRange} />
      </div>
      {h && (
        <div className="kpi-grid kpi-row" aria-label="Chỉ số hiện tại">
          <Stat label="Trạng thái" value={now ? (now.up === null ? "Không rõ" : now.up ? "UP" : "DOWN") : "—"} tone="blue" />
          <Stat label="CPU" value={pct(now?.cpu_percent)} tone="peach" />
          <Stat label="RAM" value={pct(now?.memory_percent)} tone="lavender" />
          <Stat label="Đĩa /" value={pct(now?.disk_percent)} tone="pink" />
          <Stat label="Mạng nhận / gửi" value={`${bytesPerSec(now?.network_rx_bps)} / ${bytesPerSec(now?.network_tx_bps)}`} tone="mint" />
          <Stat label="Uptime" value={duration(now?.uptime_s)} tone="blue" />
        </div>
      )}
      <div className="grid-2">
        <div className="col"><MetricCharts set={metrics.data} error={metrics.error} /></div>
        <div className="col">
          <Card title="Thông tin">
            <dl className="kv">
              <dt>Địa chỉ</dt><dd>{h?.address ?? "—"}</dd>
              <dt>Nhãn instance</dt><dd><code>{h?.prom_instance}</code></dd>
              <dt>Mô tả</dt><dd>{h?.description ?? "—"}</dd>
            </dl>
          </Card>
          <Card title="Dịch vụ">
            {!h || h.services.length === 0 ? <Empty>Không có dịch vụ.</Empty> : (
              <ul className="svc-list">
                {h.services.map((s) => {
                  const st = now?.services.find((x) => x.id === s.id);
                  return <li key={s.id}><Link to={`/may-dich-vu/dich-vu/${s.id}`}>{s.name}</Link> <StatusDot up={st?.up ?? null} /></li>;
                })}
              </ul>
            )}
          </Card>
          <IncidentsCard items={incidents.data?.items ?? []} />
        </div>
      </div>
      <GrafanaPanels url={h?.grafana_url} range={range} />
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <div className={`kpi ${tone}`} aria-label={`${label}: ${value}`}>
      <div className="label" style={{ marginTop: 0 }}>{label}</div>
      <div className="value text">{value}</div>
    </div>
  );
}

// ------------------------------------------------------------------ chi tiết dịch vụ
export function ServiceDetailPage() {
  const id = Number(useParams().id);
  const [range, setRange] = useRange();
  const svc = usePolling(() => ep.getService(id), [id], 60000);
  useTitle(svc.data ? `Dịch vụ ${svc.data.name}` : "Dịch vụ");
  const hostId = svc.data?.host_id;
  const host = usePolling(() => (hostId ? ep.getHost(hostId) : Promise.resolve(null)), [hostId], 60000);
  const metrics = usePolling(() => ep.getServiceMetrics(id, range), [id, range]);
  const incidents = usePolling(() => (svc.data && host.data
    ? ep.listIncidents({ host: host.data.name, service: svc.data.name, status: "open,acknowledged", page_size: 20 })
    : Promise.resolve(null)), [svc.data?.name, host.data?.name]);
  if (svc.error && !svc.data) {
    return <div className="page"><LoadFailed error={svc.error} what="dịch vụ" back="/may-dich-vu" backLabel="Về danh sách máy" /></div>;
  }
  const s = svc.data;
  return (
    <div className="page">
      <div className="toolbar">
        <div className="breadcrumb">
          <Link to="/may-dich-vu">Máy & dịch vụ</Link> › {host.data ? <Link to={`/may-dich-vu/${host.data.id}`}>{host.data.name}</Link> : "…"}
          {" › "}<strong>{s?.name ?? "…"}</strong>
        </div>
        <div className="spacer" />
        <GrafanaButton url={s?.grafana_url} range={range} />
        <RangeSelect value={range} onChange={setRange} />
      </div>
      <div className="grid-2">
        <div className="col"><MetricCharts set={metrics.data} error={metrics.error} /></div>
        <div className="col">
          <Card title="Thông tin">
            <dl className="kv">
              <dt>Loại</dt><dd>{s?.kind}</dd>
              <dt>Nhãn Prometheus</dt><dd><code>{s ? Object.entries(s.prom_labels).map(([k, v]) => `${k}="${v}"`).join(", ") : ""}</code></dd>
              <dt>Probe</dt><dd>{s?.probe_instance ?? "—"}</dd>
            </dl>
          </Card>
          <IncidentsCard items={incidents.data?.items ?? []} />
        </div>
      </div>
      <GrafanaPanels url={s?.grafana_url} range={range} />
    </div>
  );
}
