"use client";

import { useEffect, useRef, useState } from "react";
import { ANPR_WS_PATH } from "@sentinel/shared";

import { tokenStore } from "./token-store";

export interface AnprPlateData {
  camera_id: string;
  plate: string;
  normalized_plate: string;
  ocr_confidence: number;
  detection_confidence: number;
  state_code: string | null;
  rto_code: string | null;
  vehicle: {
    vehicle_type: string;
    color: string;
    make: string;
    model: string;
    confidence: number;
  };
  ts: string;
}

export interface AnprPlateEvent {
  type: "plate";
  camera_id: string;
  frame_seq: number;
  ts: string;
  plates: AnprPlateData[];
}

export interface AnprSocket {
  connected: boolean;
  lastEvent: AnprPlateEvent | null;
  error: string | null;
}

function wsUrl(token: string): string {
  const apiUrl = (typeof process !== "undefined" && (process.env as Record<string, string | undefined>).NEXT_PUBLIC_API_URL)
    ? (process.env as Record<string, string>).NEXT_PUBLIC_API_URL
    : `${window.location.protocol}//${window.location.hostname}:8000`;
  const wsBase = apiUrl.replace(/^http/, "ws");
  return `${wsBase}${ANPR_WS_PATH}?token=${encodeURIComponent(token)}`;
}

export function useAnprSocket(enabled: boolean): AnprSocket {
  const [state, setState] = useState<AnprSocket>({
    connected: false,
    lastEvent: null,
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
        if (msg.type === "plate") {
          setState((s) => ({
            ...s,
            lastEvent: msg as unknown as AnprPlateEvent,
          }));
        }
      };
      ws.onclose = () => {
        setState((s) => ({ ...s, connected: false }));
        if (!closed) retry = setTimeout(connect, 2000);
      };
      ws.onerror = () =>
        setState((s) => ({ ...s, error: "ANPR socket error." }));
    };

    connect();
    return () => {
      closed = true;
      clearTimeout(retry);
      wsRef.current?.close();
    };
  }, [enabled]);

  return state;
}
