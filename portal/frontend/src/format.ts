// Định dạng số và thời gian hiển thị (tiếng Việt, giờ theo trình duyệt).
const nf1 = new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 1 });

export const pct = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${nf1.format(v)} %`);
export const num1 = (v: number | null | undefined) => (v === null || v === undefined ? "—" : nf1.format(v));

export function bytesPerSec(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  if (v >= 1e6) return `${nf1.format(v / 1e6)} MB/s`;
  if (v >= 1e3) return `${nf1.format(v / 1e3)} kB/s`;
  return `${nf1.format(v)} B/s`;
}

export function duration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "—";
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (d) return `${d} ngày ${h} giờ`;
  if (h) return `${h} giờ ${m} phút`;
  return `${m} phút`;
}

export function seconds(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return v < 1 ? `${Math.round(v * 1000)} ms` : `${nf1.format(v)} s`;
}

export function time(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("vi-VN", { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit" });
}

export const SEVERITY_LABEL: Record<string, string> = { critical: "Nghiêm trọng", warning: "Cao", info: "Thấp" };
export const STATUS_LABEL: Record<string, string> = { open: "Mở", acknowledged: "Đã xác nhận", closed: "Đã đóng" };
