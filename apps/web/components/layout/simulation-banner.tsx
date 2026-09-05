"use client";

import { useInferenceConfig } from "@/lib/queries";
import { Zap } from "lucide-react";

export function SimulationBanner() {
  const { data: config } = useInferenceConfig();
  const isSim = config?.plugins?.[0]?.backend === "sim";
  // Also check ANPR config if available via /anpr/config — fallback to inference sim
  if (!isSim) return null;
  return (
    <div className="sticky top-0 z-50 flex items-center justify-center gap-2 border-b border-amber-500/30 bg-amber-500/10 px-3 py-1 text-center font-mono text-[10px] uppercase tracking-widest text-amber-300">
      <Zap className="h-3 w-3" />
      SIMULATION MODE — AI Vision (YOLO) + ANPR (OCR) running on deterministic simulation backends (no weights). Mount real models via AI_WEIGHTS_DIR for production.
    </div>
  );
}
