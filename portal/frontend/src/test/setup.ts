import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

// ECharts cần canvas thật; trong test thay bằng một thẻ div có nhãn để kiểm biểu đồ có được vẽ hay không.
vi.mock("../components/EChart", async () => {
  const React = await import("react");
  return {
    EChart: ({ label, className }: { label: string; className?: string }) =>
      React.createElement("div", { role: "img", "aria-label": label, className }),
    token: (_: string, fallback: string) => fallback,
  };
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});
