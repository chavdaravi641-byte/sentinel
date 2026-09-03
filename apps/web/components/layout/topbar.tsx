"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { useState } from "react";
import {
  Command,
  Loader2,
  LogOut,
  Radio,
  UserRound,
  ChevronDown,
} from "lucide-react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/lib/auth";
import { useHealth } from "@/lib/queries";
import { initials } from "@/lib/utils";

export function Topbar() {
  const router = useRouter();
  const { user, logout } = useAuth();
  const { data: health } = useHealth();
  const [loggingOut, setLoggingOut] = useState(false);

  const systemUp = health?.status === "ok";

  async function handleLogout() {
    setLoggingOut(true);
    await logout();
    router.replace("/login");
  }

  return (
    <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-border bg-background/80 px-4 backdrop-blur lg:px-6">
      <div className="flex items-center gap-2">
        {/* Logo */}
        <div className="hidden lg:flex h-10 w-10 flex-shrink-0">
          <Image
            src="/images/gp-logo.svg"
            alt="Gujarat Police Logo"
            width={40}
            height={40}
            className="h-full w-full object-contain"
          />
        </div>
        
        {/* SENTINEL text */}
        <div className="lg:hidden">
          <span className="font-mono text-sm font-bold tracking-[0.25em] text-glow-cyan">
            SENTINEL
          </span>
        </div>
      </div>

      <div className="relative hidden flex-1 max-w-md sm:block">
        <Command className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground/60" />
        <input
          placeholder="Search cameras, alerts, incidents…"
          className="h-9 w-full rounded-md border border-input bg-card/60 pl-9 pr-3 text-sm placeholder:text-muted-foreground focus:border-primary/50 focus:outline-none focus:ring-1 focus:ring-primary/40"
        />
      </div>

      <div className="ml-auto flex items-center gap-3">
        {/* System status */}
        <Badge
          variant={systemUp ? "default" : "destructive"}
          className={systemUp ? "" : "border-danger/40 bg-danger/10 text-danger"}
        >
          <Radio className="h-3 w-3" />
          <span className="hidden sm:inline">
            {systemUp ? "SYSTEMS NOMINAL" : "SYSTEM DEGRADED"}
          </span>
          <span className="sm:hidden">
            {systemUp ? "OK" : "DEGRADED"}
          </span>
        </Badge>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" className="h-9 gap-2 px-2">
              <Avatar className="h-7 w-7 border border-border">
                <AvatarFallback className="bg-primary/15 font-mono text-[10px] text-primary">
                  {initials(user?.full_name)}
                </AvatarFallback>
              </Avatar>
              <span className="hidden font-mono text-xs sm:flex">
                {user?.full_name}
              </span>
              <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel>
              <div className="flex flex-col">
                <span className="font-mono text-xs">{user?.full_name}</span>
                <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                  {user?.role} · {user?.email}
                </span>
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              className="gap-2"
              onClick={() => router.push("/app/settings")}
            >
              <UserRound className="h-4 w-4" />
              Profile &amp; Settings
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              className="gap-2 text-destructive focus:text-destructive"
              onClick={handleLogout}
              disabled={loggingOut}
            >
              {loggingOut ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <LogOut className="h-4 w-4" />
              )}
              Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}