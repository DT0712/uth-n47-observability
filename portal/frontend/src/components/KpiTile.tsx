// Ô KPI pastel: icon nét mảnh, nhãn nhỏ, số to (kèm ghi chú nhỏ nếu có); bấm vào thì sang trang lọc sẵn.
import type { LucideIcon } from "lucide-react";
import { Link } from "react-router-dom";
import { Skeleton } from "./Skeleton";

export type Tone = "peach" | "lavender" | "pink" | "blue" | "mint";

export function KpiTile({ icon: Icon, label, value, tone, to, note, loading = false }: {
  icon: LucideIcon; label: string; value: string | number; tone: Tone; to?: string; note?: string; loading?: boolean;
}) {
  const aria = loading ? `${label}: đang tải` : `${label}: ${value}${note ? ` (${note})` : ""}`;
  const isText = typeof value === "string" && !/^[\d,.\s]+(s|%)?$/.test(value);
  const body = (
    <>
      <Icon size={26} strokeWidth={1.5} aria-hidden="true" />
      <div>
        <div className="label">{label}</div>
        {loading ? <Skeleton width={56} height={26} /> : (
          <div className={`value${isText ? " text" : ""}`}>{value}{note && <span className="note"> ({note})</span>}</div>
        )}
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
