// Test giao diện: đăng nhập, phân quyền menu, trang tổng quan (dữ liệu giả, không cần backend).
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { api, ApiError, setToken, setUnauthorizedHandler } from "../api/client";
import { App } from "../App";
import { ADMIN, mockFetch, OPERATOR, overviewRoutes } from "./mockApi";

function openAt(path: string) {
  window.history.pushState({}, "", path);
  return render(<App />);
}

describe("client", () => {
  it("gắn token và đổi lỗi JSON thành ApiError có thông báo tiếng Việt", async () => {
    const calls = mockFetch({ "/api/x": () => ({ status: 409, body: { error: { code: "incident_still_firing", message: "Còn firing" } } }) });
    setToken("abc");
    const err = (await api("/api/x").catch((e) => e)) as ApiError;
    expect(err).toBeInstanceOf(ApiError);
    expect(err.code).toBe("incident_still_firing");
    expect(err.message).toBe("Còn firing");
    expect(new Headers(calls[0].init.headers).get("Authorization")).toBe("Bearer abc");
    setToken(null);
  });

  it("401 gọi hàm đăng xuất", async () => {
    mockFetch({ "/api/x": () => ({ status: 401, body: { error: { code: "token_expired", message: "Hết hạn" } } }) });
    let called = false;
    setToken("abc");
    setUnauthorizedHandler(() => (called = true));
    await api("/api/x").catch(() => null);
    expect(called).toBe(true);
    setUnauthorizedHandler(null);
    setToken(null);
  });
});

