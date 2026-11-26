// Nhãn mức độ và trạng thái: luôn có chữ, không chỉ dựa vào màu (giao-dien.md mục 7).
import { SEVERITY_LABEL } from "../format";

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
