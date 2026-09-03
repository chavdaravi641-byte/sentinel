"use client";

import { useEffect, useState } from "react";
import { AudioLines, Radio } from "lucide-react";

import { cn } from "@/lib/utils";

interface LivePlayerProps {
  cameraName: string;
  playing?: boolean;
  muted?: boolean;
  className?: string;
}

/**
 * Phase 1 simulated CCTV feed.
 *
 * Real streaming (RTSP → HLS/WebRTC relay) is a later phase; this component
 * renders a synthetic "camera" frame with scan sheen, timestamp burn-in and
 * REC/LIVE indicators so operators get the full command-center feel.
 */
export function LivePlayer({
  cameraName,
  playing = true,
  muted = false,
  className,
}: LivePlayerProps) {
  const [timestamp, setTimestamp] = useState(() => new Date());

  useEffect(() => {
    const id = setInterval(() => setTimestamp(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const pad = (n: number) => String(n).padStart(2, "0");
  const stamp = `${pad(timestamp.getHours())}:${pad(timestamp.getMinutes())}:${pad(timestamp.getSeconds())}`;

  return (
    <div
      className={cn(
        "relative overflow-hidden bg-[#04070d] bg-command-grid",
        className,
      )}
    >
      {/* Synthetic scene: gradient + silhouette horizon */}
      <div className="absolute inset-0">
        <div className="absolute inset-0 bg-gradient-to-b from-[#081120] via-[#0a1424] to-[#05090f]" />
        {/* skyscraper silhouette */}
        <div
          className="absolute bottom-0 left-0 right-0 h-1/3 opacity-60"
          style={{
            background:
              "linear-gradient(180deg, transparent, #0b1524 30%, #070d18 100%)",
          }}
        />
      </div>

      {playing && <div className="scanline" />}

      {/* corner brackets */}
      <div className="pointer-events-none absolute inset-2">
        <span className="absolute left-0 top-0 h-4 w-4 border-l border-t border-primary/50" />
        <span className="absolute right-0 top-0 h-4 w-4 border-r border-t border-primary/50" />
        <span className="absolute bottom-0 left-0 h-4 w-4 border-b border-l border-primary/50" />
        <span className="absolute bottom-0 right-0 h-4 w-4 border-b border-r border-primary/50" />
      </div>

      {/* HUD */}
      <div className="absolute left-2.5 top-2 flex items-center gap-2">
        {playing ? (
          <span className="flex items-center gap-1.5 font-mono text-[9px] font-bold uppercase tracking-widest text-rose-400">
            <span className="live-dot" />
            REC
          </span>
        ) : (
          <span className="font-mono text-[9px] uppercase tracking-widest text-slate-500">
            NO SIGNAL
          </span>
        )}
      </div>

      <div className="absolute right-2.5 top-2 flex items-center gap-1.5 font-mono text-[9px] uppercase tracking-widest text-cyan-300/90">
        <Radio className="h-3 w-3" />
        {playing ? "LIVE" : "OFFLINE"}
      </div>

      <div className="absolute bottom-2 left-2.5 flex items-center gap-3">
        <span className="font-mono text-[9px] tracking-widest text-muted-foreground">
          CAM · {cameraName}
        </span>
      </div>
      <div className="absolute bottom-2 right-2.5 flex items-center gap-2">
        {!muted && (
          <AudioLines className="h-3 w-3 text-muted-foreground/60" />
        )}
        <span className="font-mono text-[9px] tabular-nums tracking-widest text-muted-foreground">
          {stamp} UTC
        </span>
      </div>

      {/* subtle vignette */}
      <div className="pointer-events-none absolute inset-0 shadow-[inset_0_0_60px_rgba(0,0,0,0.55)]" />
    </div>
  );
}