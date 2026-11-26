// fetch giả: trả JSON theo đường dẫn, ghi lại các request để test kiểm token, tham số.
import { vi } from "vitest";

export type Handler = (url: URL, init: RequestInit) => { status?: number; body?: unknown };

export function mockFetch(routes: Record<string, Handler | unknown>) {
  const calls: { url: URL; init: RequestInit }[] = [];
  const fn = vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = new URL(String(input), "http://localhost");
    calls.push({ url, init });
    const key = `${(init.method ?? "GET").toUpperCase()} ${url.pathname}`;
    const route = routes[key] ?? routes[url.pathname];
    if (route === undefined) return new Response(JSON.stringify({ error: { code: "not_found", message: "Không tìm thấy" } }), { status: 404 });
    const res = typeof route === "function" ? (route as Handler)(url, init) : { body: route };
    return new Response(res.body === undefined ? null : JSON.stringify(res.body), { status: res.status ?? 200 });
  });
  vi.stubGlobal("fetch", fn);
  return calls;
}

export const ADMIN = { id: 1, username: "admin", role: "admin", is_active: true, created_at: "2026-11-26T07:00:00Z", last_login_at: null };
export const OPERATOR = { ...ADMIN, id: 2, username: "op1", role: "operator" };

const emptySet = { start: "2026-11-26T06:00:00Z", end: "2026-11-26T07:00:00Z", step_s: 15, series: [] };

export function overviewData(metrics = true) {
  return {
    generated_at: "2026-11-26T07:00:00Z", metrics_available: metrics,
    hosts: [
      { id: 1, name: "db", up: metrics ? true : null, cpu_percent: metrics ? 1.7 : null, memory_percent: metrics ? 23.3 : null,
        disk_percent: metrics ? 21.9 : null, network_rx_bps: null, network_tx_bps: null, uptime_s: metrics ? 7200 : null,
        open_incidents: 0, grafana_url: null,
        services: [{ id: 3, name: "postgresql", up: metrics ? true : null, probe_ok: null, open_incidents: 0 }] },
      { id: 3, name: "web", up: metrics ? false : null, cpu_percent: metrics ? 2.3 : null, memory_percent: metrics ? 37.5 : null,
        disk_percent: metrics ? 21.3 : null, network_rx_bps: null, network_tx_bps: null, uptime_s: null, open_incidents: 1,
        grafana_url: null, services: [{ id: 1, name: "nginx", up: metrics ? false : null, probe_ok: null, open_incidents: 1 }] },
    ],
    open_incidents: { total: 1, critical: 1, warning: 0, firing: 1, test: 0 },
    latest_incidents: [{ id: 7, alertname: "NginxDown", instance: "web", host: "web", service: "nginx", severity: "critical",
                         status: "open", firing: true, is_false_positive: false, fault_run_id: null as number | null, episode_count: 1, summary: "Nginx dừng",
                         opened_at: "2026-11-26T06:55:00Z", acknowledged_at: null, closed_at: null }],
    faults_running: 0, detection_mean_s: 47.9,
  };
}

export function seriesData(metrics = true) {
  return {
    range: "1h", step_s: 15, metrics_available: metrics, cpu: emptySet, memory: emptySet, requests: emptySet,
    latency: emptySet, latency_now: metrics ? [{ name: "demo-app p95", value_s: 0.047, threshold_s: 1 }] : [],
    uptime: metrics ? [{ service_id: 1, ratio: 0.5 }, { service_id: 3, ratio: 1 }] : [],
  };
}

export function overviewRoutes(user = ADMIN, metrics = true) {
  return {
    "GET /api/auth/me": user,
    "POST /api/auth/logout": () => ({ status: 204 }),
    "/api/overview": overviewData(metrics),
    "/api/overview/series": seriesData(metrics),
    "/api/incidents": { items: overviewData().latest_incidents, total: 1, page: 1, page_size: 200 },
    "/api/alerts": { items: [], total: 0, page: 1, page_size: 20 },
  };
}
