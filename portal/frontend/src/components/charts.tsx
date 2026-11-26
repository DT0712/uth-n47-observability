// Thẻ biểu đồ dùng trên trang tổng quan: đường mảnh, đồng hồ bán nguyệt, donut.
import { useMemo } from "react";
import { seconds } from "../format";
import type { MetricSeries } from "../types";
import { EChart, token, type EChartsOption } from "./EChart";

const FALLBACK = ["--chart-1", "--chart-2", "--chart-3", "--chart-4"];
const KNOWN: Record<string, [string, string]> = {
  monitor: ["--series-monitor", "#0f9f8f"],
  web: ["--series-web", "#2d6cd2"],
  db: ["--series-db", "#e8650c"],
  "demo-app": ["--series-demo-app", "#7356d6"],
};

/** Màu cố định theo đối tượng (máy, dịch vụ, probe) để cùng một máy luôn cùng màu trên mọi biểu đồ. */
export function seriesColor(label: string, index: number): string {
  if (KNOWN[label]) return token(...KNOWN[label]);
  if (label.startsWith("http") || label.includes(":")) return token("--series-probe", "#d6336c");
  const [name, fallback] = [FALLBACK[index % FALLBACK.length], ["#2d6cd2", "#7356d6", "#12a39a", "#e07b1f"][index % 4]];
  return token(name, fallback);
}

const SERIES_NAME: Record<string, string> = { latency_p95: "p95", probe_duration: "probe" };

function seriesName(s: MetricSeries): string {
  if (s.metric in SERIES_NAME && s.label) return `${s.label.replace(/^https?:\/\//, "")} ${SERIES_NAME[s.metric]}`;
  return s.label || s.metric;
}

function fmtValue(unit: string, v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  if (unit === "%") return `${v.toFixed(1)}%`;
  if (unit === "s") return seconds(v);
  if (unit === "rps") return `${v.toFixed(2)} req/s`;
  return v.toFixed(2);
}

function axisValue(unit: string, v: number): string {
  if (unit === "%") return `${v}%`;
  if (unit === "s") return v < 1 ? `${Math.round(v * 1000)} ms` : `${v} s`;
  return String(v);
}

/**
 * Biểu đồ đường dùng chung cho mọi trang (cùng một kiểu):
 * nét 1,5 px, làm mượt nhẹ, lấy mẫu LTTB; màu cố định theo máy; tooltip có đường dọc và giá trị mọi đường;
 * chú thích gọn ở góc trên phải, bấm để ẩn/hiện; trục Y tự chọn khoảng đẹp; lưới rất nhạt; đường ngưỡng nét đứt.
 */
export function LineChartCard({ series, unit, label }: { series: MetricSeries[]; unit: string; label: string }) {
  const option = useMemo<EChartsOption>(() => {
    const muted = token("--text-muted", "#6b7280");
    const grid = token("--chart-grid", "#eef0f3");
    const threshold = series.find((s) => s.threshold !== null)?.threshold ?? null;
    const maxValue = Math.max(0, ...series.flatMap((s) => s.points.map(([, v]) => v ?? 0)));
    // Chỉ vẽ đường ngưỡng khi nó nằm gần vùng dữ liệu, để không ép trục Y lên tận ngưỡng (vd 85 % khi CPU chỉ 3 %)
    const showThreshold = threshold !== null && maxValue >= threshold * 0.5;
    return {
      animation: false,
      grid: { left: 8, right: 12, top: 34, bottom: 8, containLabel: true },
      legend: {
        top: 0, right: 0, icon: "roundRect", itemWidth: 12, itemHeight: 3, itemGap: 12,
        textStyle: { color: muted, fontSize: 11 }, inactiveColor: "#c9ced6",
      },
      tooltip: {
        trigger: "axis", axisPointer: { type: "line", lineStyle: { color: "#9aa3ae", width: 1 } },
        backgroundColor: "rgba(255,255,255,0.96)", borderColor: grid, textStyle: { color: token("--text", "#1f2933"), fontSize: 12 },
        valueFormatter: (v: number) => fmtValue(unit, v),
      },
      xAxis: {
        type: "time", boundaryGap: false, axisLine: { lineStyle: { color: grid } }, axisTick: { show: false },
        axisLabel: { color: muted, fontSize: 11, hideOverlap: true }, splitLine: { show: false },
      },
      yAxis: {
        type: "value", min: 0, splitNumber: 4, scale: false,
        axisLabel: { color: muted, fontSize: 11, formatter: (v: number) => axisValue(unit, v) },
        splitLine: { lineStyle: { color: grid, width: 1 } },
      },
      series: series.map((s, i) => ({
        name: seriesName(s), type: "line", showSymbol: false, symbol: "circle", symbolSize: 5,
        smooth: 0.3, sampling: "lttb", connectNulls: false,
        color: seriesColor(s.label, i), lineStyle: { width: 1.5 },
        emphasis: { focus: "series", lineStyle: { width: 2 } },
        data: s.points.map(([t, v]) => [t * 1000, v]),
        markLine: i === 0 && showThreshold ? {
          silent: true, symbol: "none", label: { show: true, position: "insideEndTop", color: muted, fontSize: 10,
                                                   formatter: `ngưỡng ${fmtValue(unit, threshold)}` },
          lineStyle: { type: "dashed", color: token("--chart-threshold", "#e59a9a"), width: 1 }, data: [{ yAxis: threshold }],
        } : undefined,
      })),
    };
  }, [series, unit]);
  return <EChart className="chart" option={option} label={label} />;
}

