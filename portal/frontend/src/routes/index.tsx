// Bảng đường dẫn -> màn hình. RequireAuth chặn người chưa đăng nhập; RequireRole ẩn trang admin với operator
// (chỉ để ẩn giao diện — quyền thật luôn được kiểm ở backend).
import type { ReactNode } from "react";
import { Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { AppHeader } from "../components/AppHeader";
import { LoginPage } from "../pages/LoginPage";
import { OverviewPage } from "../pages/OverviewPage";
import { PlaceholderPage } from "../pages/PlaceholderPage";
import type { Role } from "../types";

function RequireAuth() {
  const { user, ready } = useAuth();
  const location = useLocation();
  if (!ready) return <div className="page muted">Đang tải…</div>;
  if (!user) return <Navigate to="/dang-nhap" replace state={{ from: location.pathname + location.search }} />;
  return (
    <>
      <AppHeader />
      <Outlet />
    </>
  );
}

function RequireRole({ role, children }: { role: Role; children: ReactNode }) {
  const { user } = useAuth();
  return user?.role === role ? <>{children}</> : <Navigate to="/tong-quan" replace />;
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/dang-nhap" element={<LoginPage />} />
      <Route element={<RequireAuth />}>
        <Route path="/" element={<Navigate to="/tong-quan" replace />} />
        <Route path="/tong-quan" element={<OverviewPage />} />
        <Route path="/may-dich-vu" element={<PlaceholderPage title="Máy & dịch vụ" />} />
        <Route path="/su-co/*" element={<PlaceholderPage title="Sự cố" />} />
        <Route path="/runbook" element={<PlaceholderPage title="Runbook" />} />
        <Route path="/kich-ban-loi" element={<PlaceholderPage title="Kịch bản lỗi" />} />
        <Route path="/nguong" element={<PlaceholderPage title="Ngưỡng" />} />
        <Route path="/quan-tri" element={<RequireRole role="admin"><PlaceholderPage title="Quản trị" /></RequireRole>} />
        <Route path="*" element={<Navigate to="/tong-quan" replace />} />
      </Route>
    </Routes>
  );
}
