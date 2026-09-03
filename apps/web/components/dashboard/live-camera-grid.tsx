"use client";

import { useState } from "react";
import { Camera, Maximize2 } from "lucide-react";

import { Skeleton } from "@/components/ui/skeleton";
import { LivePlayer } from "@/components/cameras/live-player";
import { cn } from "@/lib/utils";
import { statusMeta } from "@/lib/status";

/** Minimal channel shape — either a Camera or CameraGeoPoint works. */
export interface LiveChannel {
  id: string;
  name: string;
  status: string;
  location?: string | null;
  latitude?: number;
  longitude?: number;
}

export function LiveCameraGrid({ cameras }: { cameras: LiveChannel[] }) {
  const [focused, setFocused] = useState<LiveChannel | null>(null);

  if (!cameras.length) {
    return (
      <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
        {Array.from({ length: 8 }).map((_, i) => (
          <Skeleton key={i} className="aspect-video w-full rounded-md" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
        {cameras.slice(0, 8).map((camera) => {
          const meta = statusMeta.camera[camera.status as keyof typeof statusMeta.camera] ?? statusMeta.camera.unknown;
          const online = camera.status === "online";
          return (
            <button
              key={camera.id}
              type="button"
              onClick={() => setFocused(camera)}
              className="group relative overflow-hidden rounded-md border border-border text-left transition-colors hover:border-primary/50"
            >
              <LivePlayer
                cameraName={camera.name}
                muted
                className="aspect-video"
                playing={online}
              />
              <div className="flex items-center justify-between gap-2 border-t border-border/60 bg-card/80 px-2 py-1.5">
                <span className="truncate font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                  {camera.name}
                </span>
                <span className="flex items-center gap-1.5">
                  <span
                    className={cn(
                      "h-1.5 w-1.5 rounded-full",
                      meta.dot,
                      online && "radar-pulse",
                    )}
                  />
                  <span className="hidden font-mono text-[9px] uppercase lg:inline">
                    {meta.label}
                  </span>
                </span>
              </div>
            </button>
          );
        })}
      </div>

      {focused && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-6 backdrop-blur-sm">
          <div className="w-full max-w-4xl">
            <div className="mb-3 flex items-center justify-between">
              <div>
                <p className="font-mono text-xs uppercase tracking-[0.25em] text-primary">
                  LIVE FEED · {focused.name}
                </p>
                <p className="mt-1 font-mono text-[11px] text-muted-foreground">
                  {focused.location ?? "Location not set"}
                  {typeof focused.latitude === "number" &&
                    ` · ${focused.latitude.toFixed(4)}, ${focused.longitude?.toFixed(4)}`}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setFocused(null)}
                className="rounded border border-border bg-card px-3 py-1.5 font-mono text-xs uppercase tracking-widest text-muted-foreground transition-colors hover:text-foreground"
              >
                Close
              </button>
            </div>
            <LivePlayer
              cameraName={focused.name}
              className="aspect-video w-full rounded-lg border border-border shadow-2xl"
            />
          </div>
        </div>
      )}

      <div className="flex items-center justify-between px-1">
        <span className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
          <Camera className="h-3 w-3" />
          {Math.min(8, cameras.length)} channels displayed · click to expand
        </span>
        <Maximize2 className="h-3 w-3 text-muted-foreground/50" />
      </div>
    </div>
  );
}