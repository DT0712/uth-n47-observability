// Hiển thị runbook (Markdown). react-markdown không chạy HTML nhúng nên an toàn với nội dung từ file.
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Runbook } from "../types";

export function RunbookView({ runbook }: { runbook: Runbook }) {
  return (
    <article className="markdown" aria-label={`Runbook ${runbook.alertname}`}>
      <div className="runbook-meta">
        <span className={`badge-sm ${runbook.status === "reviewed" ? "st-closed" : "st-acknowledged"}`}>
          {runbook.status === "reviewed" ? "Đã duyệt" : "Bản nháp"}
        </span>
        <span className="muted">{runbook.source_path}</span>
      </div>
      {/* Hạ cấp tiêu đề: trang đã có h1 riêng, runbook không được thêm h1 thứ hai */}
      <Markdown remarkPlugins={[remarkGfm]} components={{ h1: "h3", h2: "h4", h3: "h5" }}>{runbook.body_md}</Markdown>
    </article>
  );
}
