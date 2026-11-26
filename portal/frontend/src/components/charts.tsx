// Thẻ biểu đồ dùng trên trang tổng quan: đường mảnh, đồng hồ bán nguyệt, donut.
import { useMemo } from "react";
import { seconds } from "../format";
import type { MetricSeries } from "../types";
import { EChart, token, type EChartsOption } from "./EChart";

const palette = () => ["--chart-1", "--chart-2", "--chart-3", "--chart-4"].map((n, i) =>
  token(n, ["#2d6cd2", "#7356d6", "#12a39a", "#e07b1f"][i]));

function axisLabel(unit: string) {
  return (v: number) => (unit === "%" ? `${v}%` : unit === "s" ? seconds(v) : String(v));
}

export function LineChartCard({ series, unit, label }: { series: MetricSeries[]; unit: string; label: string }) {
  const option = useMemo<EChartsOption>(() => {
    const colors = palette();
    const muted = token("--text-muted", "#6b7280");
    const line = token("--line", "#e4e7eb");
    const threshold = series.find((s) => s.threshold !== null)?.threshold ?? null;
    return {
      color: colors,
      animation: false,
      grid: { left: 44, right: 12, top: 12, bottom: 44 },
      tooltip: { trigger: "axis", valueFormatter: (v: number) => (v === null ? "—" : axisLabel(unit)(Math.round(v * 1000) / 1000)) },
      legend: { bottom: 0, icon: "circle", itemWidth: 8, itemHeight: 8, textStyle: { color: muted, fontSize: 11 } },
      xAxis: {
        type: "time", axisLine: { lineStyle: { color: line } }, axisTick: { show: false },
        axisLabel: { color: muted, fontSize: 11, hideOverlap: true }, splitLine: { show: false },
      },
      yAxis: {
        type: "value", axisLabel: { color: muted, fontSize: 11, formatter: axisLabel(unit) },
        splitLine: { lineStyle: { color: line } }, max: unit === "%" ? (v: { max: number }) => Math.max(10, Math.ceil(v.max * 1.2)) : undefined,
      },
      series: series.map((s, i) => ({
        name: s.label || s.metric, type: "line", showSymbol: false, smooth: false, lineStyle: { width: 1.5 },
        data: s.points.map(([t, v]) => [t * 1000, v]),
        markLine: i === 0 && threshold !== null ? {
          silent: true, symbol: "none", label: { show: false },
          lineStyle: { type: "dashed", color: token("--chart-threshold", "#e59a9a") }, data: [{ yAxis: threshold }],
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