/** Đồng hồ bán nguyệt: xanh < 50 % ngưỡng, cam < 100 %, đỏ ≥ ngưỡng (giao-dien.md mục 4). */
export function GaugeCard({ name, value, threshold }: { name: string; value: number | null; threshold: number | null }) {
  const option = useMemo<EChartsOption>(() => {
    const max = threshold ? threshold * 1.25 : Math.max(1, (value ?? 0) * 2);
    const ok = token("--status-up", "#2e9e52");
    const warn = token("--sev-warning", "#e07b1f");
    const bad = token("--sev-critical", "#d93636");
    const color = value === null || threshold === null ? token("--status-unknown", "#9aa3ae")
      : value >= threshold ? bad : value >= threshold / 2 ? warn : ok;
    return {
      animation: false,
      series: [{
        type: "gauge", startAngle: 180, endAngle: 0, min: 0, max, radius: "100%", center: ["50%", "72%"],
        progress: { show: true, width: 10, itemStyle: { color } }, pointer: { show: false },
        axisLine: { lineStyle: { width: 10, color: [[1, token("--line", "#e4e7eb")]] } },
        axisTick: { show: false }, splitLine: { show: false }, axisLabel: { show: false },
        title: { offsetCenter: [0, "28%"], fontSize: 11, color: token("--text-muted", "#6b7280") },
        detail: { offsetCenter: [0, "-8%"], fontSize: 18, fontWeight: 600, color: token("--text", "#1f2933"),
                  formatter: () => seconds(value) },
        data: [{ value: value ?? 0, name }],
      }],
    };
  }, [name, value, threshold]);
  return <EChart className="gauge" option={option} label={`${name}: ${seconds(value)}`} />;
}

export function DonutCard({ data, total }: { data: { name: string; value: number; color: string }[]; total: number }) {
  const option = useMemo<EChartsOption>(() => ({
    animation: false,
    tooltip: { trigger: "item" },
    title: undefined,
    series: [{
      type: "pie", radius: ["62%", "86%"], avoidLabelOverlap: false, label: {
        show: true, position: "center", formatter: () => `{n|${total}}\n{l|sự cố}`,
        rich: { n: { fontSize: 24, fontWeight: 700, color: token("--text", "#1f2933") }, l: { fontSize: 11, color: token("--text-muted", "#6b7280") } },
      },
      labelLine: { show: false },
      data: total ? data.map((d) => ({ name: d.name, value: d.value, itemStyle: { color: d.color } }))
        : [{ name: "Không có", value: 1, itemStyle: { color: token("--line", "#e4e7eb") } }],
    }],
  }), [data, total]);
  return <EChart className="donut" option={option} label={`Sự cố theo mức độ: tổng ${total}`} />;
}
