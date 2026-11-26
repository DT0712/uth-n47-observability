// Hàm gọi API chung: gắn token, đổi lỗi JSON {"error": {code, message}} thành ApiError có thông báo tiếng Việt.

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public details?: unknown[]) {
    super(message);
  }
}

let token: string | null = null;
let onUnauthorized: (() => void) | null = null;

/** AuthContext gọi hàm này khi đăng nhập/đăng xuất. */
export function setToken(value: string | null): void {
  token = value;
}

/** Được gọi khi backend trả 401 (hết hạn, bị khóa) để đưa người dùng về trang đăng nhập. */
export function setUnauthorizedHandler(handler: (() => void) | null): void {
  onUnauthorized = handler;
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let res: Response;
  try {
    res = await fetch(path, { ...init, headers });
  } catch {
    throw new ApiError(0, "network_error", "Không kết nối được tới máy chủ portal");
  }
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const err = body?.error ?? {};
    if (res.status === 401 && token && onUnauthorized) onUnauthorized();
    throw new ApiError(res.status, err.code ?? "http_error", err.message ?? `Lỗi ${res.status}`, err.details);
  }
  return body as T;
}

/** Tạo query string, bỏ tham số rỗng. */
export function qs(params: Record<string, string | number | boolean | null | undefined>): string {
  const s = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== null && v !== undefined && v !== "") s.set(k, String(v));
  const out = s.toString();
  return out ? `?${out}` : "";
}
