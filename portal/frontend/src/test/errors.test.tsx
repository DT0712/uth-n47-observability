import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { App } from "../App";
import { ErrorBoundary } from "../components/ErrorBoundary";
import { mockFetch, overviewRoutes } from "./mockApi";

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
    await userEvent.click(screen.getByRole("link", { name: "Về Tổng quan" }));
    expect(window.location.pathname).toBe("/tong-quan");
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
