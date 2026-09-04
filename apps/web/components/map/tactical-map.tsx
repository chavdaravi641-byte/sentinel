"use client";

import { useMemo, useState } from "react";
import type { CameraGeoPoint, InterceptionVector } from "@sentinel/shared";
import { Navigation, Target } from "lucide-react";

import { cn } from "@/lib/utils";
import { statusMeta } from "@/lib/status";

type Point = CameraGeoPoint;

interface TacticalMapProps {
  points: Point[];
  className?: string;
  interactive?: boolean;
  corridor?: InterceptionVector | null;
}

const W = 1000;
const H = 620;
const PAD = 60;

/**
 * Project lat/lng into the normalized viewBox. Longitude remains linear;
 * latitude is scaled with a mercator-ish correction so Gujarat geometry
 * looks roughly correct.
 */
function project(points: Point[]) {
  if (!points.length) return null;
  let minLat = 90,
    maxLat = -90,
    minLng = 180,
    maxLng = -180;
  for (const p of points) {
    minLat = Math.min(minLat, p.latitude);
    maxLat = Math.max(maxLat, p.latitude);
    minLng = Math.min(minLng, p.longitude);
    maxLng = Math.max(maxLng, p.longitude);
  }
  const latSpan = Math.max((maxLat - minLat) * 1.12, 0.2);
  const lngSpan = Math.max((maxLng - minLng) * 1.12, 0.2);

  const x = (lng: number) =>
    PAD + ((lng - minLng) / lngSpan) * (W - PAD * 2);
  const y = (lat: number) =>
    H - (PAD + ((lat - minLat) / latSpan) * (H - PAD * 2));

  return {
    x,
    y,
    bounds: { minLat, maxLat, minLng, maxLng, latSpan, lngSpan },
  };
}

