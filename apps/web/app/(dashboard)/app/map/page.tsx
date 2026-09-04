"use client";

import { useMemo, useState } from "react";
import { Layers, Radar, RefreshCw, Target } from "lucide-react";
import type { CameraGeoPoint, CameraStatus } from "@sentinel/shared";
import { CAMERA_STATUS } from "@sentinel/shared";

import { PageHeader } from "@/components/layout/page-header";
import { Panel } from "@/components/layout/panel";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { TacticalMap } from "@/components/map/tactical-map";
import { useCameras, useVehicleInterception } from "@/lib/queries";
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

  const [plateInput, setPlateInput] = useState("");
  const [plate, setPlate] = useState("");
  const [triggerCamera, setTriggerCamera] = useState<string | null>(null);

  const interception = useVehicleInterception(
    plate,
    triggerCamera,
    !!plate && !!triggerCamera,
  );

  function handleTrace() {
    const normalized = plateInput.trim().toUpperCase().replace(/\s+/g, "");
    if (normalized.length < 6) return;
    setPlate(normalized);
    setTriggerCamera(null);
  }

  function toggleCamera(camId?: string) {
    if (!camId) return;
    setTriggerCamera((cur) => (cur === camId ? null : camId));
  }

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
          <div className="mb-3 rounded-md border border-[#ffdd00]/40 bg-[#0d0c00]/60 p-2.5">
            <p className="mb-1.5 flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.18em] text-[#ffdd00]">
              <Radar className="h-3.5 w-3.5" /> Interception Vector
            </p>
            <Input
              value={plateInput}
              onChange={(e) => setPlateInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleTrace()}
              placeholder="Plate (e.g. GJ01AB1234)"
              className="h-8 pl-2 font-mono uppercase"
            />
            <Button
              variant="outline"
              size="sm"
              onClick={handleTrace}
              disabled={plateInput.trim().length < 6}
              className="mt-2 h-7 w-full font-mono text-[10px] uppercase tracking-widest"
            >
              <Target className="h-3 w-3 text-[#ffdd00]" /> Compute Corridor
            </Button>
            {plate && (
              <p className="mt-1.5 truncate font-mono text-[9px] uppercase tracking-widest text-muted-foreground">
                Plate <span className="text-[#ffdd00]">{plate}</span>
                {triggerCamera ? " · trigger armed" : " · click a camera to arm trigger"}
              </p>
            )}
            {interception.isFetching && (
              <p className="mt-1 animate-pulse font-mono text-[9px] uppercase tracking-widest text-muted-foreground">
                Predicting corridor…
              </p>
            )}
            {interception.data?.nodes.length ? (
              <p className="mt-1 font-mono text-[9px] uppercase tracking-widest text-[#ffdd00]">
                {interception.data.nodes.length} node
                {interception.data.nodes.length > 1 ? "s" : ""} ·{" "}
                {Math.round(interception.data.confidence * 100)}%
              </p>
            ) : null}
          </div>

          {plate && (
            <div className="mb-3">
              <p className="mb-1.5 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                Trigger Camera
              </p>
              <div className="grid grid-cols-1 gap-1">
                {(data?.items ?? []).slice(0, 8).map((c) => {
                  const selected = triggerCamera === c.id;
                  return (
                    <button
                      key={c.id}
                      type="button"
                      onClick={() => toggleCamera(c.id)}
                      className={cn(
                        "flex items-center gap-2 rounded border px-2 py-1.5 text-left font-mono text-[10px] transition-colors",
                        selected
                          ? "border-[#ffdd00]/60 bg-[#ffdd00]/10 text-[#ffdd00]"
                          : "border-border/50 text-muted-foreground hover:border-primary/40 hover:text-foreground",
                      )}
                    >
                      <span
                        className={cn(
                          "h-1.5 w-1.5 shrink-0 rounded-full",
                          statusMeta.camera[c.status].dot,
                        )}
                      />
                      <span className="truncate">{c.name}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

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