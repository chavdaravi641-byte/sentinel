"use client";

import { useMemo } from "react";
import { Activity, Brain, Cpu, Loader2, Play, Square, Zap } from "lucide-react";
import { toast } from "sonner";

import { AiOverlayPane } from "@/components/ai/ai-overlay";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { cn, asMediaPath } from "@/lib/utils";
import { useAuth } from "@/lib/auth";
import { useInferenceSocket } from "@/lib/inference-socket";
import {
  useCameras,
  useInferenceBenchmark,
  useInferenceConfig,
  useInferenceSummary,
  useStartInference,
  useStartStream,
  useStopInference,
  useStopStream,
  useStreamHealth,
  useStreamMedia,
  useStreams,
} from "@/lib/queries";
import type { Camera, InferenceOverlay } from "@sentinel/shared";

interface AiTileProps {
  camera: Camera;
  running: boolean;
  overlay: InferenceOverlay | null;
  canControl: boolean;
}

function AiTile({ camera, running, overlay, canControl }: AiTileProps) {
  const media = useStreamMedia(camera.id);
  const health = useStreamHealth(camera.id);
  const startStream = useStartStream();
  const stopStream = useStopStream();
  const startAi = useStartInference();
  const stopAi = useStopInference();

  const streamRunning = health.data?.running ?? running;
  const aiActive = overlay != null;
  const busy =
    startStream.isPending ||
    stopStream.isPending ||
    startAi.isPending ||
    stopAi.isPending;

  const engaged = streamRunning || aiActive;

  const handleToggle = async () => {
    if (!canControl) return;
    try {
      if (engaged) {
        if (aiActive) {
          await stopAi.mutateAsync(camera.id);
          toast.success(`${camera.name}: inference stopped.`);
        }
        if (streamRunning) {
          await stopStream.mutateAsync(camera.id);
          toast.success(`${camera.name}: stream stopped.`);
        }
      } else {
        if (!streamRunning) {
          const healthNow = await startStream.mutateAsync({ id: camera.id });
          if (!healthNow.running) {
            toast.error("Camera did not reach running state.");
            return;
          }
        }
        await startAi.mutateAsync(camera.id);
        toast.success(`${camera.name}: AI inference engaged.`);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "AI control failed.");
    }
  };

  return (
    <div className="flex flex-col overflow-hidden rounded-md border border-border bg-card/50">
      <AiOverlayPane
        name={camera.name}
        running={streamRunning}
        hlsUrl={asMediaPath(media.data?.hls_url)}
        mjpegUrl={asMediaPath(media.data?.mjpeg_url)}
        whepUrl={asMediaPath(media.data?.whep_url)}
        fps={health.data?.fps}
        state={streamRunning ? undefined : health.data?.state}
        overlay={overlay}
        className="aspect-video w-full"
      />
      <div className="flex items-center justify-between gap-2 border-t border-border/60 px-2 py-1.5">
        <span className="min-w-0">
          <span className="block truncate font-mono text-[10px] uppercase tracking-wider text-foreground">
            {camera.name}
          </span>
          <span className="block truncate font-mono text-[9px] uppercase tracking-widest text-muted-foreground/70">
            {aiActive ? `${overlay?.boxes.length ?? 0} obj · #${overlay?.frame_seq ?? "—"}` : camera.location || "—"}
          </span>
        </span>
        {canControl ? (
          <Button
            type="button"
            size="icon"
            variant="ghost"
            className="h-7 w-7"
            disabled={busy}
            onClick={handleToggle}
            title={engaged ? "Disengage AI" : "Engage AI"}
          >
            {busy ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />
            ) : engaged ? (
              <Square className="h-3.5 w-3.5 text-rose-400" />
            ) : (
              <Play className="h-3.5 w-3.5 text-emerald-400" />
            )}
          </Button>
        ) : (
          <span
            className={cn(
              "h-1.5 w-1.5 rounded-full",
              aiActive ? "bg-emerald-400 radar-pulse" : "bg-slate-500",
            )}
          />
        )}
      </div>
    </div>
  );
}

