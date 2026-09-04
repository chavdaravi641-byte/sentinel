"use client";

import { useEffect, useMemo, useRef } from "react";
import type { Watchlist } from "@sentinel/shared";
import { WATCHLIST_CATEGORY_LABELS } from "@sentinel/shared";
import { ShieldAlert } from "lucide-react";
import { toast } from "sonner";

import { useAnprSocket } from "@/lib/anpr-socket";
import type { AnprPlateData } from "@/lib/anpr-socket";
import { useWatchlists } from "@/lib/queries";

function normalizeId(id: string): string {
  return id.replace(/[^A-Za-z0-9]/g, "").toUpperCase();
}

function findMatch(
  plate: AnprPlateData,
  watchlist: Watchlist[],
): Watchlist | null {
  const norm = normalizeId(plate.normalized_plate || plate.plate);
  for (const entry of watchlist) {
    if (normalizeId(entry.identifier_number) === norm) {
      return entry;
    }
  }
  return null;
}

export function AnprWatchlistAlert() {
  const { lastEvent } = useAnprSocket(true);
  const { data } = useWatchlists({ active_only: true, page_size: 100 });
  const shownRef = useRef<Set<string>>(new Set());

  const watchlist = useMemo(() => data?.items ?? [], [data]);

  useEffect(() => {
    if (!lastEvent || !watchlist.length) return;

    for (const plate of lastEvent.plates) {
      const match = findMatch(plate, watchlist);
      if (!match) continue;

      const plateKey = `${match.id}:${plate.normalized_plate}:${lastEvent.ts}`;
      if (shownRef.current.has(plateKey)) continue;
      shownRef.current.add(plateKey);

      const categoryLabel =
        WATCHLIST_CATEGORY_LABELS[
          match.category as keyof typeof WATCHLIST_CATEGORY_LABELS
        ] ?? match.category;

      toast.warning(`WATCHLIST MATCH — ${plate.normalized_plate}`, {
        description: [
          `Category: ${categoryLabel}`,
          `Confidence: ${(plate.ocr_confidence * 100).toFixed(0)}% OCR`,
          plate.state_code ? `State: ${plate.state_code}-${plate.rto_code}` : null,
          `Source: ${match.source_db.toUpperCase()}`,
        ]
          .filter(Boolean)
          .join("  ·  "),
        duration: 10000,
        icon: <ShieldAlert className="h-5 w-5 text-red-400" />,
        classNames: {
          toast:
            "group toast border border-red-500/50 bg-[#1a0505] text-red-50 font-mono text-xs shadow-lg shadow-red-900/30",
          description: "text-red-300/80",
          title: "text-red-400 font-bold",
        },
      });
    }
  }, [lastEvent, watchlist]);

  return null;
}
