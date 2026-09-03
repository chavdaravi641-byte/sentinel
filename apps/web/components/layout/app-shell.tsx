"use client";

import type { ReactNode } from "react";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Radar } from "lucide-react";

import { Sidebar } from "@/components/layout/sidebar";
import { Topbar } from "@/components/layout/topbar";
import { TooltipProvider } from "@/components/ui/tooltip";
import { useAuth } from "@/lib/auth";

function BootScreen() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-command-grid">
      <Radar className="h-10 w-10 animate-pulse text-primary" />
      <div className="flex items-center gap-2 font-mono text-xs uppercase tracking-[0.3em] text-muted-foreground">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        Establishing secure channel
      </div>
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const { status } = useAuth();

  useEffect(() => {
    if (status === "unauthenticated") router.replace("/login");
  }, [status, router]);

  if (status === "loading") return <BootScreen />;
  if (status === "unauthenticated") return <BootScreen />;

  return (
    <TooltipProvider delayDuration={300}>
      <div className="min-h-screen">
        <Sidebar />
        <div className="flex min-h-screen flex-col pl-16 xl:pl-56">
          <Topbar />
          <main className="flex-1 bg-command-grid p-4 lg:p-6">
            <div className="relative mx-auto max-w-[1600px]">{children}</div>
          </main>
        </div>
      </div>
    </TooltipProvider>
  );
}