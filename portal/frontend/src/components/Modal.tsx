// Hộp thoại có form tùy ý (thêm/sửa máy, dịch vụ, người dùng). Esc hoặc bấm nền để hủy.
import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { ApiError } from "../api/client";

export function FormModal({ title, submitLabel, onSubmit, onClose, children }: {
  title: string; submitLabel: string; onSubmit: () => Promise<void>; onClose: () => void; children: ReactNode;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await onSubmit();
      onClose();
    } catch (err) {
      if (err instanceof ApiError && err.details?.length) {
        const d = err.details as { field?: string; message?: string }[];
        setError(`${err.message}: ${d.map((x) => `${x.field ?? ""} ${x.message ?? ""}`.trim()).join("; ")}`);
      } else {
        setError(err instanceof Error ? err.message : "Không lưu được");
      }
      setBusy(false);
    }
  }

  return (
    <div className="dialog-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <form className="dialog form-dialog" role="dialog" aria-modal="true" aria-label={title} onSubmit={submit}>
        <h2>{title}</h2>
        {children}
        {error && <p className="form-error" role="alert">{error}</p>}
        <div className="dialog-actions">
          <button type="button" className="btn" onClick={onClose}>Hủy</button>
          <button type="submit" className="btn btn-dark" disabled={busy}>{busy ? "Đang lưu…" : submitLabel}</button>
        </div>
      </form>
    </div>
  );
}

export function Field({ id, label, hint, children }: { id: string; label: string; hint?: string; children: ReactNode }) {
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {children}
      {hint && <small className="muted">{hint}</small>}
    </div>
  );
}
