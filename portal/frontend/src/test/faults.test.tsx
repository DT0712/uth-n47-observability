// Test GĐ6 phần 4: kịch bản lỗi (form, chặn backend cũ, xác nhận lab thật, lần chạy đang hoạt động, chi tiết, báo cáo).
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { App } from "../App";
import { ADMIN, mockFetch, OPERATOR } from "./mockApi";

function scenarios(simulated: boolean | null) {
  const extra = simulated === null ? {} : { simulated };  // null = backend cũ, không có trường simulated
  return [
    { scenario: "cpu", title: "CPU cao", hosts: ["web", "db"], params: [], root_alert: "HostHighCpu", expected_alerts: [], max_hold_s: 840, ...extra },
    { scenario: "memory", title: "RAM cao", hosts: ["web", "db"], root_alert: "HostHighMemory", expected_alerts: [], max_hold_s: 840,
      params: [{ name: "percent", type: "integer", min: 50, max: 97, default: 95, choices: [] }], ...extra },
    { scenario: "service-stop", title: "Dừng dịch vụ", hosts: ["web", "db"], root_alert: "theo service", expected_alerts: [], max_hold_s: 840,
      params: [{ name: "service", type: "enum", min: null, max: null, default: null, choices: ["nginx", "demo-app", "postgresql"] }], ...extra },
  ];
}

const RUN = {
  id: 5, scenario: "service-stop", host: "web", params: { service: "nginx" }, status: "completed", valid: true, invalid_reasons: [],
  root_alert: "NginxDown", expected_alerts: ["NginxDown", "ServiceDown", "EndpointDown"], requested_by: "admin",
  requested_at: "2026-11-26T07:00:00Z", injected_at: "2026-11-26T07:00:01Z", recovered_at: "2026-11-26T07:01:10Z",
  stop_reason: "root_alert_received", first_detection_s: 39.4, root_detection_s: 39.4, root_resolved_s: 55.0, error: null,
};
const DETAIL = { ...RUN, hold_s: 240, note: null, vm_clock_offset_s: 0.01, eval_lag_s: 0.002,
  config: { scrape_interval_s: 15, group_wait_s: 5, for_s: 30, match_labels: { host: "web" } },
  alerts: [{ alert_episode_id: 1, alertname: "NginxDown", instance: "web", role: "root", delay_s: 39.4, received_at: "2026-11-26T07:00:40Z" },
           { alert_episode_id: 2, alertname: "EndpointDown", instance: "web:80", role: "extra", delay_s: 95.0, received_at: "2026-11-26T07:01:36Z" }] };
const CLEAN = { host: "web", clean: true, reasons: [], eval_lag_s: 0.002, vm_clock_offset_s: 0, active_run_id: null };

function routes(user = ADMIN, simulated: boolean | null = true, extra: Record<string, unknown> = {}) {
  return {
    "GET /api/auth/me": user,
    "/api/faults/scenarios": scenarios(simulated),
    "/api/faults/preflight": CLEAN,
    "GET /api/faults/runs": { items: [RUN], total: 1, page: 1, page_size: 20 },
    "/api/faults/runs/5": DETAIL,
    ...extra,
  };
}

function openAt(path: string) {
  sessionStorage.setItem("obslab.token", "tok");
  window.history.pushState({}, "", path);
  return render(<App />);
}

