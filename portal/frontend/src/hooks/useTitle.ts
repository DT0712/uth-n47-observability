// Tiêu đề tab theo trang: "Sự cố #12 NginxDown · Obslab Portal". Nhiều tab mở cùng lúc vẫn phân biệt được.
import { useEffect } from "react";

export const APP_NAME = "Obslab Portal";

export function useTitle(title: string | null | undefined) {
  useEffect(() => {
    document.title = title ? `${title} · ${APP_NAME}` : APP_NAME;
  }, [title]);
}
