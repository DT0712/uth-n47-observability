// Khung xám nhấp nháy giữ chỗ khi dữ liệu đang tải: bố cục không nhảy khi dữ liệu về, người xem biết phần nào đang tải.
// Mỗi khối có role="status" + nhãn "Đang tải" cho trình đọc màn hình; phần hình chỉ để trang trí (aria-hidden).
import type { CSSProperties, ReactNode } from "react";

export function Skeleton({ width, height = 12, radius, className = "" }: {
  width?: number | string; height?: number | string; radius?: number; className?: string;
}) {
  const style: CSSProperties = { width, height, borderRadius: radius };
  return <span className={`skeleton ${className}`} style={style} aria-hidden="true" />;
}

function Busy({ label = "Đang tải", className, children }: { label?: string; className?: string; children: ReactNode }) {
  return (
    <div className={className} role="status" aria-busy="true" aria-label={label}>
      {children}
    </div>
  );
}

/** Vài dòng chữ (đoạn văn, runbook, thông tin chi tiết). */
export function SkeletonText({ lines = 3, label }: { lines?: number; label?: string }) {
  return (
    <Busy label={label} className="skeleton-text">
      {Array.from({ length: lines }, (_, i) => <Skeleton key={i} width={i === lines - 1 ? "60%" : "100%"} />)}
    </Busy>
  );
}

/** Bảng: hàng tiêu đề + vài hàng dữ liệu, đúng số cột để không nhảy bố cục. */
export function SkeletonTable({ rows = 4, cols = 4, label }: { rows?: number; cols?: number; label?: string }) {
  return (
    <Busy label={label} className="skeleton-table">
      {Array.from({ length: rows + 1 }, (_, r) => (
        <div className={`skeleton-row${r === 0 ? " head" : ""}`} key={r}
             style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}>
          {Array.from({ length: cols }, (_, c) => (
            <Skeleton key={c} height={r === 0 ? 10 : 12} width={`${55 + ((r * 7 + c * 13) % 40)}%`} />
          ))}
        </div>
      ))}
    </Busy>
  );
}

/** Biểu đồ: khung đúng chiều cao biểu đồ (.chart 200 px). */
export function SkeletonChart({ height = 200, label }: { height?: number; label?: string }) {
  return (
    <Busy label={label} className="skeleton-chart">
      <Skeleton height={height} radius={8} width="100%" />
    </Busy>
  );
}
