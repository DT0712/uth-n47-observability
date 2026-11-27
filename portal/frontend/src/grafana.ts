// Link và panel nhúng Grafana (FR-P05, FR-P06, ADR-0008). Backend trả link dashboard đã kèm biến (var-instance,
// var-service); ở đây chỉ đổi khoảng thời gian theo trang và dựng URL d-solo của từng panel.

/** Panel nhúng ở trang chi tiết, theo UID dashboard (monitor/grafana/dashboards/*.json). Chọn những panel portal
 *  không tự vẽ; dashboard không có trong bảng thì chỉ có nút "Mở Grafana". */
export const GRAFANA_PANELS: Record<string, { id: number; title: string }[]> = {
  "lab-host": [{ id: 9, title: "CPU theo mode" }, { id: 14, title: "Disk I/O" },
               { id: 18, title: "Dịch vụ systemd của lab" }],
  "lab-service": [{ id: 7, title: "Lịch sử UP/DOWN" }, { id: 9, title: "Request rate theo mã trạng thái" }],
  "lab-nginx": [{ id: 7, title: "Lịch sử UP/DOWN" }, { id: 9, title: "Trạng thái kết nối" }],
  "lab-postgres": [{ id: 7, title: "Lịch sử UP/DOWN" }, { id: 8, title: "Kết nối theo CSDL" }],
};

/** Link dashboard với khoảng thời gian `now-<range>` → `now` (thay from/to backend đặt sẵn). */
export function withRange(url: string, range: string): string {
  const u = new URL(url);
  u.searchParams.set("from", `now-${range}`);
  u.searchParams.set("to", "now");
  return u.toString();
}

export function dashboardUid(url: string): string | null {
  const m = new URL(url).pathname.match(/\/d\/([^/]+)/);
  return m ? m[1] : null;
}

/** URL d-solo của một panel: cùng biến với link dashboard, khoảng thời gian theo trang, tự làm mới mỗi phút. */
export function soloUrl(url: string, panelId: number, range: string): string {
  const u = new URL(withRange(url, range));
  u.pathname = u.pathname.replace(/\/d\//, "/d-solo/");
  u.searchParams.set("orgId", "1");
  u.searchParams.set("panelId", String(panelId));
  u.searchParams.set("refresh", "1m");
  u.searchParams.set("theme", "light");
  return u.toString();
}
