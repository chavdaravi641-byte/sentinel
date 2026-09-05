"use client";

import { AppShell } from "@/components/layout/app-shell";
import { AnprWatchlistAlert } from "@/components/alerts/anpr-watchlist-alert";
import { SimulationBanner } from "@/components/layout/simulation-banner";

export default function AuthedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AppShell>
      <SimulationBanner />
      <AnprWatchlistAlert />
      {children}
    </AppShell>
  );
}