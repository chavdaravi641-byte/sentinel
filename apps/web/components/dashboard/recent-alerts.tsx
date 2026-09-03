"use client";

import { useRouter } from "next/navigation";
import type { Alert } from "@sentinel/shared";
import { ArrowRight, Bell } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn, timeAgo } from "@/lib/utils";
import { alertTypeLabel, statusMeta } from "@/lib/status";

export function RecentAlerts({ alerts }: { alerts: Alert[] }) {
  const router = useRouter();

  if (!alerts.length) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-14 w-full" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-1">
      {alerts.map((alert) => {
        const sev = statusMeta.severity[alert.severity];
        return (
          <button
            key={alert.id}
            type="button"
            onClick={() => router.push("/app/alerts")}
            className="group flex w-full items-center gap-3 rounded-md border border-transparent px-2 py-2 text-left transition-colors hover:border-border hover:bg-accent/50"
          >
            <span
              className={cn(
                "h-2 w-2 shrink-0 rounded-full",
                sev.dot,
                alert.status === "new" && "radar-pulse",
              )}
            />
            <div className="min-w-0 flex-1">
              <p className="truncate font-mono text-xs text-foreground">
                {alertTypeLabel[alert.type]}
                <span className="text-muted-foreground"> · </span>
                {alert.camera_name ?? "—"}
              </p>
              <p className="truncate text-xs text-muted-foreground">
                {alert.message}
              </p>
            </div>
            <div className="flex shrink-0 flex-col items-end gap-1">
              <span
                className={cn(
                  "font-mono text-[10px] uppercase tracking-widest",
                  sev.text,
                )}
              >
                {sev.label}
              </span>
              <span className="font-mono text-[10px] text-muted-foreground/70">
                {timeAgo(alert.occurred_at)}
              </span>
            </div>
            <ArrowRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground/0 transition-colors group-hover:text-primary" />
          </button>
        );
      })}
      <div className="pt-2">
        <Button
          variant="ghost"
          size="sm"
          className="w-full gap-2 font-mono text-[11px] uppercase tracking-widest text-primary"
          onClick={() => router.push("/app/alerts")}
        >
          <Bell className="h-3.5 w-3.5" />
          Open Alert Console
        </Button>
      </div>
    </div>
  );
}