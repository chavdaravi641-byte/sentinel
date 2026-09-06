"use client";

import { useMemo, useState } from "react";
import { MapPin, Pencil, Plus, RefreshCw, ShieldAlert } from "lucide-react";
import { toast } from "sonner";
import type { Incident, IncidentStatus } from "@sentinel/shared";
import {
  INCIDENT_STATUS,
  INCIDENT_TYPE,
} from "@sentinel/shared";

import { PageHeader } from "@/components/layout/page-header";
import { Panel } from "@/components/layout/panel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { IncidentFormDialog } from "@/components/incidents/incident-form-dialog";
import { useIncidents, useUpdateIncident } from "@/lib/queries";
import { incidentTypeLabel, statusMeta } from "@/lib/status";
import { cn, timeAgo } from "@/lib/utils";

const STATUS_OPTIONS = [
  { value: "all", label: "ALL STATUS" },
  { value: INCIDENT_STATUS.OPEN, label: "OPEN" },
  { value: INCIDENT_STATUS.IN_PROGRESS, label: "IN PROGRESS" },
  { value: INCIDENT_STATUS.CLOSED, label: "CLOSED" },
] as const;

const TYPE_OPTIONS = [
  { value: "all", label: "ALL TYPES" },
  { value: INCIDENT_TYPE.THEFT, label: "THEFT" },
  { value: INCIDENT_TYPE.ASSAULT, label: "ASSAULT" },
  { value: INCIDENT_TYPE.TRAFFIC, label: "TRAFFIC" },
  { value: INCIDENT_TYPE.FIRE, label: "FIRE" },
  { value: INCIDENT_TYPE.MISSING_PERSON, label: "MISSING PERSON" },
  { value: INCIDENT_TYPE.SUSPICIOUS_ACTIVITY, label: "SUSPICIOUS ACTIVITY" },
  { value: INCIDENT_TYPE.VANDALISM, label: "VANDALISM" },
  { value: INCIDENT_TYPE.OTHER, label: "OTHER" },
] as const;

function IncidentCard({
  incident,
  onEdit,
  onSetStatus,
  busy,
}: {
  incident: Incident;
  onEdit: (i: Incident) => void;
  onSetStatus: (i: Incident, s: IncidentStatus) => void;
  busy: boolean;
}) {
  const sev = statusMeta.severity[incident.severity];
  const st = statusMeta.incident[incident.status];
  return (
    <div className="group relative flex flex-col gap-2.5 rounded-md border border-border bg-card/50 p-4 transition-colors hover:border-primary/40">
      <div className="flex items-start justify-between gap-2">
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge
            variant="outline"
            className={cn(
              "gap-1.5 border-transparent font-mono text-[9px] uppercase tracking-widest",
              sev.text,
              sev.badge,
            )}
          >
            <span className={cn("h-1.5 w-1.5 rounded-full", sev.dot)} />
            {incident.severity}
          </Badge>
          <Badge
            variant="outline"
            className={cn(
              "gap-1.5 font-mono text-[9px] uppercase tracking-widest",
              st.text,
              st.badge,
            )}
          >
            {st.label}
          </Badge>
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              aria-label="Incident actions"
              className="h-7 w-7 opacity-0 group-hover:opacity-100"
            >
              <span className="text-muted-foreground">•••</span>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => onEdit(incident)}>
              <Pencil className="h-4 w-4" /> Edit entry
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              disabled={busy || incident.status === INCIDENT_STATUS.OPEN}
              onClick={() => onSetStatus(incident, INCIDENT_STATUS.OPEN)}
            >
              Reopen
            </DropdownMenuItem>
            <DropdownMenuItem
              disabled={busy || incident.status === INCIDENT_STATUS.IN_PROGRESS}
              onClick={() => onSetStatus(incident, INCIDENT_STATUS.IN_PROGRESS)}
            >
              Mark in progress
            </DropdownMenuItem>
            <DropdownMenuItem
              disabled={busy || incident.status === INCIDENT_STATUS.CLOSED}
              onClick={() => onSetStatus(incident, INCIDENT_STATUS.CLOSED)}
            >
              Close
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <h3 className="font-mono text-sm font-semibold leading-snug">
        {incident.title}
      </h3>

      <p className="flex items-center gap-1.5 font-mono text-[11px] text-muted-foreground">
        <ShieldAlert className="h-3 w-3" />
        {incidentTypeLabel[incident.type]}
        {incident.camera_name && (
          <>
            <span className="text-muted-foreground/40">·</span>
            {incident.camera_name}
          </>
        )}
      </p>

      {incident.location && (
        <p className="flex items-center gap-1.5 font-mono text-[11px] text-muted-foreground">
          <MapPin className="h-3 w-3" />
          {incident.location}
        </p>
      )}

      {incident.description && (
        <p className="line-clamp-2 font-mono text-[11px] leading-relaxed text-muted-foreground/80">
          {incident.description}
        </p>
      )}

      <div className="mt-auto flex items-center justify-between border-t border-border/60 pt-2.5 font-mono text-[10px] uppercase tracking-widest text-muted-foreground/70">
        <span>#{incident.id.slice(0, 8)}</span>
        <span>{timeAgo(incident.occurred_at)}</span>
      </div>
    </div>
  );
}

