"use client";

import { useEffect, useMemo, useState } from "react";
import { MapPin } from "lucide-react";

import { cn } from "@/lib/utils";

export interface RouteStop {
  camera_id: string;
  camera_name: string;
  lat: number | null;
  lng: number | null;
  ts: number;
  plate: string;
  confidence: number;
}

interface RouteMapProps {
  stops: RouteStop[];
  animate?: boolean;
  className?: string;
}

const W = 1000;
const H = 620;
const PAD = 60;

function project(stops: RouteStop[]) {
  const pts = stops.filter((s) => s.lat !== null && s.lng !== null);
  if (!pts.length) return null;
  let minLat = 90,
    maxLat = -90,
    minLng = 180,
    maxLng = -180;
  for (const p of pts) {
    minLat = Math.min(minLat, p.lat!);
    maxLat = Math.max(maxLat, p.lat!);
    minLng = Math.min(minLng, p.lng!);
    maxLng = Math.max(maxLng, p.lng!);
  }
  const latSpan = Math.max(maxLat - minLat, 0.15);
  const lngSpan = Math.max(maxLng - minLng, 0.15);

  const x = (lng: number) =>
    PAD + ((lng - minLng) / lngSpan) * (W - PAD * 2);
  const y = (lat: number) =>
    H - (PAD + ((lat - minLat) / latSpan) * (H - PAD * 2));

  return { x, y, bounds: { minLat, maxLat, minLng, maxLng } };
}

