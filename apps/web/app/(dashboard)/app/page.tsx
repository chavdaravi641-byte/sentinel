"use client";

import {
  Bell,
  Camera,
  CircleDot,
  ExternalLink,
  Crosshair,
  MapPinned,
  ShieldAlert,
  RadioTower,
  Video,
  ListChecks,
} from "lucide-react";
import Link from "next/link";

import { PageHeader } from "@/components/layout/page-header";
import { Panel } from "@/components/layout/panel";
import { StatCard, tones } from "@/components/dashboard/stat-card";
import { LiveCameraGrid } from "@/components/dashboard/live-camera-grid";
import { RecentAlerts } from "@/components/dashboard/recent-alerts";
import { MapPreview } from "@/components/dashboard/map-preview";
import { useDashboardSummary, useHealth, useWatchlistStats } from "@/lib/queries";
import { useAuth } from "@/lib/auth";
import { timeAgo } from "@/lib/utils";

export default function DashboardPage() {
  const { user } = useAuth();
  const { data, isLoading, isError: dashboardError, dataUpdatedAt } = useDashboardSummary();
  const { data: health, isError: healthError } = useHealth();
  const watchlistStats = useWatchlistStats();

  const apiStatus = healthError
    ? "UNAVAILABLE"
    : health?.status === "ok"
      ? "NOMINAL"
      : health?.status === "degraded"
        ? "DEGRADED"
        : "CHECKING";
  const apiStatusTone =
    apiStatus === "NOMINAL"
      ? "text-success"
      : apiStatus === "DEGRADED"
        ? "text-warning"
        : "text-danger";

  const cameras = data?.cameras ?? {
    total: 0,
    active: 0,
    offline: 0,
    maintenance: 0,
    unknown: 0,
  };
  const alerts = data?.alerts ?? { total: 0, new: 0, critical: 0 };
  const detectionsToday = data?.detections_today ?? 0;
  const latestIncident = data?.latest_incident ?? null;
  const coverage = cameras.total
    ? Math.round((cameras.active / cameras.total) * 100)
    : 0;

  return (
    <>
      <PageHeader
        eyebrow="Command Center"
        title="Road Room"
        description={`Live operational picture · authenticated as ${user?.full_name ?? "operator"} (${user?.role})`}
      />

      {/* Status strip */}
      <Panel
        bodyClassName="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-2.5 text-muted-foreground"
        className="mb-5"
      >
        <span className="flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-widest">
          <RadioTower className={`h-3.5 w-3.5 ${apiStatusTone}`} /> API{" "}
          <span className={`font-bold ${apiStatusTone}`}>{apiStatus}</span>
        </span>
        <span className="h-4 w-px bg-border" />
        <span className="font-mono text-[11px] uppercase tracking-widest">
          GRID·{cameras.total} SENSORS
        </span>
        <span className="h-4 w-px bg-border" />
        <span className="font-mono text-[11px] uppercase tracking-widest">
          ALERTS·T-{alerts.total} N-{alerts.new} C-{alerts.critical}
        </span>
        <span className="hidden h-4 w-px bg-border sm:block" />
        <span className="flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-widest">
          <MapPinned className="h-3.5 w-3.5 text-primary" />
          COVERAGE <span className="font-bold text-foreground">{coverage}%</span>
        </span>
        <span className="ml-auto hidden font-mono text-[11px] uppercase tracking-widest lg:inline">
          {dataUpdatedAt ? `LAST CHECKED ${timeAgo(new Date(dataUpdatedAt).toISOString())}` : "DATA CHECK PENDING"}
        </span>
      </Panel>

      {dashboardError && (
        <Panel className="mb-5 border-danger/40" bodyClassName="p-4">
          <p className="text-sm font-medium text-danger">
            Command data is unavailable.
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            The dashboard could not refresh its operational summary. Refresh the page to retry.
          </p>
        </Panel>
      )}

      {/* Stat row */}
      <div className="grid grid-cols-2 gap-3 xl:grid-cols-8">
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
        />
        <StatCard
          code="CRIT"
          label="Critical Alerts"
          value={alerts.critical}
          icon={ShieldAlert}
          tone={tones.rose}
          loading={isLoading}
        />
        <StatCard
          code="UPT"
          label="Network Coverage"
          value={`${coverage}%`}
          icon={MapPinned}
          tone={tones.sky}
          loading={isLoading}
          delta={coverage}
          deltaLabel="online"
        />
        <StatCard
          code="DET"
          label="Today's Detections"
          value={detectionsToday}
          icon={Crosshair}
          tone={tones.cyan}
          loading={isLoading}
        />
        <StatCard
          code="WL"
          label="Active Watchlist"
          value={watchlistStats.isError ? "—" : watchlistStats.data?.active ?? 0}
          icon={ListChecks}
          tone={tones.amber}
          loading={watchlistStats.isLoading}
        />
      </div>

      <section className="mt-5 grid gap-3 rounded-lg border border-primary/20 bg-primary/[0.04] p-4 lg:grid-cols-[1fr_auto] lg:items-center">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-primary/25 bg-primary/10">
            <Crosshair className="h-4 w-4 text-primary" />
          </div>
          <div>
            <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-primary">
              Operator focus
            </p>
            <p className="mt-1 text-sm font-medium text-foreground">
              {alerts.critical > 0
                ? `${alerts.critical} critical alert${alerts.critical === 1 ? "" : "s"} require review`
                : "Network is stable — monitor the live sensor grid"}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Start with the highest-priority event, then pivot to camera evidence and vehicle history.
            </p>
          </div>
        </div>
        <Link
          href={alerts.critical > 0 ? "/app/alerts" : "/live"}
          className="inline-flex h-9 items-center justify-center gap-2 rounded-md border border-primary/30 bg-primary/10 px-3 font-mono text-[10px] uppercase tracking-widest text-primary transition-colors hover:bg-primary/20"
        >
          {alerts.critical > 0 ? "Review alerts" : "Open live wall"}
          <ExternalLink className="h-3.5 w-3.5" />
        </Link>
      </section>

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

      <Panel
        title="Latest Incident"
        subtitle="operator context"
        className="mt-5"
        bodyClassName="p-4"
      >
        {latestIncident ? (
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="font-mono text-sm font-semibold text-foreground">
                {latestIncident.title}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                {latestIncident.location ?? latestIncident.camera_name ?? "Location not provided"} ·{" "}
                {timeAgo(latestIncident.occurred_at)}
              </p>
            </div>
            <Link
              href="/app/incidents"
              className="font-mono text-[10px] uppercase tracking-widest text-primary hover:underline"
            >
              Open incident board
            </Link>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            No incidents are recorded in the current operational dataset.
          </p>
        )}
      </Panel>

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