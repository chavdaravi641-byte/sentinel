"use client";

import { useMemo } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Activity, Gauge, Layers3, Siren } from "lucide-react";
import type { AlertSeverity } from "@sentinel/shared";
import { ALERT_SEVERITY } from "@sentinel/shared";

import { PageHeader } from "@/components/layout/page-header";
import { Panel } from "@/components/layout/panel";
import { StatCard, tones } from "@/components/dashboard/stat-card";
import { useAlertStats, useCameras, useIncidents } from "@/lib/queries";
import { alertTypeLabel } from "@/lib/status";

const SEVERITY_HEX: Record<AlertSeverity, string> = {
  [ALERT_SEVERITY.CRITICAL]: "#fb7185",
  [ALERT_SEVERITY.HIGH]: "#fb923c",
  [ALERT_SEVERITY.MEDIUM]: "#fbbf24",
  [ALERT_SEVERITY.LOW]: "#38bdf8",
  [ALERT_SEVERITY.INFO]: "#94a3b8",
};

const PALETTE = [
  "#22d3ee",
  "#818cf8",
  "#f472b6",
  "#4ade80",
  "#facc15",
  "#a3e635",
  "#34d399",
  "#c084fc",
];

export default function AnalyticsPage() {
  const { data: stats, isLoading: statsLoading } = useAlertStats();
  const { data: incidentData } = useIncidents({ pageSize: 500 });
  const { data: cameraData } = useCameras({ pageSize: 500 });

  const byType = useMemo(
    () =>
      Object.entries(stats?.by_type ?? {}).map(([k, v]) => ({
        name: alertTypeLabel[k as keyof typeof alertTypeLabel] ?? k,
        value: v,
      })),
    [stats],
  );

  const bySeverity = useMemo(
    () =>
      Object.entries(stats?.by_severity ?? {}).map(([k, v]) => ({
        name: k.toUpperCase(),
        value: v,
        color: SEVERITY_HEX[k as AlertSeverity],
      })),
    [stats],
  );

  const incidentStatus = useMemo(() => {
    const map: Record<string, number> = {};
    for (const i of incidentData?.items ?? []) {
      map[i.status] = (map[i.status] ?? 0) + 1;
    }
    return [
      { name: "OPEN", value: map.open ?? 0 },
      { name: "IN PROGRESS", value: map.in_progress ?? 0 },
      { name: "CLOSED", value: map.closed ?? 0 },
    ];
  }, [incidentData]);

  const cameraFleet = useMemo(() => {
    const map: Record<string, number> = {};
    for (const c of cameraData?.items ?? []) map[c.status] = (map[c.status] ?? 0) + 1;
    return [
      { name: "ONLINE", value: map.online ?? 0 },
      { name: "OFFLINE", value: map.offline ?? 0 },
      { name: "MAINT", value: map.maintenance ?? 0 },
      { name: "UNKNOWN", value: map.unknown ?? 0 },
    ];
  }, [cameraData]);

  const totalCameras = cameraData?.total ?? 0;
  const onlineCameras = cameraFleet[0]?.value ?? 0;

  return (
    <>
      <PageHeader
        eyebrow="Intelligence"
        title="Analytics"
        description="Phase-1 telemetry · detection mix, severity profile, case status and fleet uptime"
      />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          code="ALRTS"
          label="Detections (total)"
          value={stats?.total ?? 0}
          icon={Siren}
          tone={tones.cyan}
          loading={statsLoading}
        />
        <StatCard
          code="CRIT"
          label="Critical share"
          value={
            stats?.total
              ? `${Math.round(((stats.critical ?? 0) / stats.total) * 100)}%`
              : "—"
          }
          icon={Gauge}
          tone={tones.rose}
          loading={statsLoading}
        />
        <StatCard
          code="CAMS"
          label="Fleet online"
          value={
            totalCameras
              ? `${Math.round((onlineCameras / totalCameras) * 100)}%`
              : "—"
          }
          icon={Activity}
          tone={tones.emerald}
          loading={!cameraData}
        />
        <StatCard
          code="OPEN"
          label="Open incidents"
          value={incidentStatus[0]?.value ?? 0}
          icon={Layers3}
          tone={tones.amber}
          loading={!incidentData}
        />
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-2">
        <Panel title="Detection Mix" subtitle="alerts by type" bodyClassName="p-4">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={byType} margin={{ top: 8, right: 8, bottom: 8, left: -18 }}>
              <CartesianGrid stroke="rgba(148,163,184,0.1)" strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="name"
                tick={{ fill: "#94a3b8", fontSize: 10, fontFamily: "var(--font-mono)" }}
                tickLine={false}
                axisLine={{ stroke: "rgba(148,163,184,0.2)" }}
                interval={0}
                angle={-18}
                height={54}
                textAnchor="end"
              />
              <YAxis
                allowDecimals={false}
                tick={{ fill: "#64748b", fontSize: 10, fontFamily: "var(--font-mono)" }}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip
                cursor={{ fill: "rgba(34,211,238,0.06)" }}
                contentStyle={{
                  background: "hsl(224 47% 6%)",
                  border: "1px solid rgba(148,163,184,0.2)",
                  borderRadius: 6,
                  fontFamily: "var(--font-mono)",
                  fontSize: 11,
                }}
                labelStyle={{ color: "#22d3ee", textTransform: "uppercase" }}
              />
              <Bar dataKey="value" radius={[3, 3, 0, 0]} maxBarSize={46}>
                {byType.map((_, i) => (
                  <Cell key={i} fill={PALETTE[i % PALETTE.length]} fillOpacity={0.85} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Panel>

        <Panel title="Severity Profile" subtitle="risk weighting" bodyClassName="p-4">
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie
                data={bySeverity}
                dataKey="value"
                nameKey="name"
                innerRadius={62}
                outerRadius={92}
                paddingAngle={3}
                stroke="#04070d"
                strokeWidth={2}
              >
                {bySeverity.map((s, i) => (
                  <Cell key={i} fill={s.color} fillOpacity={0.9} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  background: "hsl(224 47% 6%)",
                  border: "1px solid rgba(148,163,184,0.2)",
                  borderRadius: 6,
                  fontFamily: "var(--font-mono)",
                  fontSize: 11,
                }}
                formatter={(value) => [`${value}`, "detections"]}
              />
              <Legend
                wrapperStyle={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 10,
                  textTransform: "uppercase",
                  letterSpacing: "0.1em",
                }}
                iconType="circle"
                iconSize={7}
              />
            </PieChart>
          </ResponsiveContainer>
        </Panel>

        <Panel title="Case Status" subtitle="incidents by lifecycle" bodyClassName="p-4">
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={incidentStatus} layout="vertical" margin={{ top: 8, right: 24, bottom: 8, left: 0 }}>
              <CartesianGrid stroke="rgba(148,163,184,0.1)" strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" allowDecimals={false} tick={{ fill: "#64748b", fontSize: 10, fontFamily: "var(--font-mono)" }} tickLine={false} axisLine={false} />
              <YAxis type="category" dataKey="name" width={96} tick={{ fill: "#94a3b8", fontSize: 10, fontFamily: "var(--font-mono)" }} tickLine={false} axisLine={false} />
              <Tooltip
                cursor={{ fill: "rgba(34,211,238,0.06)" }}
                contentStyle={{
                  background: "hsl(224 47% 6%)",
                  border: "1px solid rgba(148,163,184,0.2)",
                  borderRadius: 6,
                  fontFamily: "var(--font-mono)",
                  fontSize: 11,
                }}
              />
              <Bar dataKey="value" radius={[0, 3, 3, 0]} maxBarSize={22}>
                {incidentStatus.map((_, i) => (
                  <Cell key={i} fill={["#fb7185", "#fbbf24", "#22d3ee"][i]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Panel>

        <Panel title="Fleet Uptime" subtitle="sensor status distribution" bodyClassName="p-4">
          <ResponsiveContainer width="100%" height={240}>
            <PieChart>
              <Pie
                data={cameraFleet}
                dataKey="value"
                nameKey="name"
                innerRadius={58}
                outerRadius={88}
                paddingAngle={3}
                stroke="#04070d"
                strokeWidth={2}
              >
                <Cell fill="#34d399" fillOpacity={0.9} />
                <Cell fill="#fb7185" fillOpacity={0.9} />
                <Cell fill="#fbbf24" fillOpacity={0.9} />
                <Cell fill="#94a3b8" fillOpacity={0.7} />
              </Pie>
              <Tooltip
                contentStyle={{
                  background: "hsl(224 47% 6%)",
                  border: "1px solid rgba(148,163,184,0.2)",
                  borderRadius: 6,
                  fontFamily: "var(--font-mono)",
                  fontSize: 11,
                }}
              />
              <Legend
                wrapperStyle={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 10,
                  textTransform: "uppercase",
                  letterSpacing: "0.1em",
                }}
                iconType="circle"
                iconSize={7}
              />
            </PieChart>
          </ResponsiveContainer>
        </Panel>
      </div>
    </>
  );
}