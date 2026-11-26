// Các hàm gọi API theo chủ đề. Tên đường dẫn theo openapi.yaml.
import { api, qs } from "./client";
import type {
  AlertEpisode, HostItem, IncidentDetail, IncidentEvent, IncidentSummary, Overview, OverviewSeries, Page, Runbook,
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

export const listRunbooks = () => api<RunbookSummary[]>("/api/runbooks");
export const getRunbook = (alertname: string) => api<Runbook>(`/api/runbooks/${encodeURIComponent(alertname)}`);
export const listHosts = () => api<HostItem[]>("/api/hosts");
