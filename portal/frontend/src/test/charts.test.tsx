import { describe, expect, it } from "vitest";
import { seriesColor } from "../components/charts";

describe("màu biểu đồ", () => {
  it("mỗi máy một màu riêng, cố định bất kể thứ tự đường", () => {
    const colors = ["monitor", "web", "db"].map((h, i) => seriesColor(h, i));
    expect(new Set(colors).size).toBe(3);
    expect(seriesColor("web", 0)).toBe(seriesColor("web", 2));
    expect(seriesColor("db", 5)).toBe(colors[2]);
  });

  it("dịch vụ và probe có màu riêng, khác màu máy", () => {
    const hosts = new Set(["monitor", "web", "db"].map((h, i) => seriesColor(h, i)));
    expect(hosts.has(seriesColor("demo-app", 0))).toBe(false);
    expect(hosts.has(seriesColor("http://web/health", 1))).toBe(false);
  });
});
