import { Link, useLocation } from "react-router-dom";
import { StatusPanel } from "../components/StatusPanel";

export function NotFoundPage() {
  const { pathname } = useLocation();
  return (
    <div className="page">
      <StatusPanel code="404" title="Không có trang này"
                   actions={<>
                     <Link className="btn btn-dark" to="/tong-quan">Về Tổng quan</Link>
                     <Link className="btn" to="/su-co">Xem sự cố</Link>
                   </>}>
        Đường dẫn <code>{pathname}</code> không tồn tại. Có thể link đã cũ hoặc gõ nhầm.
      </StatusPanel>
    </div>
  );
}
