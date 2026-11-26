// Test GĐ6 phần 3: Máy & dịch vụ, Ngưỡng (backend giả).
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { App } from "../App";
import { ADMIN, mockFetch, overviewData } from "./mockApi";

const HOST = {
  id: 3, name: "web", address: "192.168.56.11", prom_instance: "web", grafana_dashboard_uid: "lab-host",
  description: "VM web", enabled: true, grafana_url: "http://localhost:3000/d/lab-host?var-instance=web",
  services: [{ id: 1, host_id: 3, name: "nginx", kind: "web", prom_labels: { job: "nginx" }, probe_instance: "web:80",
               grafana_dashboard_uid: "lab-nginx", enabled: true, grafana_url: "http://localhost:3000/d/lab-nginx" }],
};
const pts = (v: number) => [[1795676400, v], [1795676430, v + 1]];
const METRICS = {
  start: "2026-11-26T06:00:00Z", end: "2026-11-26T07:00:00Z", step_s: 30, series: [
    { metric: "cpu", label: "", unit: "%", threshold: 85, points: pts(2) },
    { metric: "disk", label: "mountpoint=/", unit: "%", threshold: 90, points: pts(21) },
    { metric: "disk", label: "mountpoint=/mnt/labdisk", unit: "%", threshold: 90, points: pts(7) },
  ],
};

function routes(extra: Record<string, unknown> = {}) {
  return {
    "GET /api/auth/me": ADMIN,
    "/api/overview": overviewData(),
    "/api/hosts/3": HOST,
    "/api/hosts/3/metrics": METRICS,
    "/api/services/1": HOST.services[0],
    "/api/services/1/metrics": { ...METRICS, series: [{ metric: "up", label: "", unit: "0/1", threshold: null, points: pts(1) }] },
    "/api/incidents": { items: overviewData().latest_incidents, total: 1, page: 1, page_size: 20 },
    ...extra,
  };
}

function openAt(path: string) {
  sessionStorage.setItem("obslab.token", "tok");
  window.history.pushState({}, "", path);
  return render(<App />);
}

describe("máy & dịch vụ", () => {
  it("danh sách máy: trạng thái, chỉ số, dịch vụ, link chi tiết", async () => {
    mockFetch(routes());
    openAt("/may-dich-vu");
    const web = await screen.findByRole("region", { name: "Máy web" });
    expect(within(web).getByText("DOWN", { selector: ".badge" })).toBeInTheDocument();
    expect(within(web).getByText("1 sự cố")).toBeInTheDocument();
    expect(within(web).getByRole("link", { name: "nginx" })).toHaveAttribute("href", "/may-dich-vu/dich-vu/1");
    expect(within(web).getByRole("link", { name: "Xem chi tiết" })).toHaveAttribute("href", "/may-dich-vu/3");
  });

  it("chi tiết máy: chỉ số hiện tại, biểu đồ gom theo chỉ số, đổi khoảng thời gian", async () => {
    const calls = mockFetch(routes());
    openAt("/may-dich-vu/3");
    expect(await screen.findByLabelText("CPU: 2,3 %")).toBeInTheDocument();
    expect(await screen.findByRole("img", { name: "CPU" })).toBeInTheDocument();
    const disk = screen.getByRole("region", { name: "Đĩa" });
    expect(within(disk).getByText("2 đường")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Mở Grafana/ })).toHaveAttribute("href", HOST.grafana_url);
    expect(screen.getByRole("link", { name: "NginxDown" })).toHaveAttribute("href", "/su-co/7");
    await userEvent.selectOptions(screen.getByLabelText("Khoảng thời gian"), "24h");
    await waitFor(() => expect(calls.some((c) => c.url.pathname === "/api/hosts/3/metrics" && c.url.searchParams.get("range") === "24h")).toBe(true));
    const inc = calls.find((c) => c.url.pathname === "/api/incidents")!;
    expect(inc.url.searchParams.get("host")).toBe("web");
  });

  it("chi tiết máy khi Prometheus lỗi", async () => {
    mockFetch(routes({ "/api/hosts/3/metrics": () => ({ status: 503, body: { error: { code: "prometheus_unavailable",
      message: "Không đọc được Prometheus: timeout" } } }) }));
    openAt("/may-dich-vu/3");
    expect(await screen.findByText(/Biểu đồ sẽ hiện khi portal nối với lab/)).toBeInTheDocument();
  });

  it("chi tiết dịch vụ: breadcrumb về máy, biểu đồ, sự cố lọc theo máy + dịch vụ", async () => {
    const calls = mockFetch(routes());
    openAt("/may-dich-vu/dich-vu/1");
    expect(await screen.findByRole("img", { name: "Trạng thái up (1 = up)" })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "web" })).toHaveAttribute("href", "/may-dich-vu/3");
    await waitFor(() => {
      const inc = calls.find((c) => c.url.pathname === "/api/incidents");
      expect(inc?.url.searchParams.get("service")).toBe("nginx");
    });
  });
});

describe("ngưỡng", () => {
  it("bảng ngưỡng, trạng thái tạm thời, cảnh báo còn provisional", async () => {
    mockFetch(routes({ "/api/thresholds": [
      { name: "host_cpu_usage_percent", value: 85, status: "provisional", basis: "chua do baseline" },
      { name: "filesystem_usage_percent", value: 90, status: "baselined", basis: "baseline 2026-11-27" },
    ] }));
    openAt("/nguong");
    expect(await screen.findByText("CPU của máy")).toBeInTheDocument();
    expect(screen.getByText("Tạm thời")).toBeInTheDocument();
    expect(screen.getByText("Đã chốt")).toBeInTheDocument();
    expect(screen.getByText(/1\/2 ngưỡng còn tạm thời/)).toBeInTheDocument();
  });

  it("tỉ lệ báo giả không tính sự cố thử nghiệm; đổi khoảng thời gian gửi from", async () => {
    const calls = mockFetch(routes({ "/api/thresholds": [], "/api/reports/false-positives": {
      from: null, to: null, incidents: 5, test_excluded: 1, total: 4, false_positive: 1, rate: 0.25,
      by_alertname: [{ alertname: "HostHighCpu", total: 2, false_positive: 1, rate: 0.5 },
                     { alertname: "NginxDown", total: 2, false_positive: 0, rate: 0 }] } }));
    openAt("/nguong");
    const card = (await screen.findByRole("heading", { name: "Tỉ lệ báo giả" })).closest("section")!;
    expect(await within(card).findByText("25 %")).toBeInTheDocument();
    expect(within(card).getByText("(1/4 sự cố thật)")).toBeInTheDocument();
    expect(within(card).getByText(/Không tính 1 sự cố thử nghiệm/)).toBeInTheDocument();
    expect(within(card).getByRole("link", { name: "HostHighCpu" })).toHaveAttribute("href", expect.stringContaining("test=false"));
    const first = calls.find((c) => c.url.pathname === "/api/reports/false-positives")!;
    expect(first.url.searchParams.has("from")).toBe(true);  // mặc định 30 ngày
    await userEvent.selectOptions(within(card).getByLabelText("Khoảng thời gian"), "all");
    await waitFor(() => expect(calls.filter((c) => c.url.pathname === "/api/reports/false-positives").at(-1)!.url.searchParams.has("from")).toBe(false));
  });

  it("Prometheus lỗi", async () => {
    mockFetch(routes({ "/api/thresholds": () => ({ status: 503, body: { error: { code: "prometheus_unavailable", message: "x" } } }) }));
    openAt("/nguong");
    expect(await screen.findByText(/Không đọc được Prometheus/)).toBeInTheDocument();
  });
});
