// Ô KPI pastel: icon nét mảnh, nhãn nhỏ, số to; bấm vào thì sang trang lọc sẵn.
import type { LucideIcon } from "lucide-react";
import { Link } from "react-router-dom";

export type Tone = "peach" | "lavender" | "pink" | "blue" | "mint";

export function KpiTile({ icon: Icon, label, value, tone, to }: { icon: LucideIcon; label: string; value: string | number; tone: Tone; to?: string }) {
  const isText = typeof value === "string" && !/^[\d,.\s]+(s|%)?$/.test(value);
  const body = (
    <>
      <Icon size={26} strokeWidth={1.5} aria-hidden="true" />
      <div>
        <div className="label">{label}</div>
        <div className={`value${isText ? " text" : ""}`}>{value}</div>
      </div>
    </>
  );
  return to ? (
    <Link className={`kpi ${tone}`} to={to} aria-label={`${label}: ${value}`}>
      {body}
    </Link>
  ) : (
    <div className={`kpi ${tone}`} aria-label={`${label}: ${value}`}>
      {body}
    </div>
  );
}
