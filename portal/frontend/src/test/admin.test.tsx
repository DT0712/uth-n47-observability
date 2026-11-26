// Test GĐ6 phần 5: quản trị (máy & dịch vụ, người dùng, nhật ký) và đổi mật khẩu.
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { App } from "../App";
import { parseLabels } from "../pages/AdminPage";
import { ADMIN, mockFetch, OPERATOR } from "./mockApi";

const HOSTS = [
  { id: 3, name: "web", address: "192.168.56.11", prom_instance: "web", grafana_dashboard_uid: "lab-host", description: "VM web",
    enabled: true, grafana_url: null,
    services: [{ id: 1, host_id: 3, name: "nginx", kind: "web", prom_labels: { job: "nginx", service: "nginx" }, probe_instance: "web:80",
                 grafana_dashboard_uid: "lab-nginx", enabled: true, grafana_url: null }] },
];
const USERS = { items: [ADMIN, { ...OPERATOR, is_active: true, last_login_at: "2026-11-26T07:00:00Z" }], total: 2, page: 1, page_size: 100 };
const AUDIT = { items: [{ id: 9, at: "2026-11-26T07:00:00Z", user: "admin", action: "create", object_type: "user", object_id: "2",
                          detail: { username: "op1", role: "operator" }, client_ip: "127.0.0.1" }], total: 1, page: 1, page_size: 50 };

function routes(user = ADMIN, extra: Record<string, unknown> = {}) {
  return { "GET /api/auth/me": user, "GET /api/hosts": HOSTS, "GET /api/users": USERS, "/api/audit": AUDIT, ...extra };
}

function openAt(path: string) {
  sessionStorage.setItem("obslab.token", "tok");
  window.history.pushState({}, "", path);
  return render(<App />);
}

const sent = (calls: { url: URL; init: RequestInit }[], method: string, path: string) =>
  JSON.parse(String(calls.find((c) => c.init.method === method && c.url.pathname === path)!.init.body));

