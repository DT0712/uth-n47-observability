export function Pagination({ page, pageSize, total, onPage }: { page: number; pageSize: number; total: number; onPage: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  if (total === 0) return null;
  const from = (page - 1) * pageSize + 1;
  const to = Math.min(total, page * pageSize);
  return (
    <nav className="pagination" aria-label="Phân trang">
      <span className="muted">{from}–{to} / {total}</span>
      <button className="btn" disabled={page <= 1} onClick={() => onPage(page - 1)}>‹ Trước</button>
      <span>Trang {page}/{pages}</span>
      <button className="btn" disabled={page >= pages} onClick={() => onPage(page + 1)}>Sau ›</button>
    </nav>
  );
}
