"use client";

import {
  Bell,
  Camera,
  CircleDot,
  Crosshair,
  RadioTower,
  Video,
} from "lucide-react";

import { PageHeader } from "@/components/layout/page-header";
import { Panel } from "@/components/layout/panel";
import { StatCard, tones } from "@/components/dashboard/stat-card";
import { LiveCameraGrid } from "@/components/dashboard/live-camera-grid";
import { RecentAlerts } from "@/components/dashboard/recent-alerts";
import { MapPreview } from "@/components/dashboard/map-preview";
import { useDashboardSummary } from "@/lib/queries";
import { useAuth } from "@/lib/auth";
import { formatDateTime } from "@/lib/utils";

export default function DashboardPage() {
  const { user } = useAuth();
  const { data, isLoading } = useDashboardSummary();

  const cameras = data?.cameras ?? {
    total: 0,
    active: 0,
    offline: 0,
    maintenance: 0,
    unknown: 0,
  };
  const alerts = data?.alerts ?? { total: 0, new: 0, critical: 0 };

  return (
    <>
      <PageHeader
        eyebrow="Command Center"
        title="Road Room"
        description={`Live operational picture · authenticated as ${user?.full_name ?? "operator"} (${user?.role})`}
      />

      {/* Status strip */}
      <Panel bodyClassName="flex items-center gap-4 px-4 py-2.5 text-muted-foreground" className="mb-5">
        <span className="flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-widest">
          <RadioTower className="h-3.5 w-3.5 text-success" /> APi{" "}
          <span className="font-bold text-success">NOMINAL</span>
        </span>
        <span className="h-4 w-px bg-border" />
        <span className="font-mono text-[11px] uppercase tracking-widest">
          GRID·{cameras.total} SENSORS
        </span>
        <span className="h-4 w-px bg-border" />
        <span className="font-mono text-[11px] uppercase tracking-widest">
          ALERTS·T-{alerts.total} N-{alerts.new} C-{alerts.critical}
        </span>
        <span className="ml-auto hidden font-mono text-[11px] uppercase tracking-widest lg:inline">
          {formatDateTime(new Date().toISOString())}
        </span>
      </Panel>

      {/* Stat row */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          code="TOT"
          label="Total Cameras"
          value={cameras.total}
          icon={Video}
          tone={tones.cyan}
          loading={isLoading}
        />
        <StatCard
          code="ACT"
          label="Active Cameras"
          value={cameras.active}
          icon={Camera}
          tone={tones.emerald}
          loading={isLoading}
          delta={cameras.total ? Math.round((cameras.active / cameras.total) * 100) : 0}
          deltaLabel="uptime"
        />
        <StatCard
          code="OFF"
          label="Offline Cameras"
          value={cameras.offline + cameras.unknown}
          icon={Bell}
          tone={tones.rose}
          loading={isLoading}
        />
        <StatCard
          code="ALRTS"
          label="Total Alerts"
          value={alerts.total}
          icon={CircleDot}
          tone={tones.amber}
          loading={isLoading}
          delta={Math.round((alerts.total / 8) * 100)}
          deltaLabel="24h"
        />
      </div>

      {/* Live grid + recent alerts */}
      <div className="mt-5 grid gap-4 lg:grid-cols-3">
        <Panel
          title="Live Sensor Grid"
          subtitle="nearest 8 channels"
          bodyClassName="p-3"
          className="lg:col-span-2"
        >
          <LiveCameraGrid cameras={data?.camera_geo ?? []} />
        </Panel>

        <Panel
          title="Recent Alerts"
          subtitle="intelligence layer"
          right={
            <span className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
              <Crosshair className="h-3 w-3 text-primary" />
              AI PHASE 2
            </span>
          }
          bodyClassName="p-2"
        >
          <RecentAlerts alerts={data?.recent_alerts ?? []} />
        </Panel>
      </div>

      {/* Map preview */}
      <div className="mt-5">
        <MapPreview
          points={data?.camera_geo ?? []}
          loading={isLoading}
        />
      </div>
    </>
  );
}