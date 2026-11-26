// Điểm khởi động: nạp font Inter (đóng gói kèm, không cần Internet), bộ màu, rồi gắn ứng dụng vào index.html.
import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/inter/700.css";
import "./styles/tokens.css";
import "./styles/app.css";
import "./styles/incidents.css";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
