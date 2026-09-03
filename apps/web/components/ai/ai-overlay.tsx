"use client";

import { useEffect, useRef } from "react";
import type { DetectionBox, InferenceOverlay } from "@sentinel/shared";

import { LiveStreamPlayer } from "@/components/live/live-stream-player";
import { cn } from "@/lib/utils";

interface AiOverlayPaneProps {
  name: string;
  running?: boolean;
  hlsUrl?: string | null;
  mjpegUrl?: string | null;
  whepUrl?: string | null;
  fps?: number | null;
  state?: string;
  whep?: boolean;
  overlay?: InferenceOverlay | null;
  className?: string;
  showTrackIds?: boolean;
}

const CLASS_COLORS: Record<string, string> = {
  person: "#22d3ee", // cyan
  car: "#a78bfa", // violet
  bike: "#34d399", // emerald
  bicycle: "#34d399",
  bus: "#fbbf24", // amber
  truck: "#fb7185", // rose
};

function pickColor(cls: string): string {
  return CLASS_COLORS[cls] ?? "#e2e8f0";
}

/**
 * Phase 3 live inference pane: the media player plus an AI overlay canvas that
 * paints normalized detection boxes (with class + track id + confidence) from
 * the latest WebSocket `overlay` payload.
 */
export function AiOverlayPane({
  name,
  running = false,
  hlsUrl,
  mjpegUrl,
  whepUrl,
  fps,
  state,
  whep = false,
  overlay,
  className,
  showTrackIds = true,
}: AiOverlayPaneProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const lastRef = useRef<InferenceOverlay | null>(null);

  useEffect(() => {
    if (overlay) lastRef.current = overlay;
    const canvas = canvasRef.current;
    const target = lastRef.current;
    if (!canvas || !target) return;
    const host = canvas.parentElement?.getBoundingClientRect();
    if (!host) return;
    const rect = canvas.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(rect.width * dpr);
    canvas.height = Math.round(rect.height * dpr);
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.lineWidth = Math.max(1.5, rect.width / 700);

    for (const box of target.boxes ?? []) {
      drawBox(ctx, box, rect.width, rect.height, showTrackIds);
    }
  }, [overlay, showTrackIds]);

  return (
    <div className={cn("relative", className)}>
      <LiveStreamPlayer
        name={name}
        running={running}
        hlsUrl={hlsUrl}
        mjpegUrl={mjpegUrl}
        whepUrl={whepUrl}
        fps={fps}
        state={state}
        whep={whep}
        className={cn(className, "aspect-video")}
      />
      <canvas
        ref={canvasRef}
        className="pointer-events-none absolute inset-0 z-10 h-full w-full"
      />
      {overlay && (
        <div className="pointer-events-none absolute right-2.5 top-7 z-20 flex items-center gap-1.5 rounded border border-border/60 bg-black/60 px-1.5 py-0.5 font-mono text-[8px] uppercase tracking-widest text-muted-foreground backdrop-blur">
          <span className="relative flex h-1.5 w-1.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-400" />
          </span>
          AI
        </div>
      )}
    </div>
  );
}

function drawBox(
  ctx: CanvasRenderingContext2D,
  box: DetectionBox,
  w: number,
  h: number,
  showTrackIds: boolean,
) {
  const color = pickColor(box.class_name);
  const x = box.x * w;
  const y = box.y * h;
  const bw = box.w * w;
  const bh = box.h * h;
  ctx.strokeStyle = color;
  ctx.strokeRect(x, y, bw, bh);

  const label = `${box.class_name}${showTrackIds && box.track_id != null ? ` #${box.track_id}` : ""} ${Math.round(box.confidence * 100)}%`;
  ctx.font = `600 ${Math.max(10, w / 90)}px ui-monospace, monospace`;
  const tw = ctx.measureText(label).width + 6;
  ctx.fillStyle = color;
  const ly = y > 14 ? y - 15 : y + bh + 2;
  ctx.fillRect(x, ly, tw, 13);
  ctx.fillStyle = "#04121a";
  ctx.fillText(label, x + 3, ly + 10);
}