// Quản trị (chỉ admin; UC13, UC14, FR-P07, FR-P16, FR-P17): tab Máy & dịch vụ, Người dùng, Nhật ký thao tác.
// Tab nằm trên URL (?tab=nguoi-dung). Quy tắc (tự khóa, admin cuối, trùng tên…) do backend kiểm; giao diện hiện nguyên lỗi.
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import * as ep from "../api/endpoints";
import { useAuth } from "../auth/AuthContext";
import { Card, Empty, ErrorBox } from "../components/Card";
import { Field, FormModal } from "../components/Modal";
import { Pagination } from "../components/Pagination";
import { ago, dateTime } from "../format";
import { usePolling } from "../hooks/usePolling";
import type { HostDetail, ServiceDetail, User } from "../types";

const TABS = [
  { id: "may", label: "Máy & dịch vụ" },
  { id: "nguoi-dung", label: "Người dùng" },
  { id: "nhat-ky", label: "Nhật ký thao tác" },
];

export function AdminPage() {
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") ?? "may";
  return (
    <div className="page">
      <div className="toolbar"><div className="breadcrumb">Quản trị › <strong>{TABS.find((t) => t.id === tab)?.label}</strong></div></div>
      <div className="tabs" role="tablist" aria-label="Quản trị">
        {TABS.map((t) => (
          <button key={t.id} role="tab" aria-selected={tab === t.id} className={tab === t.id ? "active" : undefined}
                  onClick={() => setParams({ tab: t.id }, { replace: true })}>{t.label}</button>
        ))}
      </div>
      {tab === "may" && <InventoryTab />}
      {tab === "nguoi-dung" && <UsersTab />}
      {tab === "nhat-ky" && <AuditTab />}
    </div>
  );
}

// ------------------------------------------------------------------ máy & dịch vụ
type HostForm = { name: string; address: string; prom_instance: string; grafana_dashboard_uid: string; description: string; enabled: boolean };
type ServiceForm = { host_id: string; name: string; kind: string; labels: string; probe_instance: string; grafana_dashboard_uid: string; enabled: boolean };

const blankHost: HostForm = { name: "", address: "", prom_instance: "", grafana_dashboard_uid: "lab-host", description: "", enabled: true };
const orNull = (s: string) => (s.trim() === "" ? null : s.trim());

/** "job=nginx, service=nginx" <-> {job: "nginx", service: "nginx"} */
export function parseLabels(text: string): Record<string, string> {
  return Object.fromEntries(text.split(",").map((p) => p.trim()).filter(Boolean).map((p) => {
    const i = p.indexOf("=");
    return i < 0 ? [p, ""] : [p.slice(0, i).trim(), p.slice(i + 1).trim().replace(/^"|"$/g, "")];
  }));
}
const labelsText = (l: Record<string, string>) => Object.entries(l).map(([k, v]) => `${k}=${v}`).join(", ");

/** Chỉ gửi trường đã đổi (PATCH là sửa một phần). */
function changed<T extends Record<string, unknown>>(before: T, after: T): Partial<T> {
  return Object.fromEntries(Object.entries(after).filter(([k, v]) => JSON.stringify(v) !== JSON.stringify(before[k]))) as Partial<T>;
}

