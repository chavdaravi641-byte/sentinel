"use client";

import type { CameraGeoPoint } from "@sentinel/shared";

import { PanelsTopLeft } from "lucide-react";

import { Panel } from "@/components/layout/panel";
import { TacticalMap } from "@/components/map/tactical-map";

export function MapPreview({
  points,
  loading,
}: {
  points: CameraGeoPoint[];
  loading?: boolean;
}) {
  return (
    <Panel
      title="Tactical Grid"
      subtitle={`${points.length} sensors plotted`}
      right={
        <PanelsTopLeft className="mr-1 h-3.5 w-3.5 text-muted-foreground/60" />
      }
      bodyClassName="p-2"
    >
      <div className="relative h-72 sm:h-80">
        {loading ? (
          <div className="flex h-full items-center justify-center font-mono text-xs uppercase tracking-widest text-muted-foreground">
            Plotting sensors…
          </div>
        ) : (
          <TacticalMap points={points} />
        )}
      </div>
    </Panel>
  );
}