describe("quản trị: máy & dịch vụ", () => {
  it("thêm máy gửi đủ trường", async () => {
    const calls = mockFetch(routes(ADMIN, { "POST /api/hosts": () => ({ status: 201, body: { ...HOSTS[0], id: 4, name: "cache" } }) }));
    openAt("/quan-tri");
    await userEvent.click(await screen.findByRole("button", { name: "Thêm máy" }));
    const dialog = screen.getByRole("dialog", { name: "Thêm máy" });
    await userEvent.type(within(dialog).getByLabelText("Tên (chữ thường, số, -)"), "cache");
    await userEvent.type(within(dialog).getByLabelText("Nhãn instance của node exporter"), "cache");
    await userEvent.click(within(dialog).getByRole("button", { name: "Thêm" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(sent(calls, "POST", "/api/hosts")).toEqual({ name: "cache", address: null, prom_instance: "cache",
      grafana_dashboard_uid: "lab-host", description: null, enabled: true });
  });

  it("sửa máy chỉ gửi trường đã đổi (PATCH một phần)", async () => {
    const calls = mockFetch(routes(ADMIN, { "PATCH /api/hosts/3": HOSTS[0] }));
    openAt("/quan-tri");
    const row = (await screen.findByText("web", { selector: "b" })).closest("tr")!;
    await userEvent.click(within(row).getAllByRole("button", { name: "Sửa" }).at(-1)!);
    const dialog = screen.getByRole("dialog", { name: "Sửa máy web" });
    const addr = within(dialog).getByLabelText("Địa chỉ");
    await userEvent.clear(addr);
    await userEvent.type(addr, "10.0.0.11");
    await userEvent.click(within(dialog).getByRole("button", { name: "Lưu" }));
    await waitFor(() => expect(calls.some((c) => c.init.method === "PATCH")).toBe(true));
    expect(sent(calls, "PATCH", "/api/hosts/3")).toEqual({ address: "10.0.0.11" });
  });

  it("thêm dịch vụ: đọc nhãn dạng job=..., service=...; lỗi backend hiện trong hộp thoại", async () => {
    mockFetch(routes(ADMIN, { "POST /api/services": () => ({ status: 409, body: { error: { code: "duplicate",
      message: "Host 'web' đã có service 'nginx'" } } }) }));
    openAt("/quan-tri");
    await userEvent.click(await screen.findByRole("button", { name: "+ Dịch vụ" }));
    const dialog = screen.getByRole("dialog", { name: "Thêm dịch vụ" });
    await userEvent.type(within(dialog).getByLabelText("Tên"), "nginx");
    await userEvent.click(within(dialog).getByRole("button", { name: "Thêm" }));
    expect(await within(dialog).findByText("Host 'web' đã có service 'nginx'")).toBeInTheDocument();
  });

  it("xóa máy hỏi xác nhận rồi gọi DELETE", async () => {
    const calls = mockFetch(routes(ADMIN, { "DELETE /api/hosts/3": () => ({ status: 204 }) }));
    vi.spyOn(window, "confirm").mockReturnValue(true);
    openAt("/quan-tri");
    const row = (await screen.findByText("web", { selector: "b" })).closest("tr")!;
    await userEvent.click(within(row).getAllByRole("button", { name: "Xóa" }).at(-1)!);
    await waitFor(() => expect(calls.some((c) => c.init.method === "DELETE" && c.url.pathname === "/api/hosts/3")).toBe(true));
    expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining("Không ảnh hưởng Prometheus"));
  });

  it("đọc nhãn Prometheus", () => {
    expect(parseLabels('job=nginx, service="nginx" ,')).toEqual({ job: "nginx", service: "nginx" });
  });
});

describe("quản trị: người dùng", () => {
  it("không tự khóa/hạ quyền mình; khóa người khác gọi PATCH is_active", async () => {
    const calls = mockFetch(routes(ADMIN, { "PATCH /api/users/2": { ...OPERATOR, is_active: false } }));
    openAt("/quan-tri?tab=nguoi-dung");
    const meRow = (await screen.findByText("(bạn)")).closest("tr")!;
    expect(within(meRow).getByRole("button", { name: "Khóa" })).toBeDisabled();
    const opRow = screen.getByText("op1").closest("tr")!;
    await userEvent.click(within(opRow).getByRole("button", { name: "Khóa" }));
    await waitFor(() => expect(calls.some((c) => c.init.method === "PATCH")).toBe(true));
    expect(sent(calls, "PATCH", "/api/users/2")).toEqual({ is_active: false });
  });

  it("thêm người dùng và đặt lại mật khẩu", async () => {
    const calls = mockFetch(routes(ADMIN, {
      "POST /api/users": () => ({ status: 201, body: { ...OPERATOR, id: 5, username: "op2" } }),
      "PATCH /api/users/2": OPERATOR,
    }));
    openAt("/quan-tri?tab=nguoi-dung");
    await userEvent.click(await screen.findByRole("button", { name: "Thêm người dùng" }));
    let dialog = screen.getByRole("dialog", { name: "Thêm người dùng" });
    await userEvent.type(within(dialog).getByLabelText(/Tên đăng nhập/), "op2");
    await userEvent.type(within(dialog).getByLabelText(/Mật khẩu/), "op2-pass-123");
    await userEvent.click(within(dialog).getByRole("button", { name: "Thêm" }));
    await waitFor(() => expect(sent(calls, "POST", "/api/users")).toEqual({ username: "op2", password: "op2-pass-123", role: "operator" }));
    const opRow = screen.getByText("op1").closest("tr")!;
    await userEvent.click(within(opRow).getByRole("button", { name: "Đặt lại mật khẩu" }));
    dialog = screen.getByRole("dialog", { name: "Đặt lại mật khẩu cho op1" });
    await userEvent.type(within(dialog).getByLabelText(/Mật khẩu mới/), "moi-pass-456");
    await userEvent.click(within(dialog).getByRole("button", { name: "Đặt lại" }));
    await waitFor(() => expect(sent(calls, "PATCH", "/api/users/2")).toEqual({ password: "moi-pass-456" }));
  });
});

describe("quản trị: nhật ký, phân quyền", () => {
  it("nhật ký hiện thao tác và lọc theo loại", async () => {
    const calls = mockFetch(routes());
    openAt("/quan-tri?tab=nhat-ky");
    expect(await screen.findByText("127.0.0.1")).toBeInTheDocument();
    expect(screen.getByText(/"username":"op1"/)).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("Loại thao tác"), "fault_start");
    await waitFor(() => expect(calls.some((c) => c.url.pathname === "/api/audit" && c.url.searchParams.get("action") === "fault_start")).toBe(true));
  });

  it("operator vào /quan-tri bị đưa về tổng quan", async () => {
    mockFetch({ ...routes(OPERATOR), "/api/overview": () => ({ status: 500 }), "/api/overview/series": () => ({ status: 500 }),
                "/api/incidents": { items: [], total: 0, page: 1, page_size: 200 }, "/api/alerts": { items: [], total: 0, page: 1, page_size: 20 } });
    openAt("/quan-tri");
    await waitFor(() => expect(window.location.pathname).toBe("/tong-quan"));
  });
});

describe("đổi mật khẩu", () => {
  it("kiểm phía giao diện rồi gọi API; mở từ menu người dùng", async () => {
    const calls = mockFetch(routes(ADMIN, { "POST /api/auth/password": () => ({ status: 204 }) }));
    openAt("/quan-tri");
    await userEvent.click(await screen.findByRole("button", { name: "Tài khoản" }));
    await userEvent.click(screen.getByRole("menuitem", { name: "Đổi mật khẩu" }));
    await userEvent.type(await screen.findByLabelText("Mật khẩu hiện tại"), "admin-pass");
    await userEvent.type(screen.getByLabelText(/Mật khẩu mới/), "moi-pass-456");
    await userEvent.type(screen.getByLabelText("Nhập lại mật khẩu mới"), "khac-pass-789");
    await userEvent.click(screen.getByRole("button", { name: "Đổi mật khẩu" }));
    expect(await screen.findByText("Hai lần nhập mật khẩu mới không khớp.")).toBeInTheDocument();
    await userEvent.clear(screen.getByLabelText("Nhập lại mật khẩu mới"));
    await userEvent.type(screen.getByLabelText("Nhập lại mật khẩu mới"), "moi-pass-456");
    await userEvent.click(screen.getByRole("button", { name: "Đổi mật khẩu" }));
    expect(await screen.findByText("Đã đổi mật khẩu.")).toBeInTheDocument();
    expect(sent(calls, "POST", "/api/auth/password")).toEqual({ current_password: "admin-pass", new_password: "moi-pass-456" });
  });

  it("sai mật khẩu hiện tại: hiện thông báo của backend", async () => {
    mockFetch(routes(ADMIN, { "POST /api/auth/password": () => ({ status: 422, body: { error: { code: "validation_error",
      message: "Dữ liệu không hợp lệ", details: [{ field: "current_password", message: "Mật khẩu hiện tại không đúng" }] } } }) }));
    openAt("/doi-mat-khau");
    await userEvent.type(await screen.findByLabelText("Mật khẩu hiện tại"), "sai");
    await userEvent.type(screen.getByLabelText(/Mật khẩu mới/), "moi-pass-456");
    await userEvent.type(screen.getByLabelText("Nhập lại mật khẩu mới"), "moi-pass-456");
    await userEvent.click(screen.getByRole("button", { name: "Đổi mật khẩu" }));
    expect(await screen.findByText("Mật khẩu hiện tại không đúng")).toBeInTheDocument();
  });
});