function InventoryTab() {
  const hosts = usePolling(() => ep.listHostsFull(), [], 60000);
  const [hostEdit, setHostEdit] = useState<HostDetail | "new" | null>(null);
  const [svcEdit, setSvcEdit] = useState<{ svc: ServiceDetail | null; hostId: number } | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function remove(kind: "host" | "service", id: number, name: string) {
    const msg = kind === "host" ? `Xóa máy "${name}" và mọi dịch vụ của nó khỏi portal? (Không ảnh hưởng Prometheus.)`
      : `Xóa dịch vụ "${name}" khỏi portal?`;
    if (!window.confirm(msg)) return;
    setError(null);
    try {
      await (kind === "host" ? ep.deleteHost(id) : ep.deleteService(id));
      hosts.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Không xóa được");
    }
  }

  return (
    <>
      <Card title="Máy & dịch vụ" sub="Danh mục đối tượng hiển thị trên portal và nhãn Prometheus tương ứng (không sửa cấu hình Prometheus)"
            actions={<button className="btn btn-dark" onClick={() => setHostEdit("new")}>Thêm máy</button>}>
        {error && <ErrorBox>{error}</ErrorBox>}
        {!hosts.data ? <Empty>Đang tải…</Empty> : hosts.data.length === 0 ? <Empty>Chưa có máy nào.</Empty> : (
          <table className="table">
            <thead><tr><th>Máy</th><th>Địa chỉ</th><th>Nhãn instance</th><th>Dịch vụ</th><th>Bật</th><th /></tr></thead>
            <tbody>
              {hosts.data.map((h) => (
                <tr key={h.id}>
                  <td><b>{h.name}</b><div className="muted">{h.description}</div></td>
                  <td>{h.address ?? "—"}</td>
                  <td><code>{h.prom_instance}</code></td>
                  <td>
                    <ul className="svc-list">
                      {h.services.map((s) => (
                        <li key={s.id}>
                          <span>{s.name} <span className="muted">({s.kind}{s.enabled ? "" : ", tắt"})</span></span>
                          <span className="actions">
                            <button className="btn btn-sm" onClick={() => setSvcEdit({ svc: s, hostId: h.id })}>Sửa</button>
                            <button className="btn btn-sm" onClick={() => void remove("service", s.id, s.name)}>Xóa</button>
                          </span>
                        </li>
                      ))}
                    </ul>
                    <button className="btn btn-sm" onClick={() => setSvcEdit({ svc: null, hostId: h.id })}>+ Dịch vụ</button>
                  </td>
                  <td>{h.enabled ? "Có" : "Không"}</td>
                  <td className="actions">
                    <button className="btn btn-sm" onClick={() => setHostEdit(h)}>Sửa</button>
                    <button className="btn btn-sm" onClick={() => void remove("host", h.id, h.name)}>Xóa</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
      {hostEdit && <HostModal host={hostEdit === "new" ? null : hostEdit} onClose={() => setHostEdit(null)} onSaved={hosts.refresh} />}
      {svcEdit && <ServiceModal svc={svcEdit.svc} hostId={svcEdit.hostId} hosts={hosts.data ?? []}
                                onClose={() => setSvcEdit(null)} onSaved={hosts.refresh} />}
    </>
  );
}

function HostModal({ host, onClose, onSaved }: { host: HostDetail | null; onClose: () => void; onSaved: () => void }) {
  const initial: HostForm = host ? { name: host.name, address: host.address ?? "", prom_instance: host.prom_instance,
    grafana_dashboard_uid: host.grafana_dashboard_uid ?? "", description: host.description ?? "", enabled: host.enabled } : blankHost;
  const [f, setF] = useState<HostForm>(initial);
  const set = (k: keyof HostForm, v: string | boolean) => setF({ ...f, [k]: v });
  const toBody = (x: HostForm) => ({ name: x.name.trim(), address: orNull(x.address), prom_instance: x.prom_instance.trim(),
    grafana_dashboard_uid: orNull(x.grafana_dashboard_uid), description: orNull(x.description), enabled: x.enabled });
  async function save() {
    if (host) await ep.updateHost(host.id, changed(toBody(initial), toBody(f)));
    else await ep.createHost(toBody(f));
    onSaved();
  }
  return (
    <FormModal title={host ? `Sửa máy ${host.name}` : "Thêm máy"} submitLabel={host ? "Lưu" : "Thêm"} onSubmit={save} onClose={onClose}>
      <Field id="h-name" label="Tên (chữ thường, số, -)"><input id="h-name" value={f.name} onChange={(e) => set("name", e.target.value)} required /></Field>
      <Field id="h-address" label="Địa chỉ"><input id="h-address" value={f.address} onChange={(e) => set("address", e.target.value)} /></Field>
      <Field id="h-inst" label="Nhãn instance của node exporter" hint="Khớp nhãn instance trong prometheus.yml, vd. web">
        <input id="h-inst" value={f.prom_instance} onChange={(e) => set("prom_instance", e.target.value)} required />
      </Field>
      <Field id="h-uid" label="UID dashboard Grafana"><input id="h-uid" value={f.grafana_dashboard_uid} onChange={(e) => set("grafana_dashboard_uid", e.target.value)} /></Field>
      <Field id="h-desc" label="Mô tả"><input id="h-desc" value={f.description} onChange={(e) => set("description", e.target.value)} /></Field>
      <label className="check"><input type="checkbox" checked={f.enabled} onChange={(e) => set("enabled", e.target.checked)} /> Hiển thị trên portal</label>
    </FormModal>
  );
}

function ServiceModal({ svc, hostId, hosts, onClose, onSaved }: {
  svc: ServiceDetail | null; hostId: number; hosts: HostDetail[]; onClose: () => void; onSaved: () => void;
}) {
  const initial: ServiceForm = svc ? { host_id: String(svc.host_id), name: svc.name, kind: svc.kind, labels: labelsText(svc.prom_labels),
    probe_instance: svc.probe_instance ?? "", grafana_dashboard_uid: svc.grafana_dashboard_uid ?? "", enabled: svc.enabled }
    : { host_id: String(hostId), name: "", kind: "app", labels: "job=", probe_instance: "", grafana_dashboard_uid: "", enabled: true };
  const [f, setF] = useState<ServiceForm>(initial);
  const set = (k: keyof ServiceForm, v: string | boolean) => setF({ ...f, [k]: v });
  const toBody = (x: ServiceForm) => ({ host_id: Number(x.host_id), name: x.name.trim(), kind: x.kind, prom_labels: parseLabels(x.labels),
    probe_instance: orNull(x.probe_instance), grafana_dashboard_uid: orNull(x.grafana_dashboard_uid), enabled: x.enabled });
  async function save() {
    if (svc) await ep.updateService(svc.id, changed(toBody(initial), toBody(f)));
    else await ep.createService(toBody(f));
    onSaved();
  }
  return (
    <FormModal title={svc ? `Sửa dịch vụ ${svc.name}` : "Thêm dịch vụ"} submitLabel={svc ? "Lưu" : "Thêm"} onSubmit={save} onClose={onClose}>
      <Field id="s-host" label="Máy">
        <select id="s-host" className="range-select" value={f.host_id} onChange={(e) => set("host_id", e.target.value)}>
          {hosts.map((h) => <option key={h.id} value={h.id}>{h.name}</option>)}
        </select>
      </Field>
      <Field id="s-name" label="Tên"><input id="s-name" value={f.name} onChange={(e) => set("name", e.target.value)} required /></Field>
      <Field id="s-kind" label="Loại">
        <select id="s-kind" className="range-select" value={f.kind} onChange={(e) => set("kind", e.target.value)}>
          <option value="web">web</option><option value="app">app</option><option value="database">database</option><option value="other">other</option>
        </select>
      </Field>
      <Field id="s-labels" label="Nhãn Prometheus" hint='Dạng job=nginx, service=nginx (chọn chuỗi "up" của dịch vụ)'>
        <input id="s-labels" value={f.labels} onChange={(e) => set("labels", e.target.value)} required />
      </Field>
      <Field id="s-probe" label="Instance của probe (tùy chọn)" hint="vd. web:80 hoặc http://web/health">
        <input id="s-probe" value={f.probe_instance} onChange={(e) => set("probe_instance", e.target.value)} />
      </Field>
      <Field id="s-uid" label="UID dashboard Grafana"><input id="s-uid" value={f.grafana_dashboard_uid} onChange={(e) => set("grafana_dashboard_uid", e.target.value)} /></Field>
      <label className="check"><input type="checkbox" checked={f.enabled} onChange={(e) => set("enabled", e.target.checked)} /> Hiển thị trên portal</label>
    </FormModal>
  );
}

// ------------------------------------------------------------------ người dùng
function UsersTab() {
  const { user: me } = useAuth();
  const users = usePolling(() => ep.listUsers(), [], 60000);
  const [creating, setCreating] = useState(false);
  const [resetFor, setResetFor] = useState<User | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function patch(u: User, body: { role?: string; is_active?: boolean }) {
    setError(null);
    try {
      await ep.updateUser(u.id, body);
      users.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Không lưu được");
    }
  }

  return (
    <>
      <Card title="Người dùng" sub="Admin có mọi quyền của operator, thêm quản trị và chạy kịch bản lỗi"
            actions={<button className="btn btn-dark" onClick={() => setCreating(true)}>Thêm người dùng</button>}>
        {error && <ErrorBox>{error}</ErrorBox>}
        {!users.data ? <Empty>Đang tải…</Empty> : (
          <table className="table">
            <thead><tr><th>Tên đăng nhập</th><th>Vai trò</th><th>Trạng thái</th><th>Đăng nhập gần nhất</th><th /></tr></thead>
            <tbody>
              {users.data.items.map((u) => {
                const self = u.id === me?.id;
                return (
                  <tr key={u.id}>
                    <td><b>{u.username}</b>{self && <span className="muted"> (bạn)</span>}</td>
                    <td><span className={`badge-sm ${u.role === "admin" ? "st-firing" : "st-closed"}`}>{u.role === "admin" ? "Quản trị viên" : "Vận hành"}</span></td>
                    <td><span className={`badge-sm ${u.is_active ? "st-closed" : "st-open"}`}>{u.is_active ? "Đang hoạt động" : "Đã khóa"}</span></td>
                    <td className="muted">{u.last_login_at ? ago(u.last_login_at) : "Chưa"}</td>
                    <td className="actions">
                      <button className="btn btn-sm" disabled={self} title={self ? "Không tự đổi vai trò của mình" : undefined}
                              onClick={() => void patch(u, { role: u.role === "admin" ? "operator" : "admin" })}>
                        {u.role === "admin" ? "Hạ xuống vận hành" : "Nâng lên quản trị"}
                      </button>
                      <button className="btn btn-sm" disabled={self} title={self ? "Không tự khóa mình" : undefined}
                              onClick={() => void patch(u, { is_active: !u.is_active })}>{u.is_active ? "Khóa" : "Mở khóa"}</button>
                      <button className="btn btn-sm" onClick={() => setResetFor(u)}>Đặt lại mật khẩu</button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </Card>
      {creating && <CreateUserModal onClose={() => setCreating(false)} onSaved={users.refresh} />}
      {resetFor && <ResetPasswordModal user={resetFor} onClose={() => setResetFor(null)} />}
    </>
  );
}

function CreateUserModal({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("operator");
  return (
    <FormModal title="Thêm người dùng" submitLabel="Thêm" onClose={onClose}
               onSubmit={async () => { await ep.createUser({ username: username.trim(), password, role }); onSaved(); }}>
      <Field id="u-name" label="Tên đăng nhập" hint="3–64 ký tự: chữ thường, số, _ . -">
        <input id="u-name" value={username} onChange={(e) => setUsername(e.target.value)} required />
      </Field>
      <Field id="u-pass" label="Mật khẩu (ít nhất 8 ký tự)">
        <input id="u-pass" type="password" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} />
      </Field>
      <Field id="u-role" label="Vai trò">
        <select id="u-role" className="range-select" value={role} onChange={(e) => setRole(e.target.value)}>
          <option value="operator">Vận hành (operator)</option>
          <option value="admin">Quản trị viên (admin)</option>
        </select>
      </Field>
    </FormModal>
  );
}

function ResetPasswordModal({ user, onClose }: { user: User; onClose: () => void }) {
  const [password, setPassword] = useState("");
  return (
    <FormModal title={`Đặt lại mật khẩu cho ${user.username}`} submitLabel="Đặt lại" onClose={onClose}
               onSubmit={async () => { await ep.updateUser(user.id, { password }); }}>
      <Field id="r-pass" label="Mật khẩu mới (ít nhất 8 ký tự)" hint="Báo cho người dùng qua kênh riêng; mật khẩu không được ghi vào nhật ký.">
        <input id="r-pass" type="password" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} />
      </Field>
    </FormModal>
  );
}

// ------------------------------------------------------------------ nhật ký thao tác
const ACTION_LABEL: Record<string, string> = {
  login: "Đăng nhập", login_failed: "Đăng nhập sai", logout: "Đăng xuất", password_change: "Đổi mật khẩu",
  create: "Tạo", update: "Sửa", delete: "Xóa", acknowledged: "Xác nhận sự cố", incident_note: "Ghi chú sự cố",
  false_positive: "Báo giả", closed: "Đóng sự cố", fault_start: "Chạy kịch bản lỗi", fault_stop: "Dừng kịch bản lỗi",
  runbooks_reload: "Nạp lại runbook",
};
const PAGE_SIZE = 50;

function AuditTab() {
  const [action, setAction] = useState("");
  const [userId, setUserId] = useState("");
  const [from, setFrom] = useState("");
  const [page, setPage] = useState(1);
  const users = usePolling(() => ep.listUsers(), [], 300000);
  const log = usePolling(() => ep.listAudit({
    action: action || undefined, user_id: userId ? Number(userId) : undefined,
    from: from ? new Date(from).toISOString() : undefined, page, page_size: PAGE_SIZE,
  }), [action, userId, from, page], 30000);
  return (
    <Card title="Nhật ký thao tác" sub="Mọi thao tác thay đổi dữ liệu, đăng nhập, chạy/dừng kịch bản lỗi">
      <div className="chips">
        <select className="filter-select" aria-label="Loại thao tác" value={action} onChange={(e) => { setAction(e.target.value); setPage(1); }}>
          <option value="">Mọi thao tác</option>
          {Object.entries(ACTION_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <select className="filter-select" aria-label="Người thực hiện" value={userId} onChange={(e) => { setUserId(e.target.value); setPage(1); }}>
          <option value="">Mọi người</option>
          {(users.data?.items ?? []).map((u) => <option key={u.id} value={u.id}>{u.username}</option>)}
        </select>
        <label className="check">Từ <input type="datetime-local" aria-label="Từ thời điểm" value={from} onChange={(e) => { setFrom(e.target.value); setPage(1); }} /></label>
      </div>
      {log.error && <ErrorBox>{log.error.message}</ErrorBox>}
      {log.data && log.data.items.length === 0 && <Empty>Không có mục nào.</Empty>}
      {log.data && log.data.items.length > 0 && (
        <table className="table">
          <thead><tr><th>Thời điểm</th><th>Người</th><th>Thao tác</th><th>Đối tượng</th><th>Chi tiết</th><th>IP</th></tr></thead>
          <tbody>
            {log.data.items.map((a) => (
              <tr key={a.id}>
                <td>{dateTime(a.at)}</td>
                <td>{a.user ?? "—"}</td>
                <td>{ACTION_LABEL[a.action] ?? a.action}</td>
                <td>{a.object_type ? `${a.object_type}${a.object_id ? ` #${a.object_id}` : ""}` : "—"}</td>
                <td className="muted"><code className="detail">{a.detail ? JSON.stringify(a.detail) : ""}</code></td>
                <td className="muted">{a.client_ip ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {log.data && <Pagination page={page} pageSize={PAGE_SIZE} total={log.data.total} onPage={setPage} />}
    </Card>
  );
}
