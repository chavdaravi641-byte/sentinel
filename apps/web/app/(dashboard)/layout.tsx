"use client";

import { AppShell } from "@/components/layout/app-shell";
import { AnprWatchlistAlert } from "@/components/alerts/anpr-watchlist-alert";

export default function AuthedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AppShell>
      <AnprWatchlistAlert />
      {children}
    </AppShell>
  );
}