describe("kịch bản lỗi", () => {
  it("chế độ xem thử: chạy kịch bản gửi đúng tham số", async () => {
    const calls = mockFetch(routes(ADMIN, true, {
      "POST /api/faults/runs": () => ({ status: 202, body: { ...RUN, id: 6, status: "running", scenario: "memory", params: { percent: 90 } } }),
      "/api/faults/runs/6": { ...DETAIL, id: 6, status: "running", alerts: [] },
    }));
    openAt("/kich-ban-loi");
    expect(await screen.findByText("Chế độ xem thử: giả lập, không đụng VM")).toBeInTheDocument();
    await userEvent.selectOptions(await screen.findByLabelText("Kịch bản"), "memory");
    const form = screen.getByRole("region", { name: "Chạy kịch bản lỗi" });
    const pct = await within(form).findByLabelText("percent (50–97)");
    await userEvent.clear(pct);
    await userEvent.type(pct, "90");
    await userEvent.selectOptions(within(form).getByLabelText("Máy"), "db");
    await userEvent.click(within(form).getByRole("button", { name: "Chạy" }));
    expect(await within(form).findByText(/Đã bắt đầu lần chạy/)).toBeInTheDocument();
    const sent = JSON.parse(String(calls.find((c) => c.init.method === "POST" && c.url.pathname === "/api/faults/runs")!.init.body));
    expect(sent).toMatchObject({ scenario: "memory", host: "db", params: { percent: 90 }, hold_s: 240, stop_on_alert: true });
  });

  it("dừng dịch vụ: chọn postgresql thì chỉ còn máy db", async () => {
    mockFetch(routes());
    openAt("/kich-ban-loi");
    await userEvent.selectOptions(await screen.findByLabelText("Kịch bản"), "service-stop");
    const form = screen.getByRole("region", { name: "Chạy kịch bản lỗi" });
    await userEvent.selectOptions(await within(form).findByLabelText("service"), "postgresql");
    const host = within(form).getByLabelText("Máy") as HTMLSelectElement;
    await waitFor(() => expect([...host.options].map((o) => o.value)).toEqual(["db"]));
    expect(within(form).getByText("PostgresDown")).toBeInTheDocument();
  });

  it("backend cũ (không có trường simulated): ẩn form", async () => {
    mockFetch(routes(ADMIN, null));
    openAt("/kich-ban-loi");
    expect(await screen.findByText(/Backend chưa cho biết chế độ chạy/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Chạy" })).toBeNull();
  });

  it("lab thật: phải đánh dấu xác nhận mới chạy", async () => {
    const calls = mockFetch(routes(ADMIN, false));
    openAt("/kich-ban-loi");
    expect(await screen.findByText("Lab thật: gây lỗi trên VM")).toBeInTheDocument();
    await userEvent.click(await screen.findByRole("button", { name: "Chạy" }));
    expect(await screen.findByText(/đánh dấu ô xác nhận/)).toBeInTheDocument();
    expect(calls.some((c) => c.init.method === "POST")).toBe(false);
  });

  it("điều kiện đo chưa đạt thì hiện lý do; máy bận thì khóa nút", async () => {
    mockFetch(routes(ADMIN, true, { "/api/faults/preflight": { ...CLEAN, clean: false, active_run_id: 9,
      reasons: ["VM web đang có lần chạy #9", "Prometheus đánh giá luật trễ 10.4s (khởi động lại Prometheus, xem SC-04)"] } }));
    openAt("/kich-ban-loi");
    expect(await screen.findByText(/SC-04/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Máy web đang bận (#9)" })).toBeDisabled();
  });

  it("operator chỉ xem lịch sử: không có form, không xuất báo cáo", async () => {
    mockFetch(routes(OPERATOR));
    openAt("/kich-ban-loi");
    expect(await screen.findByText("dừng nginx")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Chạy kịch bản lỗi" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Xuất CSV" })).toBeNull();
  });

  it("lần chạy đang hoạt động: hiện cảnh báo đã nhận, admin dừng được", async () => {
    const running = { ...RUN, id: 7, status: "running", root_detection_s: null };
    const calls = mockFetch(routes(ADMIN, true, {
      "GET /api/faults/runs": { items: [running], total: 1, page: 1, page_size: 20 },
      "/api/faults/runs/7": { ...DETAIL, ...running, alerts: [DETAIL.alerts[0]] },
      "POST /api/faults/runs/7/stop": { ...running, status: "recovering" },
    }));
    openAt("/kich-ban-loi");
    const active = await screen.findByLabelText("Lần chạy #7");
    expect(await within(active).findByText(/NginxDown sau 39,4 s/)).toBeInTheDocument();
    await userEvent.click(within(active).getByRole("button", { name: "Dừng" }));
    await waitFor(() => expect(calls.some((c) => c.url.pathname === "/api/faults/runs/7/stop")).toBe(true));
  });

  it("chi tiết lần chạy: thời gian phát hiện, vai trò cảnh báo, cấu hình", async () => {
    mockFetch(routes());
    openAt("/kich-ban-loi/5");
    expect(await screen.findByRole("heading", { name: "#5 dừng nginx", level: 1 })).toBeInTheDocument();
    expect(screen.getAllByText("39,4 s").length).toBeGreaterThan(0);
    expect(screen.getByText("Cảnh báo gốc")).toBeInTheDocument();
    expect(screen.getByText("Sau khi gỡ (nhiễu)")).toBeInTheDocument();
    expect(screen.getByText("group_wait_s")).toBeInTheDocument();
    expect(screen.getByText(/Đã nhận cảnh báo gốc/)).toBeInTheDocument();
  });

  it("xuất CSV tải file qua API có token", async () => {
    const calls = mockFetch(routes(ADMIN, true, { "/api/reports/fault-runs": () => ({ body: "run_id\n5\n" }) }));
    const createUrl = vi.fn(() => "blob:x");
    vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: createUrl, revokeObjectURL: vi.fn() }));
    openAt("/kich-ban-loi");
    await userEvent.click(await screen.findByRole("button", { name: "Xuất CSV" }));
    await waitFor(() => expect(createUrl).toHaveBeenCalled());
    const call = calls.find((c) => c.url.pathname === "/api/reports/fault-runs")!;
    expect(call.url.searchParams.get("format")).toBe("csv");
    expect(new Headers(call.init.headers).get("Authorization")).toBe("Bearer tok");
  });
});
