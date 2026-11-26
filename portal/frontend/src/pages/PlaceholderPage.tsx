// Trang chưa làm (các phần sau của GĐ6).
import { Card } from "../components/Card";

export function PlaceholderPage({ title }: { title: string }) {
  return (
    <div className="page">
      <div className="toolbar"><div className="breadcrumb"><strong>{title}</strong></div></div>
      <Card title={title}><p className="muted">Trang này sẽ làm ở phần sau của GĐ6.</p></Card>
    </div>
  );
}
