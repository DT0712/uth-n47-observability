// Hộp thoại nhập lý do / kết luận (báo giả, đóng sự cố). Esc hoặc bấm nền để hủy.
import { useEffect, useRef, useState, type FormEvent } from "react";

export interface DialogProps {
  title: string;
  label: string;
  hint?: string;
  submitLabel: string;
  minLength: number;
  onSubmit: (text: string) => Promise<void>;
  onClose: () => void;
}

export function TextDialog({ title, label, hint, submitLabel, minLength, onSubmit, onClose }: DialogProps) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    ref.current?.focus();
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
      await onSubmit(text.trim());
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thực hiện được");
      setBusy(false);
    }
  }

  const tooShort = text.trim().length < minLength;
  return (
    <div className="dialog-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <form className="dialog" role="dialog" aria-modal="true" aria-label={title} onSubmit={submit}>
        <h2>{title}</h2>
        <div className="field">
          <label htmlFor="dialog-text">{label}</label>
          <textarea id="dialog-text" ref={ref} rows={4} value={text} onChange={(e) => setText(e.target.value)} maxLength={5000} />
          {hint && <small className="muted">{hint}</small>}
        </div>
        {error && <p className="form-error" role="alert">{error}</p>}
        <div className="dialog-actions">
          <button type="button" className="btn" onClick={onClose}>Hủy</button>
          <button type="submit" className="btn btn-dark" disabled={busy || tooShort}>{busy ? "Đang lưu…" : submitLabel}</button>
        </div>
      </form>
    </div>
  );
}
