// Thông báo nổi (toast) cho kết quả thao tác: xác nhận, đóng sự cố, chạy kịch bản, lưu quản trị...
// - Thành công: vùng aria-live="polite", tự ẩn sau 4 s. Lỗi: role="alert", giữ 8 s, có nút đóng.
// - Lỗi trong form vẫn hiện ngay tại form (người dùng cần sửa ở đó); toast chỉ báo kết quả chung.
import { CheckCircle2, Info, X, XCircle } from "lucide-react";
import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";

type Kind = "success" | "error" | "info";
interface Item { id: number; kind: Kind; text: string }
interface ToastApi {
  success: (text: string) => void;
  error: (text: string) => void;
  info: (text: string) => void;
}

const DURATION: Record<Kind, number> = { success: 4000, info: 5000, error: 8000 };
const MAX = 4;
const noop: ToastApi = { success: () => {}, error: () => {}, info: () => {} };
const Ctx = createContext<ToastApi>(noop);

export function useToast(): ToastApi {
  return useContext(Ctx);
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Item[]>([]);
  const seq = useRef(0);
  const dismiss = useCallback((id: number) => setItems((xs) => xs.filter((x) => x.id !== id)), []);
  const push = useCallback((kind: Kind, text: string) => {
    const id = ++seq.current;
    setItems((xs) => [...xs.filter((x) => x.text !== text), { id, kind, text }].slice(-MAX));
    window.setTimeout(() => dismiss(id), DURATION[kind]);
  }, [dismiss]);
  const api = useMemo<ToastApi>(() => ({
    success: (t) => push("success", t), error: (t) => push("error", t), info: (t) => push("info", t),
  }), [push]);

  const polite = items.filter((x) => x.kind !== "error");
  const urgent = items.filter((x) => x.kind === "error");
  return (
    <Ctx.Provider value={api}>
      {children}
      <div className="toast-stack">
        <div aria-live="polite" role="status" className="toast-region">
          {polite.map((t) => <ToastItem key={t.id} t={t} onClose={dismiss} />)}
        </div>
        <div aria-live="assertive" className="toast-region">
          {urgent.map((t) => <ToastItem key={t.id} t={t} onClose={dismiss} />)}
        </div>
      </div>
    </Ctx.Provider>
  );
}

const ICON = { success: CheckCircle2, error: XCircle, info: Info };

function ToastItem({ t, onClose }: { t: Item; onClose: (id: number) => void }) {
  const Icon = ICON[t.kind];
  return (
    <div className={`toast toast-${t.kind}`} role={t.kind === "error" ? "alert" : undefined}>
      <Icon size={18} aria-hidden="true" />
      <span className="toast-text">{t.text}</span>
      <button className="toast-close" aria-label="Đóng thông báo" onClick={() => onClose(t.id)}><X size={16} /></button>
    </div>
  );
}
