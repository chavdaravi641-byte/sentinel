"use client";

import { useEffect, useRef, useState } from "react";
import type {
  CameraInferenceStats,
  InferenceAlertItem,
  InferenceOverlay,
} from "@sentinel/shared";
import { INFERENCE_WS_PATH } from "@sentinel/shared";

import { tokenStore } from "./token-store";

export interface InferenceSocket {
  connected: boolean;
  overlays: Record<string, InferenceOverlay>;
  stats: Record<string, CameraInferenceStats>;
  alerts: InferenceAlertItem[];
  error: string | null;
}

function wsUrl(token: string): string {
  // Use NEXT_PUBLIC_API_URL if set, otherwise derive from current host.
  // This respects next.config.ts proxy and avoids hardcoding :8000 behind reverse proxy.
  const apiUrl = (typeof process !== "undefined" && (process.env as Record<string, string | undefined>).NEXT_PUBLIC_API_URL)
    ? (process.env as Record<string, string>).NEXT_PUBLIC_API_URL
    : `${window.location.protocol}//${window.location.hostname}:8000`;
  const wsBase = apiUrl.replace(/^http/, "ws");
  return `${wsBase}${INFERENCE_WS_PATH}?token=${encodeURIComponent(token)}&channels=overlay,stats,alert`;
}

/**
 * Realtime inference event bus. Auto-reconnects with backoff; filters by a
 * single `cameraId` when provided, otherwise aggregates every camera.
 */
export function useInferenceSocket(
  enabled: boolean,
  cameraId?: string | null,
): InferenceSocket {
  const [state, setState] = useState<InferenceSocket>({
    connected: false,
    overlays: {},
    stats: {},
    alerts: [],
    error: null,
  });
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!enabled) return;
    const token = tokenStore.get();
    if (!token) {
      const timer = setTimeout(
        () => setState((s) => ({ ...s, error: "No session token." })),
        0,
      );
      return () => clearTimeout(timer);
    }
    let closed = false;
    let retry: ReturnType<typeof setTimeout>;

    const connect = () => {
      if (closed) return;
      let ws: WebSocket;
      try {
        ws = new WebSocket(wsUrl(token));
      } catch {
        setState((s) => ({ ...s, error: "WebSocket unavailable." }));
        return;
      }
      wsRef.current = ws;
      ws.onopen = () =>
        setState((s) => ({ ...s, connected: true, error: null }));
      ws.onmessage = (event) => {
        let msg: Record<string, unknown>;
        try {
          msg = JSON.parse(event.data) as Record<string, unknown>;
        } catch {
          return;
        }
        if (!msg || typeof msg.type !== "string") return;
        if (cameraId && msg.camera_id && msg.camera_id !== cameraId) return;
        switch (msg.type) {
          case "overlay":
            setState((s) => ({
              ...s,
              overlays: { ...s.overlays, [String(msg.camera_id)]: msg as unknown as InferenceOverlay },
            }));
            break;
          case "stats":
            setState((s) => ({
              ...s,
              stats: { ...s.stats, [String(msg.camera_id)]: msg as unknown as CameraInferenceStats },
            }));
            break;
          case "alert":
            setState((s) => ({
              ...s,
              alerts: [msg as unknown as InferenceAlertItem, ...s.alerts].slice(0, 40),
            }));
            break;
          default:
            break;
        }
      };
      ws.onclose = () => {
        setState((s) => ({ ...s, connected: false }));
        if (!closed) retry = setTimeout(connect, 2000);
      };
      ws.onerror = () =>
        setState((s) => ({ ...s, error: "Inference socket error." }));
    };

    connect();
    return () => {
      closed = true;
      clearTimeout(retry);
      wsRef.current?.close();
    };
  }, [enabled, cameraId]);

  return state;
}