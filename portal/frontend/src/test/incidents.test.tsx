// Test trang sự cố và runbook (GĐ6 phần 2): danh sách + bộ lọc, chi tiết + thao tác, runbook. Backend giả.
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { App } from "../App";
import { ADMIN, mockFetch } from "./mockApi";

const base = {
  id: 7, alertname: "NginxDown", instance: "web", host: "web", service: "nginx", severity: "critical",
  status: "open", firing: true, is_false_positive: false, fault_run_id: null as number | null, episode_count: 1, summary: "Nginx trên VM web không phản hồi",
  opened_at: "2026-11-26T07:00:00Z", acknowledged_at: null, closed_at: null,
};

function detail(over: Record<string, unknown> = {}) {
  return {
    ...base, acknowledged_by: null, closed_by: null, false_positive_reason: null, conclusion: null, can_close: false,
    grafana_url: "http://localhost:3000/d/lab-host?var-instance=web",
    runbook: { alertname: "NginxDown", title: "Nginx trên VM web dừng", severity: "critical", category: "service",
               status: "draft", loaded_at: "2026-11-26T07:00:00Z" },
    episodes: [{ id: 1, fingerprint: "fp", alertname: "NginxDown", instance: "web", host: "web", service: "nginx",
                 severity: "critical", status: "firing", starts_at: "2026-11-26T06:59:55Z", ends_at: null,
                 first_received_at: "2026-11-26T07:00:00Z", resolved_received_at: null, labels: {}, annotations: {},
                 incident_id: 7 }],
    events: [{ id: 1, at: "2026-11-26T07:00:00Z", user: null, type: "opened", content: "Nginx trên VM web không phản hồi" },
             { id: 2, at: "2026-11-26T07:00:00Z", user: null, type: "episode_firing", content: null }],
    ...over,
  };
}

const RUNBOOK = { alertname: "NginxDown", title: "Nginx trên VM web dừng", severity: "critical", category: "service",
                  status: "draft", loaded_at: "2026-11-26T07:00:00Z", source_path: "runbooks/NginxDown.md",
                  body_md: "# NginxDown\n\n## Kiểm tra nhanh\n\n1. `systemctl status nginx`\n\n<script>alert(1)</script>" };

function common() {
  return {
    "GET /api/auth/me": ADMIN,
    "/api/hosts": [{ id: 1, name: "db", services: [] }, { id: 3, name: "web", services: [] }],
    "/api/runbooks": [{ ...RUNBOOK, body_md: undefined }, { alertname: "HostHighCpu", title: "CPU cao", severity: "warning",
                        category: "host", status: "draft", loaded_at: "2026-11-26T07:00:00Z" }],
    "/api/runbooks/NginxDown": RUNBOOK,
  };
}

function openAt(path: string) {
  sessionStorage.setItem("obslab.token", "tok");
  window.history.pushState({}, "", path);
  return render(<App />);
}

