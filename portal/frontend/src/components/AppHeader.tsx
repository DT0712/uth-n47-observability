// Thanh menu ngang: tên portal, các mục (mục đang chọn là nút viên thuốc), ô người dùng ở góc phải.
import { Presentation } from "lucide-react";
import { useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { setPresent, usePresent } from "../display";
import { Brand } from "./Logo";

const ITEMS = [
  { to: "/tong-quan", label: "Tổng quan" },
  { to: "/may-dich-vu", label: "Máy & dịch vụ" },
  { to: "/su-co", label: "Sự cố" },
  { to: "/runbook", label: "Runbook" },
  { to: "/kich-ban-loi", label: "Kịch bản lỗi" },
  { to: "/nguong", label: "Ngưỡng" },
  { to: "/quan-tri", label: "Quản trị", admin: true },
];

export function AppHeader() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const initials = (user?.username ?? "?").slice(0, 2).toUpperCase();
  const present = usePresent();
  return (
    <header className="app-header">
      <NavLink to="/tong-quan" className="brand-link" aria-label="Obslab Portal, về Tổng quan"><Brand /></NavLink>
      <nav className="nav" aria-label="Menu chính">
        {ITEMS.filter((i) => !i.admin || user?.role === "admin").map((i) => (
          <NavLink key={i.to} to={i.to} className={({ isActive }) => (isActive ? "active" : undefined)}>
            {i.label}
          </NavLink>
        ))}
      </nav>
      <button className={`icon-btn present-toggle${present ? " on" : ""}`} aria-pressed={present}
              title={present ? "Tắt chế độ Trình chiếu" : "Bật chế độ Trình chiếu: chữ to, tương phản cao cho máy chiếu"}
              onClick={() => setPresent(!present)}>
        <Presentation size={18} aria-hidden="true" />
        <span>Trình chiếu</span>
      </button>
      <div className="user-menu">
        <button className="avatar" aria-label="Tài khoản" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
          {initials}
        </button>
        {open && (
          <div className="user-dropdown" role="menu">
            <div className="who">
              <b>{user?.username}</b>
              <small>{user?.role === "admin" ? "Quản trị viên" : "Vận hành"}</small>
            </div>
            <button role="menuitem" onClick={() => { setOpen(false); navigate("/doi-mat-khau"); }}>
              Đổi mật khẩu
            </button>
            <button role="menuitem" onClick={() => void logout()}>
              Đăng xuất
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
