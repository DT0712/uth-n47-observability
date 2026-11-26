// Ô KPI pastel: icon nét mảnh, nhãn nhỏ, số to (kèm ghi chú nhỏ nếu có); bấm vào thì sang trang lọc sẵn.
import type { LucideIcon } from "lucide-react";
import { Link } from "react-router-dom";

export type Tone = "peach" | "lavender" | "pink" | "blue" | "mint";

export function KpiTile({ icon: Icon, label, value, tone, to, note }: {
  icon: LucideIcon; label: string; value: string | number; tone: Tone; to?: string; note?: string;
}) {
  const aria = `${label}: ${value}${note ? ` (${note})` : ""}`;
  const isText = typeof value === "string" && !/^[\d,.\s]+(s|%)?$/.test(value);
  const body = (
    <>
      <Icon size={26} strokeWidth={1.5} aria-hidden="true" />
      <div>
        <div className="label">{label}</div>
        <div className={`value${isText ? " text" : ""}`}>{value}{note && <span className="note"> ({note})</span>}</div>
      </div>
    </>
  );
  return to ? (
    <Link className={`kpi ${tone}`} to={to} aria-label={aria}>
      {body}
    </Link>
  ) : (
    <div className={`kpi ${tone}`} aria-label={aria}>
      {body}
    </div>
  );
}