export default function IncidentsPage() {
  const [status, setStatus] = useState<string>("all");
  const [type, setType] = useState<string>("all");
  const [formOpen, setFormOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<Incident | null>(null);

  const { data, isLoading, refetch, isFetching } = useIncidents({
    status: status === "all" ? undefined : status,
    type: type === "all" ? undefined : type,
    pageSize: 100,
  });
  const incidents = useMemo(() => data?.items ?? [], [data]);
  const updateIncident = useUpdateIncident();

  async function handleSetStatus(incident: Incident, next: IncidentStatus) {
    try {
      await updateIncident.mutateAsync({ id: incident.id, body: { status: next } });
      toast.success(`Incident moved to ${next.replace("_", " ")}.`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Update failed.");
    }
  }

  const openCount = incidents.filter((i) => i.status === INCIDENT_STATUS.OPEN).length;
  const progressCount = incidents.filter(
    (i) => i.status === INCIDENT_STATUS.IN_PROGRESS,
  ).length;
  const closedCount = incidents.filter((i) => i.status === INCIDENT_STATUS.CLOSED).length;

  return (
    <>
      <PageHeader
        eyebrow="Case Board"
        title="Incidents"
        description={`${incidents.length} on record · ${openCount} open, ${progressCount} in progress, ${closedCount} closed`}
        actions={
          <>
            <Button
              variant="outline"
              onClick={() => refetch()}
              disabled={isFetching}
              className="font-mono uppercase tracking-widest"
            >
              <RefreshCw className={isFetching ? "animate-spin" : ""} />
              Refresh
            </Button>
            <Button
              onClick={() => setFormOpen(true)}
              className="font-mono uppercase tracking-widest"
            >
              <Plus />
              Log Incident
            </Button>
          </>
        }
      />

      <Panel bodyClassName="flex flex-wrap items-center gap-3 p-3">
        <Select value={status} onValueChange={setStatus}>
          <SelectTrigger className="w-44 font-mono text-[11px] uppercase tracking-widest">
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
        <Select value={type} onValueChange={setType}>
          <SelectTrigger className="w-44 font-mono text-[11px] uppercase tracking-widest">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {TYPE_OPTIONS.map((o) => (
              <SelectItem key={o.value} value={o.value} className="font-mono uppercase">
                {o.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Panel>

      <div className="mt-5">
        {isLoading ? (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-48 w-full rounded-md" />
            ))}
          </div>
        ) : incidents.length === 0 ? (
          <Panel>
            <p className="py-10 text-center font-mono text-sm uppercase tracking-widest text-muted-foreground">
              No incidents in this view
            </p>
          </Panel>
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {incidents.map((incident) => (
              <IncidentCard
                key={incident.id}
                incident={incident}
                onEdit={setEditTarget}
                onSetStatus={handleSetStatus}
                busy={updateIncident.isPending}
              />
            ))}
          </div>
        )}
      </div>

      <IncidentFormDialog open={formOpen} onOpenChange={setFormOpen} />
      <IncidentFormDialog
        open={Boolean(editTarget)}
        onOpenChange={(o) => {
          if (!o) setEditTarget(null);
        }}
        incident={editTarget}
      />
    </>
  );
}