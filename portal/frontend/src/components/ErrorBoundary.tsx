// Bắt lỗi khi vẽ giao diện: thay vì trắng cả trang, hiện thông báo và cho tải lại. Đặt quanh nội dung từng trang
// (resetKey = đường dẫn, đổi trang là tự thử vẽ lại) và quanh toàn ứng dụng (lưới an toàn cuối cùng).
import { Component, type ErrorInfo, type ReactNode } from "react";
import { StatusPanel } from "./StatusPanel";

interface Props { children: ReactNode; resetKey?: string }
interface State { error: Error | null }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Lỗi giao diện:", error, info.componentStack);
  }

  componentDidUpdate(prev: Props) {
    if (this.state.error && prev.resetKey !== this.props.resetKey) this.setState({ error: null });
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="page">
        <StatusPanel title="Trang gặp lỗi khi hiển thị"
                     actions={<>
                       <button className="btn btn-dark" onClick={() => window.location.reload()}>Tải lại trang</button>
                       <a className="btn" href="/tong-quan">Về Tổng quan</a>
                     </>}>
          Dữ liệu vẫn an toàn; chỉ phần hiển thị bị lỗi. Tải lại trang hoặc quay về Tổng quan.
          <span className="status-detail">Chi tiết: {this.state.error.message}</span>
        </StatusPanel>
      </div>
    );
  }
}
