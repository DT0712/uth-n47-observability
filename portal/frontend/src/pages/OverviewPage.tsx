// Trang tổng quan (UC02, FR-P03) — bố cục 3 cột theo docs/02-thiet-ke/giao-dien.md mục 4.
//   Trái:  6 ô KPI, thẻ Dịch vụ, thẻ Độ trễ (đồng hồ bán nguyệt)
//   Giữa:  biểu đồ CPU, RAM, request, độ trễ theo thời gian
//   Phải:  donut sự cố theo mức độ, sự cố hiện tại, tình trạng máy chủ, cảnh báo hiện tại
// Dữ liệu: GET /api/overview, /api/overview/series, /api/incidents, /api/alerts — tự làm mới mỗi 15 s.
import { Activity, AlertTriangle, Bell, FlaskConical, Server, Timer } from "lucide-react";
import { useCallback, useMemo } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import * as ep from "../api/endpoints";
import { IncidentStatusBadge, SeverityBadge, StatusBadge, StatusDot, TestBadge } from "../components/Badges";
import { Card, Empty, ErrorBox } from "../components/Card";
import { DonutCard, GaugeCard, LineChartCard } from "../components/charts";
import { token } from "../components/EChart";
import { KpiTile } from "../components/KpiTile";
import { PageToolbar } from "../components/PageToolbar";
import { duration, pct, seconds, SEVERITY_LABEL, time } from "../format";
import { usePolling } from "../hooks/usePolling";
import type { IncidentSummary, MetricSeriesSet, Overview, OverviewSeries } from "../types";

const NO_PROM = "Không đọc được Prometheus. Chỉ số sẽ hiện khi portal nối với lab.";

