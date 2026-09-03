"use client";

import { useCallback, useEffect, useState } from "react";

import { bootstrapIam, getIamMeta, iamFetch, type IamMeta } from "./iam";

interface IamListState<T> {
  data: T[] | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

/** Fetch a list endpoint and expose loading/error/refetch. */
export function useIamList<T>(path: string): IamListState<T> {
  const [data, setData] = useState<T[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    iamFetch<T[]>(path)
      .then((items) => {
        if (!cancelled) {
          setData(Array.isArray(items) ? items : []);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Load failed.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [path, tick]);

  const refetch = useCallback(() => setTick((t) => t + 1), []);
  return { data, loading, error, refetch };
}

/** Ensure the IAM session is bootstrapped and return the principal metadata. */
export function useIamPrincipal(): {
  meta: IamMeta | null;
  connected: boolean;
  connecting: boolean;
  connect: () => Promise<void>;
} {
  const [meta, setMeta] = useState<IamMeta | null>(() => getIamMeta());
  const [connecting, setConnecting] = useState(false);

  const connect = useCallback(async () => {
    setConnecting(true);
    try {
      const m = await bootstrapIam();
      setMeta(m);
    } finally {
      setConnecting(false);
    }
  }, []);

  return { meta, connected: Boolean(meta), connecting, connect };
}