export default function AiPage() {
  const { user } = useAuth();
  const canControl = user?.role === "admin" || user?.role === "operator";
  const { data: camerasData } = useCameras();
  const { data: streams } = useStreams();
  const { data: summary } = useInferenceSummary();
  const { data: config } = useInferenceConfig();
  const { connected, overlays } = useInferenceSocket(true);
  const benchmark = useInferenceBenchmark();

  const runningByCam = useMemo(
    () => new Map((streams ?? []).map((h) => [h.camera_id, h.running])),
    [streams],
  );

  const tiles = (camerasData?.items ?? []).filter((c) => c.is_active);

  const runBenchmark = async () => {
    try {
      await benchmark.mutateAsync({ iterations: 10, batch_size: 1 });
      toast.success("Benchmark complete — report written to the weights dir.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Benchmark failed.");
    }
  };

  const stats = [
    {
      label: "INFERENCE RUNS",
      value: summary?.runs_total ?? "—",
      sub: `${summary?.runs_last_minute ?? 0} / min`,
    },
    {
      label: "DETECTIONS",
      value: summary?.detections_total ?? "—",
      sub: "person · vehicles",
    },
    {
      label: "OPEN ALERTS",
      value: summary?.alerts_open ?? "—",
      sub: "persistence · crowd · traffic",
    },
    {
      label: "LATENCY",
      value: summary ? `${summary.avg_infer_ms_recent}ms` : "—",
      sub: config?.device.accelerator ?? "cpu",
    },
  ];

  return (
    <>
      <PageHeader
        eyebrow="Phase 3 · Inference Engine"
        title="AI Vision"
        description="Per-camera YOLOv12 object detection with bounding boxes, track IDs and confidence. Streams must be live before AI can engage; detections are persisted and alerted in real time."
        actions={
          <div className="flex items-center gap-2">
            {config && config.plugins[0]?.backend === "sim" && (
              <span className="flex items-center gap-1.5 rounded border border-amber-500/40 bg-amber-500/10 px-2 py-1 font-mono text-[9px] uppercase tracking-widest text-amber-300">
                <Zap className="h-3 w-3" />
                SIM BACKEND
              </span>
            )}
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={!canControl || benchmark.isPending}
              onClick={runBenchmark}
            >
              <Activity className="h-3.5 w-3.5" />
              Benchmark
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled
              className="cursor-default"
            >
              <Cpu className="h-3.5 w-3.5 text-muted-foreground" />
              {config?.device.accelerator ?? "auto"}
            </Button>
          </div>
        }
      />

      {/* Summary strip */}
      <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {stats.map((s) => (
          <div
            key={s.label}
            className="rounded-md border border-border bg-card/50 px-3 py-2"
          >
            <p className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground">
              {s.label}
            </p>
            <p className="mt-0.5 font-mono text-xl font-bold tracking-tight text-foreground">
              {s.value}
            </p>
            <p className="truncate font-mono text-[9px] uppercase tracking-widest text-primary/70">
              {s.sub}
            </p>
          </div>
        ))}
      </div>

      {/* AI wall */}
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-3">
        {tiles.map((camera) => (
          <AiTile
            key={camera.id}
            camera={camera}
            running={runningByCam.get(camera.id) ?? false}
            overlay={overlays[camera.id] ?? null}
            canControl={canControl}
          />
        ))}
      </div>

      {!tiles.length && (
        <div className="rounded-md border border-dashed border-border p-10 text-center font-mono text-xs uppercase tracking-widest text-muted-foreground">
          No active cameras registered.
        </div>
      )}

      <div className="mt-3 flex items-center justify-between">
        <span className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
          <Brain className="h-3.5 w-3.5 text-primary" />
          Whole model · person / car / bike / bus / truck / bicycle
        </span>
        <span
          className={cn(
            "flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest",
            connected ? "text-emerald-400" : "text-amber-400",
          )}
        >
          <span
            className={cn(
              "h-1.5 w-1.5 rounded-full",
              connected ? "bg-emerald-400 radar-pulse" : "bg-amber-400",
            )}
          />
          WS {connected ? "CONNECTED" : "RECONNECTING"}
        </span>
      </div>
    </>
  );
}