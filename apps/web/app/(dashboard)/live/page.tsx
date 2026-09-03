"use client";

import { MonitorPlay } from "lucide-react";

import { PageHeader } from "@/components/layout/page-header";
import { LiveWall } from "@/components/live/live-wall";

export default function LivePage() {
  return (
    <>
      <PageHeader
        eyebrow="Surveillance Grid"
        title="Live Wall"
        description="Real-time HLS / WebRTC / MJPEG feeds from every active camera. Start or stop streams, toggle recording, and expand any channel to fullscreen."
        actions={
          <span className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
            <MonitorPlay className="h-3.5 w-3.5 text-primary" />
            PHASE 2 · EDGE MEDIA
          </span>
        }
      />
      <LiveWall />
    </>
  );
}