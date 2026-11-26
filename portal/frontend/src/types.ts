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
  /** Khác rỗng: sự cố thử nghiệm do lần chạy kịch bản lỗi này gây ra (BR-09). */
  fault_run_id: number | null;
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
  /** test: số sự cố thử nghiệm (BR-09), đã tính trong total. */
  open_incidents: { total: number; critical: number; warning: number; firing: number; test: number };
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
  type: "opened" | "episode_firing" | "episode_resolved" | "acknowledged" | "note" | "false_positive" | "closed" | "fault_run";
  content: string | null;
  /** Chỉ có với "fault_run". */
  data?: { fault_run_id: number; case: string; scenario: string; target_host: string; injected_at: string; role: string } | null;
}

export interface FalsePositiveReport {
  from: string | null;
  to: string | null;
  incidents: number;
  test_excluded: number;
  total: number;
  false_positive: number;
  rate: number | null;
  by_alertname: { alertname: string; total: number; false_positive: number; rate: number | null }[];
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

export interface FaultParam {
  name: string;
  type: "integer" | "enum";
  min: number | null;
  max: number | null;
  default: number | string | null;
  choices: string[];
}

export interface FaultScenario {
  scenario: string;
  title: string;
  hosts: string[];
  params: FaultParam[];
  root_alert: string;
  expected_alerts: string[];
  max_hold_s: number;
  simulated?: boolean; // chỉ backend mới có: thiếu trường này = backend cũ, không cho chạy
}

export interface Preflight {
  host: string;
  clean: boolean;
  reasons: string[];
  eval_lag_s: number | null;
  vm_clock_offset_s: number | null;
  active_run_id: number | null;
}

export type FaultRunStatus = "pending" | "running" | "recovering" | "completed" | "failed" | "cancelled";

export interface FaultRun {
  id: number;
  scenario: string;
  host: string;
  params: Record<string, string | number>;
  status: FaultRunStatus;
  valid: boolean;
  invalid_reasons: string[];
  root_alert: string;
  expected_alerts: string[];
  requested_by: string | null;
  requested_at: string;
  injected_at: string | null;
  recovered_at: string | null;
  stop_reason: string | null;
  first_detection_s: number | null;
  root_detection_s: number | null;
  root_resolved_s: number | null;
  error: string | null;
}

export interface FaultRunDetail extends FaultRun {
  hold_s: number;
  note: string | null;
  vm_clock_offset_s: number | null;
  eval_lag_s: number | null;
  config: Record<string, unknown> | null;
  alerts: { alert_episode_id: number; alertname: string; instance: string; role: "root" | "expected" | "extra" | "unrelated";
            delay_s: number; received_at: string }[];
}

export interface AuditEntry {
  id: number;
  at: string;
  user: string | null;
  action: string;
  object_type: string | null;
  object_id: string | null;
  detail: Record<string, unknown> | null;
  client_ip: string | null;
}
