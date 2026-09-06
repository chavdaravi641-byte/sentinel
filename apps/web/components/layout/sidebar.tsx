"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3,
  Bell,
  Brain,
  ChevronDown,
  FileWarning,
  LayoutDashboard,
  ListChecks,
  Map,
  MonitorPlay,
  Radar,
  Route,
  Settings,
  Shield,
  Video,
  Wifi,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { initials } from "@/lib/utils";
import { GUJARAT_DISTRICTS, useDistrict } from "@/lib/district";

const NAV_GROUPS = [
  {
    label: "Operations",
    items: [
      { href: "/app", label: "Road Room", description: "Live operating picture", icon: LayoutDashboard },
      { href: "/app/alerts", label: "Alerts", description: "Review and acknowledge threats", icon: Bell },
      { href: "/app/incidents", label: "Incidents", description: "Coordinate active investigations", icon: FileWarning },
    ],
  },
  {
    label: "Monitoring",
    items: [
      { href: "/live", label: "Live Wall", description: "Monitor active camera feeds", icon: MonitorPlay },
      { href: "/app/cameras", label: "Cameras", description: "Manage sensor health", icon: Video },
      { href: "/app/map", label: "Tactical Map", description: "Locate cameras and corridors", icon: Map },
    ],
  },
  {
    label: "Investigation",
    items: [
      { href: "/app/routes", label: "Vehicle Routes", description: "Reconstruct plate movement", icon: Route },
      { href: "/app/watchlist", label: "Watchlist", description: "Track flagged identifiers", icon: ListChecks },
      { href: "/ai", label: "AI Vision", description: "Inspect detection intelligence", icon: Brain },
    ],
  },
  {
    label: "Administration",
    items: [
      { href: "/iam", label: "Access Control", description: "Manage officers and roles", icon: Shield },
      { href: "/app/analytics", label: "Analytics", description: "Review system trends", icon: BarChart3 },
      { href: "/app/settings", label: "Settings", description: "Operator and system settings", icon: Settings },
    ],
  },
] as const;

export function Sidebar() {
  const pathname = usePathname();
  const { user } = useAuth();
  const { district, setDistrict } = useDistrict();

  return (
    <aside className="fixed inset-y-0 left-0 z-30 flex w-16 flex-col border-r border-border bg-card/60 backdrop-blur xl:w-56">
      {/* Brand */}
      <div className="flex h-14 items-center gap-2.5 border-b border-border px-3 xl:px-4">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-primary/30 bg-primary/10">
          <Radar className="h-4.5 w-4.5 text-primary" size={18} />
        </div>
        <div className="hidden xl:block">
          <p className="font-mono text-sm font-bold leading-none tracking-[0.25em] text-glow-cyan">
            SENTINEL
          </p>
          <p className="mt-1 font-mono text-[9px] uppercase tracking-[0.2em] text-muted-foreground">
            Gujarat Police
          </p>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 space-y-1 overflow-y-auto p-2">
        {NAV_GROUPS.map((group) => (
          <div key={group.label} className="mb-3">
            <p className="hidden px-3 pb-1 pt-3 font-mono text-[9px] uppercase tracking-[0.24em] text-muted-foreground/60 xl:block">
              {group.label}
            </p>
            {group.items.map((item) => {
          const active =
            item.href === "/app"
              ? pathname === "/app"
              : pathname.startsWith(item.href);
              return (
            <Tooltip key={item.href} delayDuration={600}>
              <TooltipTrigger asChild>
                <Link
                  href={item.href}
                  title={`${item.label}: ${item.description}`}
                  aria-label={item.label}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "group relative flex h-10 items-center justify-center gap-3 rounded-md px-2 text-sm transition-colors xl:justify-start xl:px-3",
                    active
                      ? "bg-accent text-foreground"
                      : "text-muted-foreground hover:bg-accent/60 hover:text-foreground",
                  )}
                >
                  {active && (
                    <span className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-full bg-primary shadow-[0_0_8px] shadow-primary" />
                  )}
                  <span className="sr-only">{item.label}</span>
                  <item.icon
                    className={cn(
                      "h-4 w-4 shrink-0",
                      active && "text-primary",
                    )}
                  />
                  <span className="hidden flex-1 text-left font-mono text-[12px] tracking-wider xl:block">
                    {item.label.toUpperCase()}
                  </span>
                </Link>
              </TooltipTrigger>
              <TooltipContent side="right">
                <span className="font-medium">{item.label}</span>
                <span className="ml-2 text-muted-foreground">{item.description}</span>
              </TooltipContent>
            </Tooltip>
              );
            })}
          </div>
        ))}
      </nav>

      {/* System footer */}
      <div className="border-t border-border p-2">
        <div className="mb-2 hidden rounded-md border border-primary/15 bg-primary/5 px-2.5 py-2 xl:block">
          <div className="flex items-center justify-between">
            <span className="font-mono text-[9px] uppercase tracking-[0.18em] text-muted-foreground">
              Active district
            </span>
            <ChevronDown className="h-3 w-3 text-muted-foreground" />
          </div>
          <select
            value={district}
            onChange={(event) => setDistrict(event.target.value as (typeof GUJARAT_DISTRICTS)[number])}
            aria-label="Active district"
            className="mt-1 w-full bg-transparent text-xs font-medium text-foreground outline-none"
          >
            {GUJARAT_DISTRICTS.map((item) => (
              <option key={item} value={item} className="bg-card text-foreground">
                {item}
              </option>
            ))}
          </select>
          <p className="mt-0.5 font-mono text-[9px] uppercase tracking-wider text-success">
            <span className="mr-1.5 inline-block h-1.5 w-1.5 rounded-full bg-success" />
            Operational
          </p>
        </div>
        <div className="hidden xl:flex xl:flex-col xl:gap-1 xl:px-1 xl:pb-1">
          <div className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
            <Wifi className="h-3 w-3 text-success" />
            Backend online
          </div>
          <div className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground/60">
            Phase 1 · Build 1.0.0
          </div>
        </div>
        {user && (
          <div className="flex items-center gap-2.5 rounded-md px-1 py-1.5 xl:px-2">
            <Avatar className="h-8 w-8 border border-border">
              <AvatarFallback className="bg-primary/15 font-mono text-[10px] text-primary">
                {initials(user.full_name)}
              </AvatarFallback>
            </Avatar>
            <div className="hidden min-w-0 flex-1 xl:block">
              <p className="truncate font-mono text-[11px] text-foreground">
                {user.full_name}
              </p>
              <p className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground">
                {user.role}
              </p>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}