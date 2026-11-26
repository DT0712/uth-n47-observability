// Các hàm gọi API theo chủ đề. Tên đường dẫn theo openapi.yaml.
import { api, qs } from "./client";
import type { AlertEpisode, IncidentSummary, Overview, OverviewSeries, Page, TokenResponse, User } from "../types";

export const login = (username: string, password: string) =>
  api<TokenResponse>("/api/auth/login", { method: "POST", body: JSON.stringify({ username, password }) });
export const me = () => api<User>("/api/auth/me");
export const logout = () => api<void>("/api/auth/logout", { method: "POST" });

export type Filters = { host?: string; service?: string };
export type Range = "1h" | "6h" | "24h";

export const getOverview = (f: Filters) => api<Overview>(`/api/overview${qs(f)}`);
export const getOverviewSeries = (range: Range, f: Filters) =>
  api<OverviewSeries>(`/api/overview/series${qs({ range, ...f })}`);
export const getIncidents = (p: { from?: string; host?: string; page_size?: number; status?: string }) =>
  api<Page<IncidentSummary>>(`/api/incidents${qs(p)}`);
export const getFiringAlerts = (host?: string) =>
  api<Page<AlertEpisode>>(`/api/alerts${qs({ status: "firing", host, page_size: 20 })}`);
