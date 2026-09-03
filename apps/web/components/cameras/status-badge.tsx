"use client";

import type { CameraStatus } from "@sentinel/shared";

import { cn } from "@/lib/utils";
import { statusMeta } from "@/lib/status";

export function StatusBadge({
  status,
  className,
}: {
  status: CameraStatus;
  className?: string;
}) {
  const meta = statusMeta.camera[status] ?? statusMeta.camera.unknown;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded border px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest",
        meta.badge,
        className,
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", meta.dot)} />
      {meta.label}
    </span>
  );
}