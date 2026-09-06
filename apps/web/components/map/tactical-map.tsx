"use client";

import { useMemo, useState } from "react";
import type { CameraGeoPoint, InterceptionVector } from "@sentinel/shared";
import Map, {
  Layer,
  Marker,
  NavigationControl,
  Popup,
  Source,
} from "react-map-gl/maplibre";
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

import { cn } from "@/lib/utils";

type Point = CameraGeoPoint;

interface TacticalMapProps {
  points: Point[];
  className?: string;
  interactive?: boolean;
  corridor?: InterceptionVector | null;
}

const STATUS_COLORS: Record<string, string> = {
  online: "#22c55e",
  offline: "#ef4444",
  maintenance: "#f59e0b",
  unknown: "#94a3b8",
};

const MAP_STYLE = "https://tiles.openfreemap.org/styles/liberty";

export function TacticalMap({
  points,
  className,
  interactive = true,
  corridor = null,
}: TacticalMapProps) {
  const [hover, setHover] = useState<Point | null>(null);
  const corridorCoordinates = useMemo(
    () =>
      corridor?.nodes.map((node) => [node.longitude, node.latitude] as [number, number]) ?? [],
    [corridor],
  );

  if (!points.length) {
    return (
      <div className={cn("flex items-center justify-center", className)}>
        <span className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
          No camera telemetry
        </span>
      </div>
    );
  }

  return (
    <div className={cn("relative overflow-hidden", className)}>
      <Map
        mapLib={maplibregl}
        initialViewState={{
          longitude: 72.5714,
          latitude: 23.0225,
          zoom: 8,
        }}
        mapStyle={MAP_STYLE}
      >
        <NavigationControl position="top-right" showCompass={false} />
        {corridorCoordinates.length > 1 && (
          <Source
            id="interception-corridor"
            type="geojson"
            data={{
              type: "Feature",
              properties: {},
              geometry: { type: "LineString", coordinates: corridorCoordinates },
            }}
          >
            <Layer
              id="interception-corridor-glow"
              type="line"
              paint={{
                "line-color": "#ffdd00",
                "line-width": 12,
                "line-opacity": 0.2,
                "line-blur": 2,
              }}
            />
            <Layer
              id="interception-corridor-line"
              type="line"
              paint={{
                "line-color": "#ffdd00",
                "line-width": 3,
                "line-opacity": 0.95,
                "line-dasharray": [2, 2],
              }}
            />
          </Source>
        )}
        {points.map((point) => (
          <Marker
            key={point.id}
            longitude={point.longitude}
            latitude={point.latitude}
            anchor="center"
          >
            <button
              type="button"
              aria-label={`${point.name}, ${point.status}`}
              disabled={!interactive}
              onMouseEnter={() => setHover(point)}
              onMouseLeave={() => setHover(null)}
              className="relative block h-5 w-5 rounded-full outline-none focus-visible:ring-2 focus-visible:ring-primary"
            >
              {point.status === "online" && (
                <span
                  className="absolute inset-0 animate-ping rounded-full opacity-40"
                  style={{ backgroundColor: STATUS_COLORS[point.status] }}
                />
              )}
              <span
                className="absolute left-1/2 top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-[#04070d]"
                style={{ backgroundColor: STATUS_COLORS[point.status] ?? STATUS_COLORS.unknown }}
              />
            </button>
          </Marker>
        ))}
        {hover && (
          <Popup
            longitude={hover.longitude}
            latitude={hover.latitude}
            closeButton={false}
            closeOnClick={false}
            anchor="bottom"
            offset={14}
            onClose={() => setHover(null)}
          >
            <div className="font-mono text-xs">
              <p className="font-semibold">{hover.name}</p>
              <p className="uppercase text-muted-foreground">{hover.status}</p>
            </div>
          </Popup>
        )}
      </Map>
    </div>
  );
}
