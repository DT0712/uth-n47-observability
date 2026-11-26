// Các hàm gọi API theo chủ đề. Tên đường dẫn theo openapi.yaml.
import { api, download, qs } from "./client";
import type {
  AlertEpisode, AuditEntry, FalsePositiveReport, FaultRun, FaultRunDetail, FaultScenario, HostDetail, Preflight, HostItem, IncidentDetail, MetricSeriesSet, ServiceDetail, Threshold, IncidentEvent, IncidentSummary, Overview, OverviewSeries, Page, Runbook,
  RunbookSummary, TokenResponse, User,
} from "../types";

export const login = (username: string, password: string) =>
  api<TokenResponse>("/api/auth/login", { method: "POST", body: JSON.stringify({ username, password }) });
export const me = () => api<User>("/api/auth/me");
export const logout = () => api<void>("/api/auth/logout", { method: "POST" });

export type Filters = { host?: string; service?: string };
export type Range = "1h" | "6h" | "24h";

export const getOverview = (f: Filters) => api<Overview>(`/api/overview${qs(f)}`);
export const getOverviewSeries = (range: Range, f: Filters) =>
  api<OverviewSeries>(`/api/overview/series${qs({ range, ...f })}`);
export const getIncidents = (p: { from?: string; host?: string; service?: string; page_size?: number; status?: string }) =>
  api<Page<IncidentSummary>>(`/api/incidents${qs(p)}`);
export const getFiringAlerts = (host?: string) =>
  api<Page<AlertEpisode>>(`/api/alerts${qs({ status: "firing", host, page_size: 20 })}`);

// ---------------------------------------------------------- sự cố (GĐ6 phần 2)

export interface IncidentQuery {
  status?: string;
  severity?: string;
  host?: string;
  service?: string;
  alertname?: string;
  firing?: string;
  false_positive?: string;
  test?: string;
  sort?: string;
  page?: number;
  page_size?: number;
}

export const listIncidents = (q: IncidentQuery) => api<Page<IncidentSummary>>(`/api/incidents${qs({ ...q })}`);
export const getIncident = (id: number) => api<IncidentDetail>(`/api/incidents/${id}`);
export const acknowledge = (id: number) => api<IncidentDetail>(`/api/incidents/${id}/acknowledge`, { method: "POST" });
export const addNote = (id: number, content: string) =>
  api<IncidentEvent>(`/api/incidents/${id}/notes`, { method: "POST", body: JSON.stringify({ content }) });
export const markFalsePositive = (id: number, reason: string) =>
  api<IncidentDetail>(`/api/incidents/${id}/false-positive`, { method: "POST", body: JSON.stringify({ reason }) });
export const closeIncident = (id: number, conclusion: string) =>
  api<IncidentDetail>(`/api/incidents/${id}/close`, { method: "POST", body: JSON.stringify({ conclusion }) });

export const getFalsePositiveReport = (from?: string) =>
  api<FalsePositiveReport>(`/api/reports/false-positives${qs({ from })}`);

export const listRunbooks = () => api<RunbookSummary[]>("/api/runbooks");
export const getRunbook = (alertname: string) => api<Runbook>(`/api/runbooks/${encodeURIComponent(alertname)}`);
export const listHosts = () => api<HostItem[]>("/api/hosts");

// ---------------------------------------------------------- máy & dịch vụ, ngưỡng (GĐ6 phần 3)
export type MetricRange = "15m" | "1h" | "6h" | "24h" | "7d";
export const getHost = (id: number) => api<HostDetail>(`/api/hosts/${id}`);
export const getHostMetrics = (id: number, range: MetricRange) =>
  api<MetricSeriesSet>(`/api/hosts/${id}/metrics${qs({ range })}`);
export const getService = (id: number) => api<ServiceDetail>(`/api/services/${id}`);
export const getServiceMetrics = (id: number, range: MetricRange) =>
  api<MetricSeriesSet>(`/api/services/${id}/metrics${qs({ range })}`);
export const getThresholds = () => api<Threshold[]>("/api/thresholds");

// ---------------------------------------------------------- kịch bản lỗi, báo cáo (GĐ6 phần 4)
export interface FaultRunCreate {
  scenario: string;
  host: string;
  params: Record<string, string | number>;
  hold_s: number;
  stop_on_alert: boolean;
  linger_s: number;
  require_clean: boolean;
  note?: string;
}

export const getScenarios = () => api<FaultScenario[]>("/api/faults/scenarios");
export const getPreflight = (host: string) => api<Preflight>(`/api/faults/preflight${qs({ host })}`);
export const listRuns = (q: { status?: string; scenario?: string; host?: string; valid?: string; page?: number; page_size?: number }) =>
  api<Page<FaultRun>>(`/api/faults/runs${qs(q)}`);
export const getRun = (id: number) => api<FaultRunDetail>(`/api/faults/runs/${id}`);
export const startRun = (body: FaultRunCreate) => api<FaultRun>("/api/faults/runs", { method: "POST", body: JSON.stringify(body) });
export const stopRun = (id: number) => api<FaultRun>(`/api/faults/runs/${id}/stop`, { method: "POST" });
export const downloadReport = (format: "csv" | "md", validOnly: boolean) =>
  download(`/api/reports/fault-runs${qs({ format, valid_only: validOnly })}`);

// ---------------------------------------------------------- quản trị, đổi mật khẩu (GĐ6 phần 5)
export type HostInput = { name: string; address?: string | null; prom_instance: string; grafana_dashboard_uid?: string | null;
                          description?: string | null; enabled?: boolean };
export type ServiceInput = { host_id: number; name: string; kind: string; prom_labels: Record<string, string>;
                             probe_instance?: string | null; grafana_dashboard_uid?: string | null; enabled?: boolean };
const json = (method: string, body: unknown) => ({ method, body: JSON.stringify(body) });

export const listHostsFull = () => api<HostDetail[]>("/api/hosts");
export const createHost = (b: HostInput) => api<HostDetail>("/api/hosts", json("POST", b));
export const updateHost = (id: number, b: Partial<HostInput>) => api<HostDetail>(`/api/hosts/${id}`, json("PATCH", b));
export const deleteHost = (id: number) => api<void>(`/api/hosts/${id}`, { method: "DELETE" });
export const createService = (b: ServiceInput) => api<ServiceDetail>("/api/services", json("POST", b));
export const updateService = (id: number, b: Partial<ServiceInput>) => api<ServiceDetail>(`/api/services/${id}`, json("PATCH", b));
export const deleteService = (id: number) => api<void>(`/api/services/${id}`, { method: "DELETE" });

export const listUsers = (page = 1) => api<Page<User>>(`/api/users${qs({ page, page_size: 100 })}`);
export const createUser = (b: { username: string; password: string; role: string }) => api<User>("/api/users", json("POST", b));
export const updateUser = (id: number, b: { role?: string; is_active?: boolean; password?: string }) =>
  api<User>(`/api/users/${id}`, json("PATCH", b));
export const listAudit = (q: { user_id?: number; action?: string; from?: string; to?: string; page?: number; page_size?: number }) =>
  api<Page<AuditEntry>>(`/api/audit${qs(q)}`);
export const changePassword = (current_password: string, new_password: string) =>
  api<void>("/api/auth/password", json("POST", { current_password, new_password }));
