import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { App } from "../App";
import { ErrorBoundary } from "../components/ErrorBoundary";
import { ToastProvider, useToast } from "../components/Toast";
import { ADMIN, mockFetch, overviewRoutes } from "./mockApi";

function Boom(): JSX.Element {
  throw new Error("dữ liệu lạ");
}

describe("trang lỗi và 404 (F8)", () => {
  it("đường dẫn không có hiện trang 404, không tự chuyển về Tổng quan", async () => {
    mockFetch(overviewRoutes());
    sessionStorage.setItem("obslab.token", "tok");
    window.history.pushState({}, "", "/khong-co-trang-nay");
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Không có trang này" })).toBeInTheDocument();
    expect(screen.getByText("/khong-co-trang-nay")).toBeInTheDocument();
    expect(window.location.pathname).toBe("/khong-co-trang-nay");
    expect(document.title).toBe("Không có trang này · Obslab Portal");  // F3: tiêu đề tab theo trang
    await userEvent.click(screen.getByRole("link", { name: "Về Tổng quan" }));
    expect(window.location.pathname).toBe("/tong-quan");
    await waitFor(() => expect(document.title).toBe("Tổng quan · Obslab Portal"));
    expect(screen.getByRole("link", { name: "Obslab Portal, về Tổng quan" })).toHaveAttribute("href", "/tong-quan");
  });

  it("lỗi khi vẽ giao diện hiện thông báo thay vì trắng trang", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    render(<ErrorBoundary><Boom /></ErrorBoundary>);
    expect(screen.getByRole("heading", { name: "Trang gặp lỗi khi hiển thị" })).toBeInTheDocument();
    expect(screen.getByText(/dữ liệu lạ/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Tải lại trang" })).toBeInTheDocument();
    spy.mockRestore();
  });

  it("đổi trang thì thử vẽ lại", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    const { rerender } = render(<ErrorBoundary resetKey="/a"><Boom /></ErrorBoundary>);
    expect(screen.getByRole("heading", { name: "Trang gặp lỗi khi hiển thị" })).toBeInTheDocument();
    rerender(<ErrorBoundary resetKey="/b"><p>Trang mới</p></ErrorBoundary>);
    expect(screen.getByText("Trang mới")).toBeInTheDocument();
    spy.mockRestore();
  });
});

describe("skeleton khi đang tải (F1)", () => {
  it("tổng quan chưa có dữ liệu: ô KPI, bảng, biểu đồ hiện khung đang tải, không báo 'không có sự cố'", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      if (new URL(String(input), "http://localhost").pathname === "/api/auth/me") {
        return new Response(JSON.stringify(ADMIN), { status: 200 });
      }
      return new Promise<Response>(() => {});  // dữ liệu không bao giờ về
    }));
    sessionStorage.setItem("obslab.token", "tok");
    window.history.pushState({}, "", "/tong-quan");
    render(<App />);
    expect(await screen.findByLabelText("Sự cố đang mở: đang tải")).toBeInTheDocument();
    expect(screen.getByRole("status", { name: "Đang tải biểu đồ CPU" })).toBeInTheDocument();
    expect(screen.getByRole("status", { name: "Đang tải máy chủ" })).toBeInTheDocument();
    expect(screen.queryByText("Không có sự cố đang mở.")).not.toBeInTheDocument();
    expect(screen.queryByText("Đang tải…")).not.toBeInTheDocument();
  });
});

describe("toast (F2)", () => {
  function Buttons() {
    const toast = useToast();
    return (
      <>
        <button onClick={() => toast.success("Đã lưu")}>ok</button>
        <button onClick={() => toast.error("Không lưu được")}>err</button>
      </>
    );
  }

  it("thành công tự ẩn sau 4 s, lỗi là alert và đóng được", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    render(<ToastProvider><Buttons /></ToastProvider>);
    act(() => screen.getByText("ok").click());
    expect(screen.getByText("Đã lưu")).toBeInTheDocument();
    act(() => screen.getByText("err").click());
    expect(screen.getByRole("alert")).toHaveTextContent("Không lưu được");
    act(() => vi.advanceTimersByTime(4100));
    expect(screen.queryByText("Đã lưu")).not.toBeInTheDocument();
    expect(screen.getByText("Không lưu được")).toBeInTheDocument();  // lỗi giữ lâu hơn
    act(() => screen.getByRole("button", { name: "Đóng thông báo" }).click());
    expect(screen.queryByText("Không lưu được")).not.toBeInTheDocument();
    vi.useRealTimers();
  });
});
