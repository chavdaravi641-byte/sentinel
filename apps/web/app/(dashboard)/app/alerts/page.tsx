"use client";

import { useMemo, useState } from "react";
import { RefreshCw } from "lucide-react";
import {
  AlertTriangle,
  Bell,
  CheckCheck,
  CheckCircle2,
  ChevronsUp,
  Siren,
} from "lucide-react";
import { toast } from "sonner";
import type { Alert, AlertStatus } from "@sentinel/shared";
import { ALERT_SEVERITY, ALERT_STATUS } from "@sentinel/shared";

import { PageHeader } from "@/components/layout/page-header";
import { Panel } from "@/components/layout/panel";
import { StatCard, tones } from "@/components/dashboard/stat-card";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { AlertList } from "@/components/alerts/alert-list";
import { useAlertStats, useAlerts, useUpdateAlert } from "@/lib/queries";

const SEVERITY_OPTIONS = [
  { value: "all", label: "ALL SEVERITIES" },
  { value: ALERT_SEVERITY.CRITICAL, label: "CRITICAL" },
  { value: ALERT_SEVERITY.HIGH, label: "HIGH" },
  { value: ALERT_SEVERITY.MEDIUM, label: "MEDIUM" },
  { value: ALERT_SEVERITY.LOW, label: "LOW" },
  { value: ALERT_SEVERITY.INFO, label: "INFO" },
] as const;

const STATUS_OPTIONS = [
  { value: "all", label: "ALL STATUS" },
  { value: ALERT_STATUS.NEW, label: "NEW" },
  { value: ALERT_STATUS.ACKNOWLEDGED, label: "ACKNOWLEDGED" },
  { value: ALERT_STATUS.ESCALATED, label: "ESCALATED" },
  { value: ALERT_STATUS.RESOLVED, label: "RESOLVED" },
] as const;

export default function AlertsPage() {
  const [severity, setSeverity] = useState<string>("all");
  const [status, setStatus] = useState<string>("all");

  const { data: stats, isLoading: statsLoading } = useAlertStats();
  const { data, isLoading, refetch, isFetching } = useAlerts({
    severity: severity === "all" ? undefined : severity,
    status: status === "all" ? undefined : status,
    pageSize: 100,
  });

  const updateAlert = useUpdateAlert();
  const alerts = useMemo(() => data?.items ?? [], [data]);

  async function handleSetStatus(alert: Alert, next: AlertStatus) {
    try {
      await updateAlert.mutateAsync({ id: alert.id, body: { status: next } });
      toast.success(`Alert moved to ${next.toUpperCase()} state.`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Update failed.");
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Threat Inbox"
        title="Alerts"
        description="Detections awaiting disposition · phase 1 sources (motion/spreadsheet intake)"
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

      {/* Stat row */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-6">
        <StatCard code="TOT" label="Total" value={stats?.total ?? 0} icon={Siren} tone={tones.cyan} loading={statsLoading} />
        <StatCard code="NEW" label="New" value={stats?.new ?? 0} icon={Bell} tone={tones.sky} loading={statsLoading} />
        <StatCard code="CRIT" label="Critical" value={stats?.critical ?? 0} icon={AlertTriangle} tone={tones.rose} loading={statsLoading} />
        <StatCard code="ACK" label="Ack'd" value={stats?.acknowledged ?? 0} icon={CheckCircle2} tone={tones.violet} loading={statsLoading} />
        <StatCard code="ESC" label="Escalated" value={stats?.escalated ?? 0} icon={ChevronsUp} tone={tones.amber} loading={statsLoading} />
        <StatCard code="RES" label="Resolved" value={stats?.resolved ?? 0} icon={CheckCheck} tone={tones.slate} loading={statsLoading} />
      </div>

      {/* Filter + list */}
      <div className="mt-5">
        <Panel
          title="Alert Queue"
          subtitle={`${alerts.length} visible`}
          bodyClassName="p-0"
          right={
            <div className="flex items-center gap-2">
              <Select value={severity} onValueChange={setSeverity}>
                <SelectTrigger className="h-8 w-40 font-mono text-[10px] uppercase tracking-widest">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {SEVERITY_OPTIONS.map((o) => (
                    <SelectItem key={o.value} value={o.value} className="font-mono uppercase">
                      {o.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={status} onValueChange={setStatus}>
                <SelectTrigger className="h-8 w-40 font-mono text-[10px] uppercase tracking-widest">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {STATUS_OPTIONS.map((o) => (
                    <SelectItem key={o.value} value={o.value} className="font-mono uppercase">
                      {o.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          }
        >
          {isLoading ? (
            <div className="space-y-2 p-4">
              {Array.from({ length: 8 }).map((_, i) => (
                <Skeleton key={i} className="h-16 w-full rounded-md" />
              ))}
            </div>
          ) : (
            <AlertList alerts={alerts} actions={{ onSetStatus: handleSetStatus }} />
          )}
        </Panel>
      </div>
    </>
  );
}