export function RouteMap({ stops, animate, className }: RouteMapProps) {
  const [progress, setProgress] = useState(0);
  const [hover, setHover] = useState<number | null>(null);

  const projection = useMemo(() => project(stops), [stops]);
  const coords = useMemo(
    () =>
      stops
        .filter((s) => s.lat !== null && s.lng !== null)
        .map((s) => ({ lat: s.lat!, lng: s.lng! })),
    [stops],
  );

  useEffect(() => {
    if (!animate || coords.length < 2) {
      // reset to 0 when not animating (state change scheduled via RAF callback)
      const id = requestAnimationFrame(() => setProgress(coords.length < 2 ? 1 : 0));
      return () => cancelAnimationFrame(id);
    }
    const duration = Math.max(3000, coords.length * 1500);
    const start = performance.now();
    let raf = 0;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      // ease
      setProgress(t * t * (3 - 2 * t));
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [animate, coords.length]);

  if (!projection || coords.length === 0) {
    return (
      <div className={cn("flex items-center justify-center", className)}>
        <span className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
          No coordinates to plot
        </span>
      </div>
    );
  }

  const { x, y } = projection;

  // Build path through all coords
  const pathD = coords
    .map((c, i) => `${i === 0 ? "M" : "L"} ${x(c.lng).toFixed(1)} ${y(c.lat).toFixed(1)}`)
    .join(" ");

  // Trail visible portion (path from start to progress point)
  const visibleCount = Math.max(1, Math.round(coords.length * progress));
  const trailCoords = coords.slice(0, visibleCount);
  const trailPath = trailCoords
    .map((c, i) => `${i === 0 ? "M" : "L"} ${x(c.lng).toFixed(1)} ${y(c.lat).toFixed(1)}`)
    .join(" ");

  // Head coordinate is the last visible trail point (used for marker highlighting).

  return (
    <div className={cn("relative overflow-hidden", className)}>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="xMidYMid meet"
        className="h-full w-full text-border"
      >
        <defs>
          <filter id="neon-glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="4" result="blur" />
            <feColorMatrix
              in="blur"
              type="matrix"
              values="0 0 0 0 0  0 0.9 0 0 0.95  0 0 1 0 1  0 0 0 2 0"
              result="glow"
            />
            <feMerge>
              <feMergeNode in="glow" />
              <feMergeNode in="glow" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <filter id="marker-glow" x="-100%" y="-100%" width="300%" height="300%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="3" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
        <rect width={W} height={H} fill="transparent" />
        {/* grid */}
        {Array.from({ length: 9 }).map((_, i) => {
          const gx = ((i + 1) / 10) * W;
          const gy = ((i + 1) / 10) * H;
          return (
            <g key={i} stroke="currentColor" strokeOpacity={0.05}>
              <line x1={gx} y1={0} x2={gx} y2={H} />
              <line x1={0} y1={gy} x2={W} y2={gy} />
            </g>
          );
        })}

        {/* full route (faint dashed) */}
        <path
          d={pathD}
          fill="none"
          stroke="currentColor"
          strokeOpacity={0.15}
          strokeWidth={1}
          strokeDasharray="4 6"
        />

        {/* animated trail — soft wide underglow */}
        {animate && coords.length > 1 && (
          <path
            d={trailPath}
            fill="none"
            stroke="#00e5ff"
            strokeWidth={12}
            strokeOpacity={0.18}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        )}

        {/* animated trail — neon core */}
        {animate && coords.length > 1 && (
          <path
            d={trailPath}
            fill="none"
            stroke="#00e5ff"
            strokeWidth={3.5}
            strokeLinecap="round"
            strokeLinejoin="round"
            filter="url(#neon-glow)"
          />
        )}

        {/* camera stop markers */}
        {coords.map((c, i) => {
          const isHead = animate && i === visibleCount - 1;
          const cam = stops.find((s) => s.lat === c.lat && s.lng === c.lng);
          return (
            <g
              key={i}
              transform={`translate(${x(c.lng)}, ${y(c.lat)})`}
              onMouseEnter={() => setHover(i)}
              onMouseLeave={() => setHover(null)}
              className="cursor-pointer"
            >
              {isHead && (
                <circle
                  r={14}
                  fill="none"
                  stroke="#00e5ff"
                  strokeOpacity={0.7}
                  strokeWidth={2}
                  className="radar-pulse origin-center"
                />
              )}
              <circle
                r={hover === i ? 7 : 4.5}
                fill={isHead ? "#00e5ff" : "#ff4081"}
                stroke="#04070d"
                strokeWidth={1.5}
                filter={isHead ? "url(#marker-glow)" : undefined}
              />
              {hover === i && cam && (
                <text
                  y={-14}
                  textAnchor="middle"
                  className="fill-foreground"
                  style={{
                    fontSize: 16,
                    fontFamily: "var(--font-mono)",
                    letterSpacing: "0.1em",
                  }}
                >
                  {cam.camera_name}
                </text>
              )}
            </g>
          );
        })}
      </svg>

      {/* HUD chrome */}
      <div className="pointer-events-none absolute left-3 top-3 flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
        <MapPin className="h-3.5 w-3.5 text-primary" />
        VEHICLE TRAVERSAL · GUJARAT
      </div>
      {coords.length > 1 && (
        <div className="pointer-events-none absolute right-3 top-3 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
          {coords.length} STOPS · {animate ? "ANIMATING" : "STATIC"}
        </div>
      )}

      {/* Legend */}
      <div className="pointer-events-none absolute bottom-3 left-3 flex items-center gap-3 rounded border border-border/60 bg-card/70 px-2.5 py-1.5 backdrop-blur">
        <span className="flex items-center gap-1.5 font-mono text-[9px] uppercase tracking-widest text-muted-foreground">
          <span className="h-1.5 w-1.5 rounded-full bg-[#ff4081]" />
          Camera
        </span>
        <span className="flex items-center gap-1.5 font-mono text-[9px] uppercase tracking-widest text-muted-foreground">
          <span className="h-1.5 w-1.5 rounded-full bg-[#00e5ff]" />
          Trail
        </span>
      </div>

      {hover !== null && stops[hover] && (
        <div className="pointer-events-none absolute bottom-10 right-3 hidden rounded border border-border bg-popover px-3 py-2 font-mono text-[11px] text-popover-foreground sm:block">
          <p className="uppercase tracking-widest text-primary">
            {stops[hover].camera_name}
          </p>
          <p className="mt-0.5 text-muted-foreground">
            {stops[hover].lat?.toFixed(5)}, {stops[hover].lng?.toFixed(5)}
          </p>
          <p className="mt-0.5 text-muted-foreground/70">
            conf {Math.round(stops[hover].confidence * 100)}%
          </p>
        </div>
      )}
    </div>
  );
}