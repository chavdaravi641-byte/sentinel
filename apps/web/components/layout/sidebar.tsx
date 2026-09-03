"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3,
  Bell,
  Brain,
  FileWarning,
  LayoutDashboard,
  Map,
  MonitorPlay,
  Radar,
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

const NAV_ITEMS = [
  { href: "/app", label: "Road Room", short: "OPS", icon: LayoutDashboard },
  { href: "/live", label: "Live Wall", short: "LIVE", icon: MonitorPlay },
  { href: "/ai", label: "AI Vision", short: "AI", icon: Brain },
  { href: "/app/cameras", label: "Cameras", short: "CAMS", icon: Video },
  { href: "/app/alerts", label: "Alerts", short: "ALRTS", icon: Bell },
  { href: "/app/incidents", label: "Incidents", short: "INCDNTS", icon: FileWarning },
  { href: "/app/map", label: "Tactical Map", short: "MAP", icon: Map },
  { href: "/app/analytics", label: "Analytics", short: "ANALYTICS", icon: BarChart3 },
  { href: "/iam", label: "IAM", short: "IAM", icon: Shield },
  { href: "/app/settings", label: "Settings", short: "SYS", icon: Settings },
] as const;

export function Sidebar() {
  const pathname = usePathname();
  const { user } = useAuth();

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
        {NAV_ITEMS.map((item) => {
          const active =
            item.href === "/app"
              ? pathname === "/app"
              : pathname.startsWith(item.href);
          return (
            <Tooltip key={item.href} delayDuration={600}>
              <TooltipTrigger asChild>
                <Link
                  href={item.href}
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
              <TooltipContent side="right" className="xl:hidden">
                {item.label}
              </TooltipContent>
            </Tooltip>
          );
        })}
      </nav>

      {/* System footer */}
      <div className="border-t border-border p-2">
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