"use client";

import { useRouter } from "next/navigation";
import {
  Check,
  ChevronUp,
  CircleDot,
  ExternalLink,
  Siren,
} from "lucide-react";
import type { Alert, AlertStatus } from "@sentinel/shared";
import { ALERT_STATUS } from "@sentinel/shared";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn, timeAgo } from "@/lib/utils";
import { alertTypeLabel, statusMeta } from "@/lib/status";

export interface AlertListActions {
  onSetStatus: (alert: Alert, status: AlertStatus) => void;
}

function ActionBtn({
  label,
  onClick,
  variant,
}: {
  label: string;
  onClick: () => void;
  variant: "ack" | "escalate" | "resolve";
}) {
  const styles =
    variant === "ack"
      ? "hover:border-sky-500/50 hover:text-sky-300"
      : variant === "escalate"
        ? "hover:border-orange-500/50 hover:text-orange-300"
        : "hover:border-emerald-500/50 hover:text-emerald-300";
  return (
    <Button
      variant="outline"
      size="sm"
      onClick={onClick}
      className={cn(
        "h-7 border-muted/60 px-2 font-mono text-[10px] uppercase tracking-widest text-muted-foreground",
        styles,
      )}
    >
      {label}
    </Button>
  );
}

export function AlertList({
  alerts,
  actions,
}: {
  alerts: Alert[];
  actions: AlertListActions;
}) {
  const router = useRouter();
  if (!alerts.length) {
    return (
      <div className="flex flex-col items-center gap-2 py-16 text-center">
        <CircleDot className="h-10 w-10 text-muted-foreground/40" />
        <p className="font-mono text-sm uppercase tracking-widest text-muted-foreground">
          No alerts in this view
        </p>
      </div>
    );
  }

  return (
    <ul className="divide-y divide-border/60">
      {alerts.map((alert) => {
        const severity = statusMeta.severity[alert.severity];
        const status = statusMeta.alert[alert.status];
        const accented = alert.status === ALERT_STATUS.NEW;
        return (
          <li
            key={alert.id}
            className={cn(
              "group relative flex flex-col gap-2 px-4 py-3 transition-colors hover:bg-card/50",
              accented && "bg-primary/[0.03]",
            )}
          >
            {/* severity bar */}
            <span
              className={cn(
                "absolute inset-y-0 left-0 w-0.5",
                severity.dot,
              )}
            />
            <div className="flex flex-wrap items-center gap-2">
              <Badge
                variant="outline"
                className={cn(
                  "gap-1.5 border-transparent font-mono text-[9px] uppercase tracking-widest",
                  severity.text,
                  severity.badge,
                )}
              >
                <span className={cn("h-1.5 w-1.5 rounded-full", severity.dot)} />
                {alert.severity}
              </Badge>
              <span className="inline-flex items-center gap-1 font-mono text-[11px] text-muted-foreground">
                <Siren className="h-3 w-3" />
                {alertTypeLabel[alert.type]}
              </span>
              <span className="font-mono text-[11px] text-muted-foreground">
                · {alert.camera_name ?? "UNASSIGNED"}
              </span>
              <span
                className={cn(
                  "font-mono text-[10px] uppercase tracking-widest",
                  status.text,
                )}
              >
                {status.label}
              </span>
              {alert.confidence !== null && (
                <span className="font-mono text-[10px] text-muted-foreground/70">
                  conf {Math.round(alert.confidence * 100)}%
                </span>
              )}
              <span className="ml-auto font-mono text-[10px] text-muted-foreground">
                {timeAgo(alert.occurred_at)}
              </span>
            </div>

            <p className="font-mono text-sm leading-snug text-foreground">
              {alert.message}
            </p>

            <div className="flex gap-1.5">
              {alert.status === ALERT_STATUS.NEW && (
                <>
                  <ActionBtn
                    label="Acknowledge"
                    variant="ack"
                    onClick={() =>
                      actions.onSetStatus(alert, ALERT_STATUS.ACKNOWLEDGED)
                    }
                  />
                  <ActionBtn
                    label="Escalate"
                    variant="escalate"
                    onClick={() =>
                      actions.onSetStatus(alert, ALERT_STATUS.ESCALATED)
                    }
                  />
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 gap-1 px-2 font-mono text-[10px] uppercase tracking-widest text-primary"
                    onClick={() => router.push("/app/incidents")}
                  >
                    <ExternalLink className="h-3 w-3" />
                    Investigate
                  </Button>
                </>
              )}
              {alert.status !== ALERT_STATUS.RESOLVED && (
                <>
                  <ActionBtn
                    label="Resolve"
                    variant="resolve"
                    onClick={() =>
                      actions.onSetStatus(alert, ALERT_STATUS.RESOLVED)
                    }
                  />
                  <span className="ml-auto flex items-center gap-1 font-mono text-[9px] uppercase tracking-widest text-muted-foreground/50">
                    <ChevronUp className="h-3 w-3" />
                    L2 workbench in phase 2
                  </span>
                </>
              )}
              {alert.status === ALERT_STATUS.RESOLVED && (
                <span className="ml-auto flex items-center gap-1 font-mono text-[9px] uppercase tracking-widest text-muted-foreground/50">
                  <Check className="h-3 w-3" />
                  closed
                </span>
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}