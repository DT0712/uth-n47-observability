// Đổi mật khẩu của chính mình (POST /api/auth/password). Mở từ menu người dùng ở góc phải.
import { useState, type FormEvent } from "react";
import { ApiError } from "../api/client";
import * as ep from "../api/endpoints";
import { Card } from "../components/Card";

export function ChangePasswordPage() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setDone(false);
    if (next.length < 8) return setError("Mật khẩu mới phải có ít nhất 8 ký tự.");
    if (next !== confirm) return setError("Hai lần nhập mật khẩu mới không khớp.");
    if (next === current) return setError("Mật khẩu mới phải khác mật khẩu hiện tại.");
    setBusy(true);
    try {
      await ep.changePassword(current, next);
      setDone(true);
      setCurrent("");
      setNext("");
      setConfirm("");
    } catch (err) {
      const d = err instanceof ApiError ? (err.details as { message?: string }[] | undefined) : undefined;
      setError(d?.[0]?.message ?? (err instanceof Error ? err.message : "Không đổi được mật khẩu"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page">
      <div className="toolbar"><div className="breadcrumb"><strong>Đổi mật khẩu</strong></div></div>
      <div style={{ maxWidth: 460 }}>
        <Card title="Đổi mật khẩu" sub="Phiên đăng nhập hiện tại vẫn giữ; lần đăng nhập sau dùng mật khẩu mới.">
          <form onSubmit={submit} aria-label="Đổi mật khẩu">
            <div className="field"><label htmlFor="p-cur">Mật khẩu hiện tại</label>
              <input id="p-cur" type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} required /></div>
            <div className="field"><label htmlFor="p-new">Mật khẩu mới (ít nhất 8 ký tự)</label>
              <input id="p-new" type="password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} required /></div>
            <div className="field"><label htmlFor="p-confirm">Nhập lại mật khẩu mới</label>
              <input id="p-confirm" type="password" autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} required /></div>
            {error && <p className="form-error" role="alert">{error}</p>}
            {done && <p className="notice info" role="status">Đã đổi mật khẩu.</p>}
            <button className="btn btn-dark" type="submit" disabled={busy}>{busy ? "Đang lưu…" : "Đổi mật khẩu"}</button>
          </form>
        </Card>
      </div>
    </div>
  );
}
