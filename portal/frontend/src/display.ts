// Chế độ Trình chiếu: chữ to hơn, tương phản cao hơn cho máy chiếu (CSS ở tokens.css, html[data-present]).
// Lưu trong localStorage để mở lại vẫn giữ; biểu đồ ECharts (vẽ trên canvas, không ăn CSS) đọc `chartFont`.
import { useSyncExternalStore } from "react";

const KEY = "obslab.present";
const SCALE = 1.15; // khớp font-size 18.4px = 16px x 1.15 trong tokens.css
const listeners = new Set<() => void>();

function read(): boolean {
  try {
    return localStorage.getItem(KEY) === "1";
  } catch {
    return false;
  }
}

let present = read();
apply();

function apply() {
  if (typeof document !== "undefined") document.documentElement.toggleAttribute("data-present", present);
}

export function setPresent(on: boolean) {
  present = on;
  try {
    localStorage.setItem(KEY, on ? "1" : "0");
  } catch {
    /* trình duyệt chặn lưu trữ: vẫn bật cho phiên hiện tại */
  }
  apply();
  listeners.forEach((l) => l());
}

export function usePresent(): boolean {
  return useSyncExternalStore((l) => {
    listeners.add(l);
    return () => listeners.delete(l);
  }, () => present);
}

/** Cỡ chữ cho biểu đồ theo chế độ hiện tại. */
export function chartFont(px: number): number {
  return present ? Math.round(px * SCALE * 1.1) : px;  // canvas trông nhỏ hơn chữ HTML cùng cỡ: tăng thêm chút
}
