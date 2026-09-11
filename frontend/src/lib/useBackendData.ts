import { useCallback, useEffect, useState } from 'react';
import { ApiResponse } from './api/client';

/**
 * Wraps one safeFetch call and, crucially, keeps its isFallback flag.
 *
 * safeFetch resolves successfully with mock data when the backend is
 * unreachable. Every page that ignored that flag rendered demo rows that look
 * exactly like real ones — the single most misleading thing about this
 * dashboard. Pages use `isMock` here to say so on screen.
 */
export function useBackendData<T>(
  fetcher: () => Promise<ApiResponse<T>>,
  initial: T,
  deps: unknown[] = []
) {
  const [data, setData] = useState<T>(initial);
  const [isMock, setIsMock] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    const res = await fetcher();
    if (res.data !== null) setData(res.data);
    setIsMock(res.isFallback);
    setError(res.error);
    setLoading(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const res = await fetcher();
      if (cancelled) return;
      if (res.data !== null) setData(res.data);
      setIsMock(res.isFallback);
      setError(res.error);
      setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, setData, isMock, loading, error, reload };
}
