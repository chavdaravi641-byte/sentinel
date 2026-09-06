"use client";

import type { ReactNode } from "react";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth";
import { useDistrict } from "@/lib/district";
import { useHealth } from "@/lib/queries";
import { CheckCircle2, CircleAlert, MapPin } from "lucide-react";

interface PageHeaderProps {
  title: string;
  eyebrow?: string;
  description?: string;
  actions?: ReactNode;
  className?: string;
}

/**
 * Console-style page heading used across every module.
 */
export function PageHeader({
  title,
  eyebrow,
  description,
  actions,
  className,
}: PageHeaderProps) {
  const pathname = usePathname();
  const { user } = useAuth();
  const { district } = useDistrict();
  const { data: health } = useHealth();
  const healthOk = health?.status === "ok";
  const breadcrumb = pathname
    .split("/")
    .filter(Boolean)
    .map((segment) => segment.replace(/-/g, " "))
    .join(" / ");

  return (
    <div
      className={cn(
        "mb-5 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between",
        className,
      )}
    >
      <div>
        {eyebrow && (
          <p className="mb-1 font-mono text-[10px] uppercase tracking-[0.25em] text-primary">
            {eyebrow}
          </p>
        )}
        <h1 className="font-mono text-2xl font-bold tracking-tight">
          <span className="mr-2 text-primary">/</span>
          {title}
        </h1>
        {description && (
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            {description}
          </p>
        )}
        <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[9px] uppercase tracking-[0.16em] text-muted-foreground/70">
          <span className="truncate">{breadcrumb || "command center"}</span>
          <span className="text-border">·</span>
          <span className="flex items-center gap-1">
            <MapPin className="h-3 w-3 text-primary" />
            {district}
          </span>
          <span className="text-border">·</span>
          <span className="hidden sm:inline">
            Operator: {user?.full_name ?? "Loading"}
          </span>
          <span className="text-border">·</span>
          <span className={cn("flex items-center gap-1", healthOk ? "text-success" : "text-warning")}>
            {healthOk ? <CheckCircle2 className="h-3 w-3" /> : <CircleAlert className="h-3 w-3" />}
            {healthOk ? "Systems nominal" : "Health review"}
          </span>
          <span className="text-border">·</span>
          <span>Data freshness: not provided</span>
        </div>
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}