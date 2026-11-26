// Kiểu dữ liệu khớp docs/02-thiet-ke/api/openapi.yaml (chỉ những phần frontend dùng).

export type Role = "admin" | "operator";
export type Severity = "critical" | "warning" | "info";

export interface User {
  id: number;
  username: string;
  role: Role;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
  expires_at: string;
  user: User;
}

export interface OverviewService {
  id: number;
  name: string;
  up: boolean | null;
  probe_ok: boolean | null;
  open_incidents: number;
}

export interface OverviewHost {
  id: number;
  name: string;
  up: boolean | null;
  cpu_percent: number | null;
  memory_percent: number | null;
  disk_percent: number | null;
  network_rx_bps: number | null;
  network_tx_bps: number | null;
  uptime_s: number | null;
  open_incidents: number;
  grafana_url: string | null;
  services: OverviewService[];
}

export interface IncidentSummary {
  id: number;
  alertname: string;
  instance: string;
  host: string | null;
  service: string | null;
  severity: Severity;
  status: "open" | "acknowledged" | "closed";
  firing: boolean;
  is_false_positive: boolean;
  episode_count: number;
  summary: string | null;
  opened_at: string;
  acknowledged_at: string | null;
  closed_at: string | null;
}

export interface Overview {
  generated_at: string;
  metrics_available: boolean;
  hosts: OverviewHost[];
  open_incidents: { total: number; critical: number; warning: number; firing: number };
  latest_incidents: IncidentSummary[];
  faults_running: number;
  detection_mean_s: number | null;
}

export interface MetricSeries {
  metric: string;
  label: string;
  unit: string;
  threshold: number | null;
  points: [number, number | null][];
}

export interface MetricSeriesSet {
  start: string;
  end: string;
  step_s: number;
  series: MetricSeries[];
}

export interface OverviewSeries {
  range: string;
  step_s: number;
  metrics_available: boolean;
  cpu: MetricSeriesSet;
  memory: MetricSeriesSet;
  requests: MetricSeriesSet;
  latency: MetricSeriesSet;
  latency_now: { name: string; value_s: number | null; threshold_s: number | null }[];
  uptime: { service_id: number; ratio: number | null }[];
}

export interface AlertEpisode {
  id: number;
  alertname: string;
  instance: string;
  host: string | null;
  service: string | null;
  severity: Severity;
  status: "firing" | "resolved";
  starts_at: string;
  first_received_at: string;
  incident_id: number | null;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface IncidentEvent {
  id: number;
  at: string;
  user: string | null;
  type: "opened" | "episode_firing" | "episode_resolved" | "acknowledged" | "note" | "false_positive" | "closed";
  content: string | null;
}

export interface AlertEpisodeFull extends AlertEpisode {
  fingerprint: string;
  ends_at: string | null;
  resolved_received_at: string | null;
  labels: Record<string, string>;
  annotations: Record<string, string>;
}

export interface RunbookSummary {
  alertname: string;
  title: string;
  severity: string | null;
  category: string | null;
  status: "draft" | "reviewed";
  loaded_at: string;
}

export interface Runbook extends RunbookSummary {
  body_md: string;
  source_path: string;
}

export interface IncidentDetail extends IncidentSummary {
  acknowledged_by: string | null;
  closed_by: string | null;
  false_positive_reason: string | null;
  conclusion: string | null;
  can_close: boolean;
  episodes: AlertEpisodeFull[];
  events: IncidentEvent[];
  runbook: RunbookSummary | null;
  grafana_url: string | null;
}

export interface HostItem {
  id: number;
  name: string;
  services: { id: number; name: string }[];
}

export interface ServiceDetail {
  id: number;
  host_id: number;
  name: string;
  kind: "web" | "app" | "database" | "other";
  prom_labels: Record<string, string>;
  probe_instance: string | null;
  grafana_dashboard_uid: string | null;
  enabled: boolean;
  grafana_url: string | null;
}

export interface HostDetail {
  id: number;
  name: string;
  address: string | null;
  prom_instance: string;
  grafana_dashboard_uid: string | null;
  description: string | null;
  enabled: boolean;
  grafana_url: string | null;
  services: ServiceDetail[];
}

export interface Threshold {
  name: string;
  value: number | null;
  status: "provisional" | "baselined";
  basis: string;
}
