import { useCallback, useEffect, useState } from "react";
import type { DependencyList } from "react";

export function useAsync<T>(fn: () => Promise<T>, deps: DependencyList = []) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const execute = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const value = await fn();
      setData(value);
      return value;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
      throw err;
    } finally {
      setLoading(false);
    }
  }, deps);

  useEffect(() => {
    execute().catch(() => undefined);
  }, [execute]);

  return { data, loading, error, refresh: execute, setData };
}
