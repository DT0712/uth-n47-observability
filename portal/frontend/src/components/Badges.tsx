// Nhãn mức độ và trạng thái: luôn có chữ, không chỉ dựa vào màu (giao-dien.md mục 7).
import { SEVERITY_LABEL, STATUS_LABEL } from "../format";

export function SeverityBadge({ severity }: { severity: string }) {
  return <span className={`badge ${severity}`}>{SEVERITY_LABEL[severity] ?? severity}</span>;
}

export function StatusBadge({ up }: { up: boolean | null }) {
  if (up === null) return <span className="badge unknown">Không rõ</span>;
  return <span className={`badge ${up ? "up" : "down"}`}>{up ? "UP" : "DOWN"}</span>;
}

export function StatusDot({ up, label }: { up: boolean | null; label?: string }) {
  const cls = up === null ? "unknown" : up ? "up" : "down";
  const text = label ?? (up === null ? "Không rõ" : up ? "Online" : "DOWN");
  return (
    <span>
      <span className={`dot ${cls}`} aria-hidden="true" />
      {text}
    </span>
  );
}

/** Sự cố thử nghiệm (BR-09): cảnh báo do kịch bản lỗi gây ra, là phát hiện đúng, không phải báo giả. */
export function TestBadge({ runId, inline }: { runId: number | null; inline?: boolean }) {
  if (runId === null) return null;
  return <span className="badge-sm st-test" style={inline ? { marginLeft: 6 } : undefined}
               title={`Do kịch bản lỗi #${runId} gây ra`}>thử nghiệm</span>;
}

/** Trạng thái xử lý sự cố: badge nhỏ nền nhạt; kèm nhãn "firing" nếu còn cảnh báo đang bắn. */
export function IncidentStatusBadge({ status, firing }: { status: string; firing?: boolean }) {
  return (
    <span className="status-badges">
      <span className={`badge-sm st-${status}`}>{STATUS_LABEL[status] ?? status}</span>
      {firing && <span className="badge-sm st-firing">firing</span>}
    </span>
  );
}