export function OverviewPage() {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const range = (params.get("range") ?? "1h") as ep.Range;
  const host = params.get("host") ?? undefined;
  const service = params.get("service") ?? undefined;
  const filters = useMemo(() => ({ host, service }), [host, service]);

  const overview = usePolling(() => ep.getOverview(filters), [host, service]);
  const series = usePolling(() => ep.getOverviewSeries(range, filters), [range, host, service]);
  // Donut tính MỌI sự cố chưa đóng, cùng bộ lọc với ô KPI "Sự cố đang mở" (không phụ thuộc khoảng thời gian)
  const incidents = usePolling(
    () => ep.getIncidents({ status: "open,acknowledged", host, service, page_size: 200 }),
    [host, service],
  );
  const alerts = usePolling(() => ep.getFiringAlerts(host), [host]);

  const update = (next: Record<string, string | undefined>) => {
    const p = new URLSearchParams(params);
    for (const [k, v] of Object.entries(next)) (v ? p.set(k, v) : p.delete(k));
    setParams(p, { replace: true });
  };
  const refresh = useCallback(() => {
    overview.refresh();
    series.refresh();
    incidents.refresh();
    alerts.refresh();
  }, [overview, series, incidents, alerts]);

  const o = overview.data;
  return (
    <div className="page">
      <PageToolbar crumbs={["Tổng quan", host || service ? "Đã lọc" : "Toàn bộ lab"]} range={range}
                   onRange={(r) => update({ range: r })} onRefresh={refresh} hosts={o?.hosts ?? []} host={host}
                   service={service} onFilter={(f) => update({ host: f.host, service: f.service })} />
      {overview.error && !o && <ErrorBox>Không tải được tổng quan: {overview.error.message}</ErrorBox>}
      <div className="grid-3">
        <div className="col">
          <KpiGrid o={o} />
          <ServicesCard o={o} s={series.data} />
          <LatencyCard s={series.data} />
        </div>
        <div className="col">
          <ChartCard title="CPU" sub="% CPU theo máy" set={series.data?.cpu} s={series.data} unit="%" />
          <ChartCard title="RAM" sub="% RAM đã dùng theo máy" set={series.data?.memory} s={series.data} unit="%" />
          <ChartCard title="Request" sub="Request/giây của demo app" set={series.data?.requests} s={series.data} unit="rps" />
          <ChartCard title="Độ trễ theo thời gian" sub="p95 demo app, thời gian probe" set={series.data?.latency}
                     s={series.data} unit="s" />
        </div>
        <div className="col">
          <SeverityDonut items={incidents.data?.items ?? []} total={incidents.data?.total ?? 0} />
          <CurrentIncidents items={o?.latest_incidents ?? []} onOpen={(id) => navigate(`/su-co/${id}`)} />
          <ServerTable o={o} />
          <CurrentAlerts items={alerts.data?.items ?? []} />
        </div>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ cột trái
function KpiGrid({ o }: { o: Overview | null }) {
  const down = o ? o.hosts.filter((h) => h.up === false).length : null;
  const v = (x: number | null | undefined) => (x === null || x === undefined ? "—" : x);
  return (
    <div className="kpi-grid">
      <KpiTile icon={Server} tone="blue" label="Máy đang giám sát" value={v(o?.hosts.length)} to="/may-dich-vu" />
      <KpiTile icon={AlertTriangle} tone="pink" label="Máy DOWN" value={v(down)} to="/may-dich-vu" />
      <KpiTile icon={Bell} tone="peach" label="Cảnh báo đang firing" value={v(o?.open_incidents.firing)} to="/su-co?firing=true" />
      <KpiTile icon={Activity} tone="lavender" label="Sự cố đang mở" value={v(o?.open_incidents.total)} to="/su-co" />
      <KpiTile icon={FlaskConical} tone="mint" label="Kịch bản lỗi đang chạy" value={v(o?.faults_running)} to="/kich-ban-loi" />
      <KpiTile icon={Timer} tone="peach" label="Thời gian phát hiện TB" value={o?.detection_mean_s != null ? seconds(o.detection_mean_s) : "—"}
               to="/kich-ban-loi" />
    </div>
  );
}

function ServicesCard({ o, s }: { o: Overview | null; s: OverviewSeries | null }) {
  const services = o?.hosts.flatMap((h) => h.services.map((svc) => ({ ...svc, host: h.name }))) ?? [];
  const uptime = new Map(s?.uptime.map((u) => [u.service_id, u.ratio]) ?? []);
  return (
    <Card title="Dịch vụ" sub={!o ? "Đang tải…" : o.metrics_available
      ? `${services.filter((x) => x.up).length}/${services.length} dịch vụ đang chạy` : "Chưa có dữ liệu"}>
      {services.length === 0 && <Empty>Chưa có dịch vụ nào trong danh mục.</Empty>}
      {services.map((svc) => (
        <div className="svc-row" key={svc.id}>
          <div className="svc-icon" aria-hidden="true">{svc.name.slice(0, 1).toUpperCase()}</div>
          <div>
            <div className="name">{svc.name}</div>
            <div className="meta"><StatusDot up={svc.up} /> · máy {svc.host}</div>
          </div>
          <div className="uptime">
            <b>{uptime.get(svc.id) != null ? pct((uptime.get(svc.id) as number) * 100) : "—"}</b>
            <span className="meta">Uptime</span>
          </div>
        </div>
      ))}
    </Card>
  );
}

function LatencyCard({ s }: { s: OverviewSeries | null }) {
  return (
    <Card title="Độ trễ" sub="Giá trị hiện tại so với ngưỡng">
      {s && !s.metrics_available && <Empty>{NO_PROM}</Empty>}
      {s?.metrics_available && s.latency_now.length === 0 && <Empty>Không có dịch vụ đo độ trễ.</Empty>}
      {s?.metrics_available && (
        <div className="gauges">
          {s.latency_now.map((g) => <GaugeCard key={g.name} name={g.name} value={g.value_s} threshold={g.threshold_s} />)}
        </div>
      )}
    </Card>
  );
}

// ------------------------------------------------------------------ cột giữa
function ChartCard({ title, sub, set, s, unit }: { title: string; sub: string; set?: MetricSeriesSet; s: OverviewSeries | null; unit: string }) {
  return (
    <Card title={title} sub={sub}>
      {!s && <Empty>Đang tải…</Empty>}
      {s && !s.metrics_available && <Empty>{NO_PROM}</Empty>}
      {s?.metrics_available && set && set.series.length === 0 && <Empty>Không có dữ liệu trong khoảng này.</Empty>}
      {s?.metrics_available && set && set.series.length > 0 && <LineChartCard series={set.series} unit={unit} label={title} />}
    </Card>
  );
}

// ------------------------------------------------------------------ cột phải
function SeverityDonut({ items, total }: { items: IncidentSummary[]; total: number }) {
  const counts = { critical: 0, warning: 0, info: 0 } as Record<string, number>;
  const byAlert = new Map<string, { severity: string; n: number }>();
  for (const i of items) {
    counts[i.severity] = (counts[i.severity] ?? 0) + 1;
    const cur = byAlert.get(i.alertname) ?? { severity: i.severity, n: 0 };
    byAlert.set(i.alertname, { severity: cur.severity, n: cur.n + 1 });
  }
  const colors = { critical: token("--sev-critical", "#d93636"), warning: token("--sev-warning", "#e07b1f"), info: token("--sev-info", "#12a39a") };
  const data = (["critical", "warning", "info"] as const).map((k) => ({ name: SEVERITY_LABEL[k], value: counts[k], color: colors[k] }));
  const top = [...byAlert.entries()].sort((a, b) => b[1].n - a[1].n).slice(0, 6);
  return (
    <Card title="Sự cố theo mức độ" sub={total > items.length
      ? `Tất cả sự cố đang mở (đang hiện ${items.length}/${total})` : "Tất cả sự cố đang mở"}>
      <div className="donut-wrap">
        <DonutCard data={data} total={total} />
        {top.length === 0 ? <p className="muted">Không có sự cố.</p> : (
          <ul className="legend-list">
            {top.map(([name, x]) => (
              <li key={name}><SeverityBadge severity={x.severity} /> {name}<span className="count">{x.n}</span></li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  );
}

function CurrentIncidents({ items, onOpen }: { items: IncidentSummary[]; onOpen: (id: number) => void }) {
  return (
    <Card title="Sự cố hiện tại" sub="Chưa đóng, mới nhất trước">
      {items.length === 0 ? <Empty>Không có sự cố đang mở.</Empty> : (
        <table className="table">
          <thead><tr><th>Mức độ</th><th>Cảnh báo</th><th>Máy</th><th>Trạng thái</th><th>Mở lúc</th></tr></thead>
          <tbody>
            {items.map((i) => (
              <tr key={i.id} className="link" onClick={() => onOpen(i.id)} tabIndex={0}
                  onKeyDown={(e) => e.key === "Enter" && onOpen(i.id)}>
                <td><SeverityBadge severity={i.severity} /></td>
                <td>{i.alertname}<TestBadge runId={i.fault_run_id} inline /></td>
                <td>{i.host ?? i.instance}</td>
                <td><IncidentStatusBadge status={i.status} firing={i.firing} /></td>
                <td>{time(i.opened_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  );
}

function ServerTable({ o }: { o: Overview | null }) {
  return (
    <Card title="Tình trạng máy chủ">
      {!o ? <Empty>Đang tải…</Empty> : (
        <table className="table">
          <thead><tr><th>Máy</th><th>Trạng thái</th><th className="num">CPU</th><th className="num">RAM</th><th className="num">Đĩa</th><th className="num">Uptime</th></tr></thead>
          <tbody>
            {o.hosts.map((h) => (
              <tr key={h.id}>
                <td>{h.name}</td>
                <td><StatusBadge up={h.up} /></td>
                <td className="num">{pct(h.cpu_percent)}</td>
                <td className="num">{pct(h.memory_percent)}</td>
                <td className="num">{pct(h.disk_percent)}</td>
                <td className="num">{duration(h.uptime_s)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {o && !o.metrics_available && <p className="sub" style={{ marginTop: 10 }}>{NO_PROM}</p>}
    </Card>
  );
}

function CurrentAlerts({ items }: { items: { id: number; alertname: string; instance: string; severity: string; first_received_at: string }[] }) {
  return (
    <Card title="Cảnh báo hiện tại" sub="Các đợt đang firing">
      {items.length === 0 ? <Empty>Không có cảnh báo đang firing.</Empty> : (
        <table className="table">
          <thead><tr><th>Mức độ</th><th>Cảnh báo</th><th>Instance</th><th>Firing từ</th></tr></thead>
          <tbody>
            {items.map((a) => (
              <tr key={a.id}><td><SeverityBadge severity={a.severity} /></td><td>{a.alertname}</td><td>{a.instance}</td><td>{time(a.first_received_at)}</td></tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  );
}
