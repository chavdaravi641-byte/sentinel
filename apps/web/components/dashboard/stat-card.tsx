"use client";

import type { LucideIcon } from "lucide-react";
import { ArrowDownRight, ArrowUpRight } from "lucide-react";

import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

interface StatCardProps {
  label: string;
  value: number | string;
  /** short mono identifier, e.g. "TOT" */
  code: string;
  icon: LucideIcon;
  /** tailwind classes for the icon/glow tint */
  tone: string;
  delta?: number;
  deltaLabel?: string;
  loading?: boolean;
}

export function StatCard({
  label,
  value,
  code,
  icon: Icon,
  tone,
  delta,
  deltaLabel,
  loading,
}: StatCardProps) {
  return (
    <div className="group relative overflow-hidden rounded-lg border bg-card/70 p-4 backdrop-blur transition-colors hover:border-primary/40">
      <div
        className={cn(
          "pointer-events-none absolute -right-8 -top-8 h-24 w-24 rounded-full blur-2xl opacity-20 transition-opacity group-hover:opacity-40",
          tone,
        )}
      />
      <div className="relative">
        <div className="flex items-center justify-between">
          <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            {code}
          </span>
          <Icon
            className={cn(
              "h-4 w-4",
              toneIcon[tone] ?? "text-foreground",
            )}
          />
        </div>
        {loading ? (
          <Skeleton className="mt-3 h-9 w-20" />
        ) : (
          <div className="mt-3 font-mono text-3xl font-bold tabular-nums text-foreground">
            {value}
          </div>
        )}
        <div className="mt-1 flex items-center justify-between">
          <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {label}
          </span>
          {typeof delta === "number" && (
            <span
              className={cn(
                "flex items-center gap-0.5 font-mono text-[11px] tabular-nums",
                delta >= 0 ? "text-success" : "text-danger",
              )}
            >
              {delta >= 0 ? (
                <ArrowUpRight className="h-3 w-3" />
              ) : (
                <ArrowDownRight className="h-3 w-3" />
              )}
              {Math.abs(delta)}%
              <span className="text-muted-foreground">{deltaLabel}</span>
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

/** Tone presets used by stat cards */
export const tones = {
  cyan: "bg-cyan-500/20",
  emerald: "bg-emerald-500/20",
  rose: "bg-rose-500/20",
  amber: "bg-amber-500/20",
  violet: "bg-violet-500/20",
  sky: "bg-sky-500/20",
  slate: "bg-slate-500/20",
} as const;

const toneIcon: Record<string, string> = {
  [tones.cyan]: "text-cyan-400",
  [tones.emerald]: "text-emerald-400",
  [tones.rose]: "text-rose-400",
  [tones.amber]: "text-amber-400",
  [tones.violet]: "text-violet-400",
  [tones.sky]: "text-sky-400",
  [tones.slate]: "text-slate-400",
};