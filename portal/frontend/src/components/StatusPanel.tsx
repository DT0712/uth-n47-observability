// Khối thông báo lớn giữa trang: 404, lỗi giao diện, không tìm thấy đối tượng. Dùng chung để mọi trang lỗi trông giống nhau.
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../api/client";

export function StatusPanel({ code, title, children, actions }: {
  code?: string; title: string; children?: ReactNode; actions?: ReactNode;
}) {
  return (
    <div className="status-panel" role="alert">
      {code && <div className="status-code" aria-hidden="true">{code}</div>}
      <h1>{title}</h1>
      {children && <p className="muted">{children}</p>}
      {actions && <div className="actions">{actions}</div>}
    </div>
  );
}

/** Trang chi tiết tải không được: 404 thì báo không tìm thấy, lỗi khác thì hiện thông báo của backend. */
export function LoadFailed({ error, what, back, backLabel }: {
  error: unknown; what: string; back: string; backLabel: string;
}) {
  const notFound = error instanceof ApiError && error.status === 404;
  return (
    <StatusPanel code={notFound ? "404" : undefined} title={notFound ? `Không tìm thấy ${what}` : `Không tải được ${what}`}
                 actions={<Link className="btn btn-dark" to={back}>{backLabel}</Link>}>
      {notFound ? `${what[0].toUpperCase()}${what.slice(1)} này không tồn tại hoặc đã bị xóa.`
                : error instanceof Error ? error.message : "Lỗi không xác định"}
    </StatusPanel>
  );
}
