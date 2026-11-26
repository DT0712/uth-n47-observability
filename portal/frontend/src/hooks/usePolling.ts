// Gọi lại một hàm lấy dữ liệu mỗi `intervalMs` (mặc định 15 s = chu kỳ scrape) và khi `deps` đổi.
import { useCallback, useEffect, useRef, useState } from "react";

export interface Polled<T> {
  data: T | null;
  error: Error | null;
  loading: boolean;
  refresh: () => void;
}

export function usePolling<T>(fetcher: () => Promise<T>, deps: unknown[], intervalMs = 15000): Polled<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(true);
  const fetchRef = useRef(fetcher);
  fetchRef.current = fetcher;
  const seq = useRef(0);

  const run = useCallback(() => {
    const id = ++seq.current;
    fetchRef
      .current()
      .then((d) => {
        if (id === seq.current) {
          setData(d);
          setError(null);
        }
      })
      .catch((e: Error) => id === seq.current && setError(e))
      .finally(() => id === seq.current && setLoading(false));
  }, []);

  useEffect(() => {
    setLoading(true);
    run();
    const t = window.setInterval(run, intervalMs);
    return () => window.clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, intervalMs, run]);

  return { data, error, loading, refresh: run };
}
