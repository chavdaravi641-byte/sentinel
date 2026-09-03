"use client";

import { useMemo, useState } from "react";
import { Layers, RefreshCw } from "lucide-react";
import type { CameraGeoPoint, CameraStatus } from "@sentinel/shared";
import { CAMERA_STATUS } from "@sentinel/shared";

import { PageHeader } from "@/components/layout/page-header";
import { Panel } from "@/components/layout/panel";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { TacticalMap } from "@/components/map/tactical-map";
import { useCameras } from "@/lib/queries";
import { statusMeta } from "@/lib/status";
import { cn } from "@/lib/utils";

const STATUS_OPTIONS = [
  { value: CAMERA_STATUS.ONLINE, label: "ONLINE" },
  { value: CAMERA_STATUS.OFFLINE, label: "OFFLINE" },
  { value: CAMERA_STATUS.MAINTENANCE, label: "MAINTENANCE" },
  { value: CAMERA_STATUS.UNKNOWN, label: "UNKNOWN" },
] as const;

export default function MapPage() {
  const [hidden, setHidden] = useState<Set<CameraStatus>>(new Set());
  const { data, isLoading, refetch, isFetching } = useCameras({
    pageSize: 250,
  });

  const points: CameraGeoPoint[] = useMemo(
    () =>
      (data?.items ?? [])
        .filter((c) => !hidden.has(c.status))
        .map((c) => ({
          id: c.id,
          name: c.name,
          latitude: c.latitude,
          longitude: c.longitude,
          status: c.status,
        })),
    [data, hidden],
  );

  const counts = useMemo(() => {
    const by: Record<string, number> = {};
    for (const c of data?.items ?? []) by[c.status] = (by[c.status] ?? 0) + 1;
    return by;
  }, [data]);

  function toggle(status: CameraStatus) {
    setHidden((prev) => {
      const next = new Set(prev);
      if (next.has(status)) next.delete(status);
      else next.add(status);
      return next;
    });
  }

  return (
    <>
      <PageHeader
        eyebrow="Operational Picture"
        title="Tactical Map"
        description={`Gujarat sensor overlay · ${points.length} plotted`}
        actions={
          <Button
            variant="outline"
            onClick={() => refetch()}
            disabled={isFetching}
            className="font-mono uppercase tracking-widest"
          >
            <RefreshCw className={isFetching ? "animate-spin" : ""} />
            Refresh
          </Button>
        }
      />

      <div className="grid gap-4 xl:grid-cols-[1fr_14rem]">
        <Panel bodyClassName="p-0">
          {isLoading ? (
            <Skeleton className="h-[540px] w-full rounded-none" />
          ) : (
            <TacticalMap points={points} className="h-[540px]" />
          )}
        </Panel>

        <Panel
          title="Layer Control"
          subtitle="toggle channels"
          right={<Layers className="h-4 w-4 text-primary" />}
          bodyClassName="p-3"
        >
          <ul className="space-y-2">
            {STATUS_OPTIONS.map((o) => {
              const meta = statusMeta.camera[o.value];
              const active = !hidden.has(o.value);
              return (
                <li key={o.value}>
                  <button
                    type="button"
                    onClick={() => toggle(o.value)}
                    className={cn(
                      "flex w-full items-center gap-2.5 rounded-md border border-border/60 px-3 py-2 text-left font-mono text-[11px] uppercase tracking-widest transition-colors",
                      active
                        ? "bg-card/70 hover:border-primary/40"
                        : "opacity-40 hover:opacity-70",
                    )}
                  >
                    <span className={cn("h-2 w-2 rounded-full", meta.dot)} />
                    {o.label}
                    <span className="ml-auto tabular-nums text-muted-foreground">
                      {counts[o.value] ?? 0}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>

          <div className="mt-4 border-t border-border/60 pt-3">
            <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
              Plotted
            </p>
            <p className="mt-1 font-mono text-2xl font-bold tabular-nums">
              {points.length}
              <span className="text-sm text-muted-foreground">/{data?.total ?? 0}</span>
            </p>
          </div>

          <div className="mt-4">
            <p className="mb-2 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
              Cluster
            </p>
            <Badge variant="outline" className="font-mono text-[9px]">
              AHMEDABAD METRO · 22.99–23.05N
            </Badge>
          </div>
        </Panel>
      </div>
    </>
  );
}