describe("đăng nhập", () => {
  it("chưa đăng nhập thì về trang đăng nhập; đăng nhập đúng thì vào tổng quan", async () => {
    const calls = mockFetch({
      ...overviewRoutes(),
      "POST /api/auth/login": { access_token: "tok", token_type: "bearer", expires_at: "2026-11-26T08:00:00Z", user: ADMIN },
    });
    openAt("/tong-quan");
    await userEvent.type(await screen.findByLabelText("Tên đăng nhập"), "admin");
    await userEvent.type(screen.getByLabelText("Mật khẩu"), "admin-pass");
    await userEvent.click(screen.getByRole("button", { name: "Đăng nhập" }));
    expect(await screen.findByRole("link", { name: "Tổng quan" })).toHaveClass("active");
    expect(sessionStorage.getItem("obslab.token")).toBe("tok");
    const overviewCall = calls.find((c) => c.url.pathname === "/api/overview")!;
    expect(new Headers(overviewCall.init.headers).get("Authorization")).toBe("Bearer tok");
  });

  it("đăng nhập sai hiện thông báo của backend", async () => {
    mockFetch({ "POST /api/auth/login": () => ({ status: 401, body: { error: { code: "invalid_credentials",
      message: "Sai tên đăng nhập hoặc mật khẩu, hoặc tài khoản đã bị khóa" } } }) });
    openAt("/dang-nhap");
    await userEvent.type(await screen.findByLabelText("Tên đăng nhập"), "admin");
    await userEvent.type(screen.getByLabelText("Mật khẩu"), "sai");
    await userEvent.click(screen.getByRole("button", { name: "Đăng nhập" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Sai tên đăng nhập");
  });

  it("đăng xuất xóa token và về trang đăng nhập", async () => {
    mockFetch(overviewRoutes());
    sessionStorage.setItem("obslab.token", "tok");
    openAt("/tong-quan");
    await userEvent.click(await screen.findByRole("button", { name: "Tài khoản" }));
    await userEvent.click(screen.getByRole("menuitem", { name: "Đăng xuất" }));
    expect(await screen.findByLabelText("Tên đăng nhập")).toBeInTheDocument();
    expect(sessionStorage.getItem("obslab.token")).toBeNull();
  });
});

describe("tổng quan", () => {
  it("hiện ô KPI, dịch vụ, bảng máy chủ, sự cố và đồng hồ độ trễ", async () => {
    mockFetch(overviewRoutes());
    sessionStorage.setItem("obslab.token", "tok");
    openAt("/tong-quan");
    expect(await screen.findByLabelText("Máy đang giám sát: 2")).toBeInTheDocument();
    expect(screen.getByLabelText("Máy DOWN: 1")).toBeInTheDocument();
    expect(screen.getByLabelText("Sự cố đang mở: 1")).toBeInTheDocument();
    expect(screen.getByLabelText("Kịch bản lỗi đang chạy: 0")).toBeInTheDocument();  // số 0, không phải chữ
    expect(screen.getByText("1/2 dịch vụ đang chạy")).toBeInTheDocument();
    expect(screen.getByLabelText(/Thời gian phát hiện TB: 47,9 s/)).toBeInTheDocument();
    const servers = screen.getByRole("region", { name: "Tình trạng máy chủ" });
    const webRow = within(servers).getByText("web").closest("tr")!;
    expect(within(webRow).getByText("DOWN")).toBeInTheDocument();
    const incidents = screen.getByRole("region", { name: "Sự cố hiện tại" });
    expect(within(incidents).getByText("Nghiêm trọng")).toBeInTheDocument();
    expect(within(incidents).getByText("Mở")).toHaveClass("badge-sm", "st-open");
    expect(within(incidents).getByText("firing")).toHaveClass("badge-sm", "st-firing");
    expect(await screen.findByLabelText("demo-app p95: 47 ms")).toBeInTheDocument();
    expect(screen.getByLabelText("Sự cố theo mức độ: tổng 1")).toBeInTheDocument();
  });

  it("không có Prometheus: báo rõ, máy hiện 'Không rõ' chứ không phải DOWN, sự cố vẫn hiện", async () => {
    mockFetch(overviewRoutes(ADMIN, false));
    sessionStorage.setItem("obslab.token", "tok");
    openAt("/tong-quan");
    expect((await screen.findAllByText(/Không đọc được Prometheus/)).length).toBeGreaterThan(3);
    const servers = screen.getByRole("region", { name: "Tình trạng máy chủ" });
    expect(within(servers).getAllByText("Không rõ")).toHaveLength(2);
    expect(within(servers).queryByText("DOWN")).toBeNull();
    expect(screen.getByLabelText("Sự cố đang mở: 1")).toBeInTheDocument();
    expect(screen.getByText("Chưa có dữ liệu")).toBeInTheDocument();  // thẻ Dịch vụ, không phải "0/2"
    expect(screen.queryByText(/dịch vụ đang chạy/)).toBeNull();
  });

  it("donut tính mọi sự cố chưa đóng, cùng bộ lọc với ô KPI", async () => {
    const calls = mockFetch(overviewRoutes());
    sessionStorage.setItem("obslab.token", "tok");
    openAt("/tong-quan?host=web&service=nginx");
    expect(await screen.findByLabelText("Sự cố theo mức độ: tổng 1")).toBeInTheDocument();
    const call = calls.find((c) => c.url.pathname === "/api/incidents")!;
    expect(Object.fromEntries(call.url.searchParams)).toEqual({ status: "open,acknowledged", host: "web", service: "nginx",
                                                                page_size: "200" });
    expect(screen.getByText("Tất cả sự cố đang mở")).toBeInTheDocument();
  });

  it("chip lọc và khoảng thời gian nằm trên URL và được gửi lên API", async () => {
    const calls = mockFetch(overviewRoutes());
    sessionStorage.setItem("obslab.token", "tok");
    openAt("/tong-quan");
    await screen.findByLabelText("Máy đang giám sát: 2");
    await userEvent.selectOptions(screen.getByLabelText("Lọc theo máy"), "web");
    await userEvent.selectOptions(screen.getByLabelText("Khoảng thời gian"), "6h");
    await waitFor(() => expect(window.location.search).toContain("host=web"));
    expect(window.location.search).toContain("range=6h");
    await waitFor(() => expect(calls.some((c) => c.url.pathname === "/api/overview/series"
      && c.url.searchParams.get("range") === "6h" && c.url.searchParams.get("host") === "web")).toBe(true));
    expect(screen.getByRole("button", { name: "Bỏ lọc máy web" })).toBeInTheDocument();
  });

  it("operator không thấy menu Quản trị", async () => {
    mockFetch(overviewRoutes(OPERATOR));
    sessionStorage.setItem("obslab.token", "tok");
    openAt("/tong-quan");
    await screen.findByRole("link", { name: "Tổng quan" });
    expect(screen.queryByRole("link", { name: "Quản trị" })).toBeNull();
  });
});
