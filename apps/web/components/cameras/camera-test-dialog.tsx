"use client";

import { useState } from "react";
import {
  CheckCircle2,
  Crosshair,
  Loader2,
  Radar,
  XCircle,
} from "lucide-react";
import type { Camera, CameraTestResult } from "@sentinel/shared";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { useRunCameraTest } from "@/lib/queries";
import { cn, timeAgo } from "@/lib/utils";

interface CameraTestDialogProps {
  camera: Camera | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function ResultRow({
  label,
  value,
  ok,
}: {
  label: string;
  value: string;
  ok?: boolean;
}) {
  return (
    <div className="flex items-center justify-between border-b border-border/60 py-2 font-mono text-xs last:border-0">
      <span className="uppercase tracking-widest text-muted-foreground">
        {label}
      </span>
      <span
        className={cn(
          "font-semibold",
          ok === undefined ? "text-foreground" : ok ? "text-success" : "text-destructive",
        )}
      >
        {value}
      </span>
    </div>
  );
}

export function CameraTestDialog({
  camera,
  open,
  onOpenChange,
}: CameraTestDialogProps) {
  const runTest = useRunCameraTest();
  const [latest, setLatest] = useState<CameraTestResult | null>(null);
  const [running, setRunning] = useState(false);

  async function handleRun() {
    if (!camera || running) return;
    setRunning(true);
    setLatest(null);
    try {
      const result = await runTest.mutateAsync(camera.id);
      setLatest(result);
    } finally {
      setRunning(false);
    }
  }

  const result = latest;

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent className="max-w-md">
        <AlertDialogHeader>
          <AlertDialogTitle className="flex items-center gap-2 font-mono">
            <Crosshair className="h-4 w-4 text-primary" />
            CONNECTIVITY PROBE
          </AlertDialogTitle>
          <AlertDialogDescription>
            Liveness test for{" "}
            <span className="font-mono text-foreground">{camera?.name}</span>. TCP
            probe against the configured stream host — cached for 10 minutes.
          </AlertDialogDescription>
        </AlertDialogHeader>

        <div className="space-y-3">
          {camera ? (
            <>
              {result ? (
                <div className="rounded-md border border-border bg-card/60 p-3">
                  <ResultRow
                    label="Result"
                    value={result.ok ? "REACHABLE" : "UNREACHABLE"}
                    ok={result.ok}
                  />
                  <ResultRow
                    label="Host"
                    value={result.host ?? "n/a"}
                  />
                  <ResultRow
                    label="Port"
                    value={result.port !== null ? String(result.port) : "n/a"}
                  />
                  <ResultRow
                    label="Latency"
                    value={
                      result.latency_ms !== null
                        ? `${result.latency_ms} ms`
                        : result.rtt_ms !== null
                          ? `${result.rtt_ms} ms`
                          : "n/a"
                    }
                    ok={result.reachable}
                  />
                  <ResultRow
                    label="Probed"
                    value={timeAgo(result.tested_at)}
                  />
                  <p
                    className={cn(
                      "mt-2 flex items-start gap-1.5 font-mono text-[11px] leading-relaxed",
                      result.ok ? "text-success" : "text-destructive",
                    )}
                  >
                    {result.ok ? (
                      <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
                    ) : (
                      <XCircle className="h-3.5 w-3.5 shrink-0" />
                    )}
                    {result.message}
                  </p>
                </div>
              ) : (
                <div className="flex items-center gap-3 rounded-md border border-dashed border-border p-3 font-mono text-xs text-muted-foreground">
                  <Radar className="h-4 w-4 animate-pulse text-primary" />
                  {running
                    ? "Probe in flight — scanning host…"
                    : "Awaiting probe — run a test to measure reachability."}
                </div>
              )}
            </>
          ) : (
            <Badge variant="outline" className="font-mono">
              No camera selected
            </Badge>
          )}
        </div>

        <AlertDialogFooter>
          <AlertDialogCancel>Close</AlertDialogCancel>
          <AlertDialogAction
            disabled={!camera || running}
            onClick={(e) => {
              e.preventDefault();
              void handleRun();
            }}
            className="font-mono uppercase tracking-widest"
          >
            {running ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Radar className="mr-2 h-4 w-4" />
            )}
            Run Probe
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}