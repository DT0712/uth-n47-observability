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

  it("Prometheus lỗi", async () => {
    mockFetch(routes({ "/api/thresholds": () => ({ status: 503, body: { error: { code: "prometheus_unavailable", message: "x" } } }) }));
    openAt("/nguong");
    expect(await screen.findByText(/Không đọc được Prometheus/)).toBeInTheDocument();
  });
});
