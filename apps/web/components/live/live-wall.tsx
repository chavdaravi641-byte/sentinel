"use client";

import { useMemo, useState } from "react";
import {
  BrainCircuit,
  Circle,
  ImageDown,
  Play,
  Radio,
  Search,
  Square,
  X,
  Zap,
} from "lucide-react";
import { toast } from "sonner";

import { LiveStreamPlayer } from "@/components/live/live-stream-player";
import { Button } from "@/components/ui/button";
import { cn, asMediaPath } from "@/lib/utils";
import { statusMeta } from "@/lib/status";
import {
  useCameras,
  useRecordStart,
  useRecordStop,
  useStartStream,
  useStopStream,
  useStreamHealth,
  useStreamMedia,
  useStreams,
  useInferenceCameraStats,
} from "@/lib/queries";
import type { Camera, StreamHealth } from "@sentinel/shared";

const DENSITIES = [2, 3, 4] as const;
type Columns = (typeof DENSITIES)[number];

/* -------------------------------------------------------------------------- */

interface LiveTileProps {
  camera: Camera;
  health?: StreamHealth | null;
  whep: boolean;
  onFocus: () => void;
}

function LiveTile({ camera, health, whep, onFocus }: LiveTileProps) {
  const media = useStreamMedia(camera.id);
  const inference = useInferenceCameraStats(camera.id);
  const start = useStartStream();
  const stop = useStopStream();
  const recStart = useRecordStart();
  const recStop = useRecordStop();

  const running = health?.running ?? false;
  const recording = health?.recording ?? false;
  const busy = start.isPending || stop.isPending || recStart.isPending || recStop.isPending;

  const handleToggle = async () => {
    try {
      if (running) {
        await stop.mutateAsync(camera.id);
      } else {
        await start.mutateAsync({ id: camera.id });
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Stream control failed.");
    }
  };

  const handleRecord = async () => {
    try {
      if (recording) {
        await recStop.mutateAsync(camera.id);
        toast.success(`${camera.name}: recording stopped.`);
      } else {
        await recStart.mutateAsync({ id: camera.id });
        toast.success(`${camera.name}: recording started.`);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Recording control failed.");
    }
  };

  const state = health?.state ?? "stopped";
  const meta = statusMeta.stream[state as keyof typeof statusMeta.stream] ?? statusMeta.stream.stopped;

  return (
    <div className="group flex flex-col overflow-hidden rounded-md border border-border bg-card/50 transition-colors hover:border-primary/40">
      <button
        type="button"
        onClick={onFocus}
        className="relative block w-full text-left focus:outline-none"
      >
        <LiveStreamPlayer
          name={camera.name}
          running={running}
          hlsUrl={asMediaPath(media.data?.hls_url)}
          mjpegUrl={asMediaPath(media.data?.mjpeg_url)}
          whepUrl={asMediaPath(media.data?.whep_url)}
          recording={recording}
          fps={health?.fps}
          state={running ? undefined : state}
          whep={whep}
          className="aspect-video w-full"
        />
      </button>

      <div className="flex items-center justify-between gap-2 border-t border-border/60 px-2 py-1.5">
        <span className="min-w-0">
          <span className="block truncate font-mono text-[10px] uppercase tracking-wider text-foreground">
            {camera.name}
          </span>
          <span className="block truncate font-mono text-[9px] uppercase tracking-widest text-muted-foreground/70">
            {camera.location || "—"}
          </span>
        </span>
        <span className="flex items-center gap-1 text-[10px]">
        <span
          className={cn(
            "hidden items-center gap-1 font-mono text-[9px] uppercase tracking-wider sm:flex",
            inference.data?.inference_active ? "text-emerald-300" : "text-muted-foreground",
          )}
          title="AI inference status"
        >
          <BrainCircuit className="h-3 w-3" />
          {inference.data?.inference_active ? "AI ON" : "AI OFF"}
        </span>
        <span className="hidden font-mono text-[9px] uppercase tracking-wider text-muted-foreground sm:inline">
          {health?.latency_ms != null ? `${Math.round(health.latency_ms)} ms` : "Latency —"}
        </span>
        {media.data?.snapshot_url && (
          <a
            href={asMediaPath(media.data.snapshot_url)}
            target="_blank"
            rel="noreferrer"
            className="inline-flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
            aria-label={`Open snapshot for ${camera.name}`}
            title="Open snapshot"
            onClick={(event) => event.stopPropagation()}
          >
            <ImageDown className="h-3.5 w-3.5" />
          </a>
        )}
          <Button
            type="button"
            size="icon"
            variant="ghost"
            className="h-7 w-7"
            disabled={busy}
            onClick={handleToggle}
            aria-label={running ? "Stop stream" : "Start stream"}
            title={running ? "Stop stream" : "Start stream"}
          >
            {running ? (
              <Square className="h-3.5 w-3.5 text-rose-400" />
            ) : (
              <Play className="h-3.5 w-3.5 text-emerald-400" />
            )}
          </Button>
          <Button
            type="button"
            size="icon"
            variant="ghost"
            className="h-7 w-7"
            disabled={busy || !running}
            onClick={handleRecord}
            aria-label={recording ? "Stop recording" : "Start recording"}
            title={recording ? "Stop recording" : "Start recording"}
          >
            <Circle
              className={cn(
                "h-3.5 w-3.5",
                recording ? "fill-rose-500 text-rose-500" : "text-rose-400/60",
              )}
            />
          </Button>
          <span
            className={cn(
              "h-1.5 w-1.5 rounded-full",
              meta.dot,
              running && "radar-pulse",
            )}
          />
        </span>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */

interface FocusState {
  camera: Camera;
  health: StreamHealth | null | undefined;
}

export function LiveWall() {
  const { data: camerasData } = useCameras();
  const { data: streams } = useStreams();
  const [query, setQuery] = useState("");
  const [cols, setCols] = useState<Columns>(4);
  const [whep, setWhep] = useState(false);
  const [focus, setFocus] = useState<FocusState | null>(null);

  const startAll = useStartStream();
  const stopAll = useStopStream();

  const healthByCam = useMemo(
    () => new Map((streams ?? []).map((h) => [h.camera_id, h])),
    [streams],
  );

  const tiles = useMemo(
    () =>
      (camerasData?.items ?? [])
        .filter((c) => c.is_active)
        .filter((c) => {
          const q = query.trim().toLowerCase();
          if (!q) return true;
          return (
            c.name.toLowerCase().includes(q) ||
            (c.location ?? "").toLowerCase().includes(q)
          );
        }),
    [camerasData, query],
  );

  const runningCount = tiles.filter(
    (t) => healthByCam.get(t.id)?.running,
  ).length;

  const handleStartAll = async () => {
    const targets = tiles.filter((t) => !healthByCam.get(t.id)?.running);
    if (!targets.length) {
      toast.info("All displayed channels already streaming.");
      return;
    }
    const results = await Promise.allSettled(
      targets.map((t) => startAll.mutateAsync({ id: t.id })),
    );
    const ok = results.filter((r) => r.status === "fulfilled").length;
    toast.success(`${ok}/${targets.length} channels started.`);
  };

  const handleStopAll = async () => {
    const targets = tiles.filter((t) => healthByCam.get(t.id)?.running);
    if (!targets.length) {
      toast.info("No active channels to stop.");
      return;
    }
    const results = await Promise.allSettled(
      targets.map((t) => stopAll.mutateAsync(t.id)),
    );
    const ok = results.filter((r) => r.status === "fulfilled").length;
    toast.success(`${ok}/${targets.length} channels stopped.`);
  };

  return (
    <div className="space-y-3">
      {/* Control strip */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filter channels…"
            className="h-9 w-56 rounded-md border border-input bg-card/70 pl-8 pr-3 font-mono text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </div>

        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={handleStartAll}
          disabled={startAll.isPending || runningCount === tiles.length}
        >
          <Play className="h-3.5 w-3.5 text-emerald-400" />
          Start all
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={handleStopAll}
          disabled={stopAll.isPending || runningCount === 0}
        >
          <Square className="h-3.5 w-3.5 text-rose-400" />
          Stop all
        </Button>

        <label className="flex h-9 cursor-pointer items-center gap-2 rounded-md border border-input bg-card/70 px-3 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
          <input
            type="checkbox"
            checked={whep}
            onChange={(e) => setWhep(e.target.checked)}
            className="h-3.5 w-3.5 accent-primary"
          />
          <Radio className="h-3 w-3" />
          WHEP
        </label>

        <div className="flex h-9 items-center overflow-hidden rounded-md border border-input bg-card/70">
          {DENSITIES.map((n) => (
            <button
              key={n}
              type="button"
              onClick={() => setCols(n)}
              className={cn(
                "h-full px-2.5 font-mono text-[10px] uppercase tracking-widest transition-colors",
                cols === n
                  ? "bg-accent text-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {n}×{n / 2}
            </button>
          ))}
        </div>

        <span className="ml-auto flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
          <Zap className="h-3 w-3 text-emerald-400" />
          {runningCount}/{tiles.length} streaming
        </span>
      </div>

      {/* Wall grid */}
      <div
        className={cn(
          "grid grid-cols-2 gap-2",
          cols >= 3 && "lg:grid-cols-3",
          cols >= 4 && "xl:grid-cols-4",
        )}
      >
        {tiles.map((camera) => (
          <LiveTile
            key={camera.id}
            camera={camera}
            health={healthByCam.get(camera.id)}
            whep={whep}
            onFocus={() =>
              setFocus({ camera, health: healthByCam.get(camera.id) })
            }
          />
        ))}
      </div>

      {!tiles.length && (
        <div className="rounded-md border border-dashed border-border p-10 text-center font-mono text-xs uppercase tracking-widest text-muted-foreground">
          No cameras match the current filter.
        </div>
      )}

      {/* Fullscreen modal */}
      {focus && (
        <LiveFullscreen
          camera={focus.camera}
          running={focus.health?.running ?? false}
          recording={focus.health?.recording ?? false}
          fps={focus.health?.fps}
          whep={whep}
          onClose={() => setFocus(null)}
        />
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------- */

function LiveFullscreen({
  camera,
  running: runningProp,
  recording: recordingProp,
  fps: fpsProp,
  whep,
  onClose,
}: {
  camera: Camera;
  running: boolean;
  recording: boolean;
  fps: number | null | undefined;
  whep: boolean;
  onClose: () => void;
}) {
  const media = useStreamMedia(camera.id);
  const health = useStreamHealth(camera.id);
  const running = health.data?.running ?? runningProp;
  const recording = health.data?.recording ?? recordingProp;
  const fps = health.data?.fps ?? fpsProp;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 p-4 backdrop-blur-sm lg:p-8">
      <div className="w-full max-w-5xl">
        <div className="mb-3 flex items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="font-mono text-xs uppercase tracking-[0.25em] text-primary">
              LIVE FEED · FULLSCREEN
            </p>
            <p className="mt-1 truncate font-mono text-[11px] text-muted-foreground">
              {camera.name}
              {camera.location ? ` · ${camera.location}` : ""}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <LiveTileControls
              cameraId={camera.id}
              running={running}
              recording={recording}
            />
            <Button type="button" variant="outline" size="sm" onClick={onClose}>
              <X className="h-3.5 w-3.5" />
              Close
            </Button>
          </div>
        </div>
        <LiveStreamPlayer
          name={camera.name}
          running={running}
          hlsUrl={asMediaPath(media.data?.hls_url)}
          mjpegUrl={asMediaPath(media.data?.mjpeg_url)}
          whepUrl={asMediaPath(media.data?.whep_url)}
          recording={recording}
          fps={fps}
          whep={whep}
          className="aspect-video w-full rounded-lg border border-border shadow-2xl"
        />
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */

function LiveTileControls({
  cameraId,
  running,
  recording,
}: {
  cameraId: string;
  running: boolean;
  recording: boolean;
}) {
  const start = useStartStream();
  const stop = useStopStream();
  const recStart = useRecordStart();
  const recStop = useRecordStop();
  const busy = start.isPending || stop.isPending || recStart.isPending || recStop.isPending;

  const toggle = async () => {
    try {
      if (running) await stop.mutateAsync(cameraId);
      else await start.mutateAsync({ id: cameraId });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Stream control failed.");
    }
  };

  const toggleRec = async () => {
    try {
      if (recording) await recStop.mutateAsync(cameraId);
      else await recStart.mutateAsync({ id: cameraId });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Recording control failed.");
    }
  };

  return (
    <div className="flex items-center gap-2">
      <Button type="button" size="sm" variant="outline" disabled={busy} onClick={toggle}>
        {running ? <Square className="h-3 w-3 text-rose-400" /> : <Play className="h-3 w-3 text-emerald-400" />}
        {running ? "Stop" : "Start"}
      </Button>
      <Button type="button" size="sm" variant="outline" disabled={busy || !running} onClick={toggleRec}>
        <Circle className={cn("h-3 w-3", recording ? "fill-rose-500 text-rose-500" : "text-rose-400/60")} />
        {recording ? "Stop rec" : "Record"}
      </Button>
    </div>
  );
}