describe("danh sách sự cố", () => {
  it("mặc định hiện sự cố chưa đóng; bộ lọc nằm trên URL và gửi đúng tham số", async () => {
    const calls = mockFetch({ ...common(), "/api/incidents": { items: [base], total: 1, page: 1, page_size: 25 } });
    openAt("/su-co");
    const row = (await screen.findByText("NginxDown", { selector: "td b" })).closest("tr")!;
    expect(within(row).getByText("Nghiêm trọng")).toBeInTheDocument();
    expect(within(row).getByText("Mở")).toHaveClass("st-open");
    const first = calls.find((c) => c.url.pathname === "/api/incidents")!;
    expect(first.url.searchParams.get("status")).toBe("open,acknowledged");
    await userEvent.selectOptions(screen.getByLabelText("Mức độ"), "critical");
    await userEvent.selectOptions(await screen.findByLabelText("Máy"), "web");
    await userEvent.click(screen.getByLabelText("Đang firing"));
    await waitFor(() => expect(window.location.search).toContain("firing=true"));
    expect(window.location.search).toContain("severity=critical");
    await waitFor(() => {
      const last = calls.filter((c) => c.url.pathname === "/api/incidents").at(-1)!;
      expect(Object.fromEntries(last.url.searchParams)).toMatchObject({ severity: "critical", host: "web", firing: "true" });
    });
  });

  it("chọn 'Tất cả' thì không gửi status; bấm dòng mở chi tiết", async () => {
    const calls = mockFetch({ ...common(), "/api/incidents": { items: [base], total: 1, page: 1, page_size: 25 },
                              "/api/incidents/7": detail() });
    openAt("/su-co");
    await userEvent.selectOptions(await screen.findByLabelText("Trạng thái xử lý"), "all");
    await waitFor(() => expect(calls.filter((c) => c.url.pathname === "/api/incidents").at(-1)!.url.searchParams.has("status")).toBe(false));
    await userEvent.click(screen.getByText("NginxDown", { selector: "td b" }));
    expect(await screen.findByRole("heading", { name: "NginxDown", level: 1 })).toBeInTheDocument();
    expect(window.location.pathname).toBe("/su-co/7");
  });

  it("phân trang", async () => {
    const calls = mockFetch({ ...common(), "/api/incidents": { items: [base], total: 60, page: 1, page_size: 25 } });
    openAt("/su-co");
    expect(await screen.findByText("1–25 / 60")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Sau ›" }));
    await waitFor(() => expect(calls.filter((c) => c.url.pathname === "/api/incidents").at(-1)!.url.searchParams.get("page")).toBe("2"));
  });

  it("sự cố thử nghiệm có nhãn; ô 'Ẩn sự cố thử nghiệm' gửi test=false", async () => {
    const test = { ...base, id: 8, alertname: "HostHighCpu", fault_run_id: 12 };
    const calls = mockFetch({ ...common(), "/api/incidents": { items: [base, test], total: 2, page: 1, page_size: 25 } });
    openAt("/su-co");
    const row = (await screen.findByText("HostHighCpu", { selector: "td b" })).closest("tr")!;
    expect(within(row).getByText("thử nghiệm")).toHaveAttribute("title", "Do kịch bản lỗi #12 gây ra");
    const real = screen.getByText("NginxDown", { selector: "td b" }).closest("tr")!;
    expect(within(real).queryByText("thử nghiệm")).toBeNull();
    expect(calls.find((c) => c.url.pathname === "/api/incidents")!.url.searchParams.has("test")).toBe(false);
    await userEvent.click(screen.getByLabelText("Ẩn sự cố thử nghiệm"));
    await waitFor(() => expect(window.location.search).toContain("test=false"));
    await waitFor(() => expect(calls.filter((c) => c.url.pathname === "/api/incidents").at(-1)!.url.searchParams.get("test")).toBe("false"));
  });

  it("không có sự cố", async () => {
    mockFetch({ ...common(), "/api/incidents": { items: [], total: 0, page: 1, page_size: 25 } });
    openAt("/su-co");
    expect(await screen.findByText("Không có sự cố nào khớp bộ lọc.")).toBeInTheDocument();
  });
});

describe("chi tiết sự cố", () => {
  it("hiện thông tin, đợt cảnh báo, dòng thời gian, runbook; nút Đóng bị tắt khi còn firing", async () => {
    mockFetch({ ...common(), "/api/incidents/7": detail() });
    openAt("/su-co/7");
    expect(await screen.findByRole("heading", { name: "NginxDown", level: 1 })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Xác nhận" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Đóng sự cố" })).toBeDisabled();
    expect(screen.getByText(/chưa đóng được \(BR-01\)/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Mở Grafana/ })).toHaveAttribute("href", expect.stringContaining("var-instance=web"));
    const timeline = screen.getByRole("region", { name: "Dòng thời gian" });
    expect(within(timeline).getByText("Mở sự cố")).toBeInTheDocument();
    const rb = await screen.findByRole("article", { name: "Runbook NginxDown" });
    expect(within(rb).getByRole("heading", { name: "Kiểm tra nhanh" })).toBeInTheDocument();
    expect(within(rb).getByText("systemctl status nginx").tagName).toBe("CODE");
    expect(document.querySelector("script")?.textContent ?? "").not.toContain("alert(1)");  // HTML nhúng không được chạy
  });

  it("sự cố thử nghiệm: nhãn, nguồn và dòng thời gian dẫn tới lần chạy kịch bản lỗi", async () => {
    mockFetch({ ...common(), "/api/incidents/7": detail({
      fault_run_id: 12,
      events: [...detail().events, { id: 3, at: "2026-11-26T07:00:00Z", user: null, type: "fault_run",
        content: "Do kịch bản lỗi #12 (dừng nginx) gây ra lúc 2026-11-26T06:59:20Z",
        data: { fault_run_id: 12, case: "dừng nginx", scenario: "service-stop", target_host: "web",
                injected_at: "2026-11-26T06:59:20Z", role: "root" } }],
    }) });
    openAt("/su-co/7");
    const info = await screen.findByRole("region", { name: "Thông tin sự cố" });
    expect(within(info).getByText("thử nghiệm")).toBeInTheDocument();
    expect(within(info).getByRole("link", { name: "Kịch bản lỗi #12" })).toHaveAttribute("href", "/kich-ban-loi/12");
    expect(within(info).getByRole("button", { name: "Đánh dấu báo giả" })).toBeEnabled();  // không tự đánh dấu báo giả
    const timeline = screen.getByRole("region", { name: "Dòng thời gian" });
    expect(within(timeline).getByText("Kịch bản lỗi")).toBeInTheDocument();
    expect(within(timeline).getByRole("link", { name: "kịch bản lỗi #12" })).toHaveAttribute("href", "/kich-ban-loi/12");
    expect(timeline.querySelector(".ev-fault_run .content")?.textContent).toMatch(/^Do kịch bản lỗi #12 \(dừng nginx\) gây ra lúc \S/);
  });

  it("xác nhận gọi đúng API rồi tải lại", async () => {
    let state = detail();
    const calls = mockFetch({
      ...common(),
      "GET /api/incidents/7": () => ({ body: state }),
      "POST /api/incidents/7/acknowledge": () => {
        state = detail({ status: "acknowledged", acknowledged_by: "admin", acknowledged_at: "2026-11-26T07:01:00Z" });
        return { body: state };
      },
    });
    openAt("/su-co/7");
    await userEvent.click(await screen.findByRole("button", { name: "Xác nhận" }));
    expect(await screen.findByText("Đã xác nhận")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Xác nhận" })).toBeDisabled();
    expect(calls.some((c) => c.url.pathname === "/api/incidents/7/acknowledge" && c.init.method === "POST")).toBe(true);
  });

  it("thêm ghi chú", async () => {
    const calls = mockFetch({ ...common(), "GET /api/incidents/7": detail(),
      "POST /api/incidents/7/notes": () => ({ status: 201, body: { id: 3, at: "2026-11-26T07:02:00Z", user: "admin", type: "note", content: "x" } }) });
    openAt("/su-co/7");
    await userEvent.type(await screen.findByLabelText("Ghi chú"), "systemctl status nginx: inactive");
    await userEvent.click(screen.getByRole("button", { name: "Thêm ghi chú" }));
    await waitFor(() => expect(calls.some((c) => c.url.pathname === "/api/incidents/7/notes")).toBe(true));
    const sent = calls.find((c) => c.url.pathname === "/api/incidents/7/notes")!;
    expect(JSON.parse(String(sent.init.body))).toEqual({ content: "systemctl status nginx: inactive" });
    await waitFor(() => expect(screen.getByLabelText("Ghi chú")).toHaveValue(""));
  });

  it("báo giả bắt buộc lý do ≥ 5 ký tự; sau đó Đóng bật được và gửi kết luận", async () => {
    let state = detail();
    const calls = mockFetch({
      ...common(),
      "GET /api/incidents/7": () => ({ body: state }),
      "POST /api/incidents/7/false-positive": () => {
        state = detail({ is_false_positive: true, false_positive_reason: "Bảo trì có kế hoạch", can_close: true });
        return { body: state };
      },
      "POST /api/incidents/7/close": () => {
        state = detail({ is_false_positive: true, can_close: false, status: "closed", closed_by: "admin",
                         closed_at: "2026-11-26T07:05:00Z", conclusion: "Báo giả do bảo trì" });
        return { body: state };
      },
    });
    openAt("/su-co/7");
    await userEvent.click(await screen.findByRole("button", { name: "Đánh dấu báo giả" }));
    const dialog = screen.getByRole("dialog", { name: "Đánh dấu báo giả" });
    const submit = within(dialog).getByRole("button", { name: "Đánh dấu báo giả" });
    await userEvent.type(within(dialog).getByLabelText("Lý do (bắt buộc)"), "abc");
    expect(submit).toBeDisabled();
    await userEvent.type(within(dialog).getByLabelText("Lý do (bắt buộc)"), " - bảo trì");
    await userEvent.click(submit);
    expect(await screen.findByText("Bảo trì có kế hoạch")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Đóng sự cố" }));
    const closeDialog = screen.getByRole("dialog", { name: "Đóng sự cố" });
    await userEvent.type(within(closeDialog).getByLabelText("Kết luận"), "Báo giả do bảo trì");
    await userEvent.click(within(closeDialog).getByRole("button", { name: "Đóng sự cố" }));
    expect(await screen.findByText("Báo giả do bảo trì")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Xác nhận" })).toBeNull();  // đã đóng: hết nút thao tác
    expect(screen.queryByLabelText("Ghi chú")).toBeNull();
    const body = JSON.parse(String(calls.find((c) => c.url.pathname === "/api/incidents/7/close")!.init.body));
    expect(body).toEqual({ conclusion: "Báo giả do bảo trì" });
  });

  it("backend từ chối thì hiện nguyên thông báo", async () => {
    mockFetch({ ...common(), "GET /api/incidents/7": detail(),
      "POST /api/incidents/7/acknowledge": () => ({ status: 409, body: { error: { code: "incident_not_open",
        message: "Chỉ xác nhận được sự cố đang ở trạng thái mở" } } }) });
    openAt("/su-co/7");
    await userEvent.click(await screen.findByRole("button", { name: "Xác nhận" }));
    expect(await screen.findByText("Chỉ xác nhận được sự cố đang ở trạng thái mở")).toBeInTheDocument();
  });

  it("sự cố không tồn tại", async () => {
    mockFetch({ ...common() });
    openAt("/su-co/999");
    expect(await screen.findByRole("heading", { name: "Không tìm thấy sự cố" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Về danh sách sự cố" })).toHaveAttribute("href", "/su-co");
  });
});

describe("trang runbook", () => {
  it("danh sách bên trái, chọn trên URL, nội dung Markdown", async () => {
    mockFetch(common());
    openAt("/runbook?alert=NginxDown");
    expect(await screen.findByRole("article", { name: "Runbook NginxDown" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /NginxDown/ })).toHaveClass("active");
    expect(screen.getByRole("link", { name: /HostHighCpu/ })).toHaveAttribute("href", "/runbook?alert=HostHighCpu");
  });
});
