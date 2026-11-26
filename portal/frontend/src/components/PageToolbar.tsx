// Dưới menu: breadcrumb, nút làm mới, ô chọn khoảng thời gian; hàng chip lọc máy/dịch vụ.
// Bộ lọc nằm trên URL (?host=web&range=1h) để chia sẻ link và giữ khi tải lại trang.
import { RefreshCw, X } from "lucide-react";
import type { OverviewHost } from "../types";

export interface ToolbarProps {
  crumbs: string[];
  range: string;
  onRange: (r: string) => void;
  onRefresh: () => void;
  hosts: OverviewHost[];
  host?: string;
  service?: string;
  onFilter: (f: { host?: string; service?: string }) => void;
}

export function PageToolbar({ crumbs, range, onRange, onRefresh, hosts, host, service, onFilter }: ToolbarProps) {
  const services = [...new Set(hosts.flatMap((h) => h.services.map((s) => s.name)))].sort();
  return (
    <>
      <div className="toolbar">
        <div className="breadcrumb">
          {crumbs.slice(0, -1).map((c) => `${c} › `)}
          <strong>{crumbs[crumbs.length - 1]}</strong>
        </div>
        <div className="spacer" />
        <button className="icon-btn" onClick={onRefresh} aria-label="Làm mới">
          <RefreshCw size={16} strokeWidth={1.5} />
        </button>
        <select className="range-select" value={range} onChange={(e) => onRange(e.target.value)} aria-label="Khoảng thời gian">
          <option value="1h">1 giờ</option>
          <option value="6h">6 giờ</option>
          <option value="24h">24 giờ</option>
        </select>
      </div>
      <div className="chips" aria-label="Bộ lọc">
        {host && (
          <button className="chip" onClick={() => onFilter({ service })} aria-label={`Bỏ lọc máy ${host}`}>
            Máy: <b>{host}</b> <X size={14} />
          </button>
        )}
        {service && (
          <button className="chip" onClick={() => onFilter({ host })} aria-label={`Bỏ lọc dịch vụ ${service}`}>
            Dịch vụ: <b>{service}</b> <X size={14} />
          </button>
        )}
        {!host && (
          <label className="chip add">
            + Máy
            <select value="" onChange={(e) => onFilter({ host: e.target.value, service })} aria-label="Lọc theo máy">
              <option value="" />
              {hosts.map((h) => <option key={h.id} value={h.name}>{h.name}</option>)}
            </select>
          </label>
        )}
        {!service && (
          <label className="chip add">
            + Dịch vụ
            <select value="" onChange={(e) => onFilter({ host, service: e.target.value })} aria-label="Lọc theo dịch vụ">
              <option value="" />
              {services.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>
        )}
      </div>
    </>
  );
}