export function TacticalMap({
  points,
  className,
  interactive = true,
  corridor = null,
}: TacticalMapProps) {
  const [hover, setHover] = useState<Point | null>(null);
  const projection = useMemo(() => project(points), [points]);

  if (!projection || !points.length) {
    return (
      <div className={cn("flex items-center justify-center", className)}>
        <span className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
          No camera telemetry
        </span>
      </div>
    );
  }

  const { x, y, bounds } = projection;

  function gridLines() {
    const lines = [];
    const step = 8;
    for (let i = 1; i < step; i++) {
      const gx = (i / step) * W;
      lines.push(
        <line
          key={`v${i}`}
          x1={gx}
          y1={0}
          x2={gx}
          y2={H}
          stroke="currentColor"
          strokeOpacity={0.06}
        />,
      );
      const gy = (i / step) * H;
      lines.push(
        <line
          key={`h${i}`}
          x1={0}
          y1={gy}
          x2={W}
          y2={gy}
          stroke="currentColor"
          strokeOpacity={0.06}
        />,
      );
    }
    return lines;
  }

  return (
    <div className={cn("relative overflow-hidden", className)}>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="xMidYMid meet"
        className="h-full w-full text-border"
      >
        <defs>
          <filter
            id="corridor-glow"
            x="-50%"
            y="-50%"
            width="200%"
            height="200%"
          >
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
        <rect width={W} height={H} fill="transparent" />
        {gridLines()}

        {/* coarse state boundary hint */}
        <ellipse
          cx={W * 0.5}
          cy={H * 0.56}
          rx={W * 0.4}
          ry={H * 0.34}
          fill="none"
          stroke="currentColor"
          strokeOpacity={0.12}
          strokeDasharray="4 6"
        />

        {/* Predicted Interception Corridor (killer feature #2) */}
        {corridor && corridor.nodes.length > 1 && (
          <g className="interception-corridor">
            <polyline
              points={corridor.nodes
                .map((n) => `${x(n.longitude)},${y(n.latitude)}`)
                .join(" ")}
              fill="none"
              stroke="#ffdd00"
              strokeWidth={14}
              strokeLinejoin="round"
              strokeLinecap="round"
              opacity={0.16}
            />
            <polyline
              points={corridor.nodes
                .map((n) => `${x(n.longitude)},${y(n.latitude)}`)
                .join(" ")}
              fill="none"
              stroke="#ffdd00"
              strokeWidth={3.5}
              strokeLinejoin="round"
              strokeLinecap="round"
              strokeDasharray="2 6"
              style={{ filter: "url(#corridor-glow)" }}
            />
          </g>
        )}

        {points.map((p) => {
          const px = x(p.longitude);
          const py = y(p.latitude);
          const meta = statusMeta.camera[p.status];
          const isHover = hover?.id === p.id;
          const online = p.status === "online";
          return (
            <g
              key={p.id}
              className={interactive ? "cursor-pointer" : ""}
              onMouseEnter={() => setHover(p)}
              onMouseLeave={() => setHover(null)}
              transform={`translate(${px}, ${py})`}
            >
              {online && (
                <>
                  <circle
                    r={isHover ? 15 : 9}
                    fill="none"
                    stroke={meta.dot}
                    strokeOpacity={0.5}
                    strokeWidth={1.5}
                    className="radar-pulse origin-center"
                  />
                  <circle r={6} fill={meta.dot} opacity={0.18} />
                </>
              )}
              <circle
                r={isHover ? 5 : 3.5}
                fill={meta.dot}
                stroke="#04070d"
                strokeWidth={1.5}
              />
              {isHover && (
                <text
                  y={-14}
                  textAnchor="middle"
                  className="fill-foreground"
                  style={{
                    fontSize: 18,
                    fontFamily: "var(--font-mono)",
                    letterSpacing: "0.1em",
                  }}
                >
                  {p.name}
                </text>
              )}
            </g>
          );
        })}

        {/* Corridor target markers (ranked interception nodes) */}
        {corridor &&
          corridor.nodes.map((n) => {
            const nx = x(n.longitude);
            const ny = y(n.latitude);
            return (
              <g
                key={n.camera_id}
                transform={`translate(${nx}, ${ny})`}
                className="corridor-node"
              >
                <circle
                  r={13}
                  fill="none"
                  stroke="#ffdd00"
                  strokeWidth={2}
                  strokeOpacity={0.9}
                  className="radar-pulse origin-center"
                />
                <circle r={8} fill="#ffdd00" opacity={0.12} />
                <circle r={3.5} fill="#ffdd00" stroke="#04070d" strokeWidth={1.5} />
                <text
                  y={-18}
                  textAnchor="middle"
                  className="fill-[#ffdd00]"
                  style={{
                    fontSize: 14,
                    fontWeight: 700,
                    fontFamily: "var(--font-mono)",
                  }}
                >
                  {n.rank}
                </text>
              </g>
            );
          })}
      </svg>

      {/* HUD chrome */}
      <div className="pointer-events-none absolute left-3 top-3 flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
        <Navigation className="h-3.5 w-3.5 text-primary" />
        STATE GRID · GUJARAT
      </div>
      {corridor && corridor.nodes.length > 0 && (
        <div className="pointer-events-none absolute left-3 top-10 flex items-center gap-2 rounded border border-[#ffdd00]/50 bg-[#0d0c00]/80 px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.18em] text-[#ffdd00] backdrop-blur">
          <Target className="h-3.5 w-3.5" />
          Interception corridor · {corridor.nodes.length} node
          {corridor.nodes.length > 1 ? "s" : ""} · basis {corridor.basis} ·{" "}
          {Math.round(corridor.confidence * 100)}%
        </div>
      )}
      <div className="pointer-events-none absolute right-3 top-3 font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
        LAT {bounds.minLat.toFixed(2)}–{bounds.maxLat.toFixed(2)} · LON{" "}
        {bounds.minLng.toFixed(2)}–{bounds.maxLng.toFixed(2)}
      </div>

      {/* Legend */}
      <div className="pointer-events-none absolute bottom-3 left-3 flex items-center gap-3 rounded border border-border/60 bg-card/70 px-2.5 py-1.5 backdrop-blur">
        {(["online", "offline", "maintenance", "unknown"] as const).map(
          (s) => (
            <span
              key={s}
              className="flex items-center gap-1.5 font-mono text-[9px] uppercase tracking-widest text-muted-foreground"
            >
              <span
                className={cn(
                  "h-1.5 w-1.5 rounded-full",
                  statusMeta.camera[s].dot,
                )}
              />
              {s}
            </span>
          ),
        )}
      </div>

      {hover && interactive && (
        <div className="pointer-events-none absolute bottom-10 right-3 hidden rounded border border-border bg-popover px-3 py-2 font-mono text-[11px] text-popover-foreground sm:block">
          <p className="uppercase tracking-widest text-primary">{hover.name}</p>
          <p className="mt-0.5 text-muted-foreground">
            {hover.latitude.toFixed(5)}, {hover.longitude.toFixed(5)} ·{" "}
            {statusMeta.camera[hover.status].label}
          </p>
        </div>
      )}
    </div>
  );
}