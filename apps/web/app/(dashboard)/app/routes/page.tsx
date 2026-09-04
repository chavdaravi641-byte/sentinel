"use client";

import { useMemo, useState } from "react";
import {
  FileDown,
  FileText,
  MapPin,
  Play,
  Radar,
  Search,
  Truck,
} from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/layout/page-header";
import { Panel } from "@/components/layout/panel";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  useVehicleDossier,
  useVehicleInterception,
  useVehicleInvestigate,
} from "@/lib/queries";
import { downloadDossier } from "@/lib/api";
import { formatDateTime } from "@/lib/utils";
import { RouteMap } from "@/components/map/route-map";

export default function VehicleRoutesPage() {
  const [plateInput, setPlateInput] = useState("");
  const [plate, setPlate] = useState("");
  const [animate, setAnimate] = useState(false);

  const { data, isLoading, isError, error } = useVehicleInvestigate(
    plate,
    !!plate,
  );

  const routeStops = useMemo(() => {
    return data?.route_summary?.ordered_stops ?? [];
  }, [data]);

  const matches = data?.matches ?? [];
  const routeSummary = data?.route_summary;

  const triggerCamera: string | null =
    routeStops.length > 0 ? routeStops[routeStops.length - 1]?.camera_id ?? null : null;

  const dossier = useVehicleDossier(plate, !!plate);
  const interception = useVehicleInterception(
    plate,
    triggerCamera,
    !!plate && !!triggerCamera,
  );

  const [exporting, setExporting] = useState<"pdf" | "md" | null>(null);

  async function handleExport(format: "pdf" | "markdown") {
    if (!plate || exporting) return;
    setExporting(format === "pdf" ? "pdf" : "md");
    try {
      const integrity = await downloadDossier(plate, format);
      toast.success(`Evidence dossier exported (${format.toUpperCase()})`, {
        description: integrity
          ? `SHA-256 ${integrity.slice(0, 16)}…`
          : undefined,
      });
    } catch (e) {
      toast.error(`Export failed: ${(e as Error).message}`);
    } finally {
      setExporting(null);
    }
  }

  function handleSearch() {
    const normalized = plateInput.trim().toUpperCase().replace(/\s+/g, "");
    if (normalized.length < 6) return;
    setAnimate(false);
    setPlate(normalized);
    // restart animation shortly after
    setTimeout(() => setAnimate(true), 400);
  }

  return (
    <>
      <PageHeader
        eyebrow="Target Traversal"
        title="Vehicle Route Reconstruction"
        description="Query ANPR detections for a plate and reconstruct its movement path across Gujarat camera locations."
      />

      {/* Search bar */}
      <Panel
        title="Vehicle Search"
        subtitle="ANPR plate lookup"
        bodyClassName="p-3"
      >
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Truck className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={plateInput}
              onChange={(e) => setPlateInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              placeholder="Enter vehicle registration number (e.g. GJ01AB1234)"
              className="pl-8 font-mono uppercase"
            />
          </div>
          <Button
            onClick={handleSearch}
            disabled={plateInput.trim().length < 6}
            className="font-mono uppercase tracking-widest"
          >
            <Search />
            Trace
          </Button>
        </div>

        {plate && (
          <div className="mt-3 flex flex-wrap items-center gap-2 font-mono text-[11px] text-muted-foreground">
            <span className="uppercase tracking-widest">Querying:</span>
            <Badge variant="outline" className="font-mono text-primary">
              {plate}
            </Badge>
            {matches.length > 0 && (
              <>
                <span className="text-muted-foreground/60">·</span>
                <span>{matches.length} matched sighting(s)</span>
              </>
            )}
          </div>
        )}
      </Panel>

      {plate && (
        <div className="mt-4 grid gap-4 xl:grid-cols-[1.7fr_1fr]">
          {/* Map */}
          <Panel
            title="GIS Traversal Route"
            subtitle="chronological camera path"
            bodyClassName="p-0"
            right={
              <div className="flex items-center gap-1">
                {routeStops.length > 0 && (
                  <>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 font-mono text-[10px]"
                      onClick={() => handleExport("pdf")}
                      disabled={exporting !== null}
                      title="Export court-admissible dossier (PDF)"
                    >
                      <FileDown className="h-3 w-3 text-[#ffdd00]" />
                      {exporting === "pdf" ? "EXPORTING…" : "EXPORT PDF"}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 font-mono text-[10px]"
                      onClick={() => handleExport("markdown")}
                      disabled={exporting !== null}
                      title="Export dossier as Markdown"
                    >
                      <FileText className="h-3 w-3 text-[#ffdd00]" />
                      {exporting === "md" ? "…" : "MD"}
                    </Button>
                  </>
                )}
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 font-mono text-[10px]"
                  onClick={() => setAnimate((v) => !v)}
                >
                  {animate ? <Play className="h-3 w-3 animate-pulse" /> : <Play className="h-3 w-3" />}
                  {animate ? "PAUSED" : "PLAY"}
                </Button>
              </div>
            }
          >
            {isLoading ? (
              <div className="flex h-[420px] items-center justify-center">
                <span className="animate-pulse font-mono text-xs uppercase tracking-widest text-muted-foreground">
                  Tracing plate across Gujarat...
                </span>
              </div>
            ) : isError ? (
              <div className="flex h-[420px] items-center justify-center">
                <span className="font-mono text-xs uppercase tracking-widest text-destructive">
                  {(error as Error)?.message ?? "No sightings found for this plate."}
                </span>
              </div>
            ) : routeStops.length === 0 ? (
              <div className="flex h-[420px] flex-col items-center justify-center gap-2">
                <MapPin className="h-8 w-8 text-muted-foreground/30" />
                <span className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
                  No camera sightings recorded for {plate}
                </span>
              </div>
            ) : (
              <RouteMap stops={routeStops} animate={animate} className="h-[420px]" />
            )}
          </Panel>

          {/* Route details sidebar */}
          <div className="space-y-4">
            <Panel
              title="Route Summary"
              subtitle="traversal stats"
              bodyClassName="p-3 space-y-2"
            >
              <div className="grid grid-cols-2 gap-2">
                <Stat label="CAMERAS VISITED" value={routeSummary?.ordered_stops.length ?? 0} />
                <Stat label="TOTAL CONFIDENCE" value={routeSummary ? `${Math.round(routeSummary.confidence * 100)}%` : "—"} />
                <Stat label="DISTANCE (KM)" value={routeSummary ? routeSummary.total_distance_km.toFixed(1) : "—"} />
                <Stat label="TRAVEL TIME (MIN)" value={routeSummary ? routeSummary.total_travel_time_minutes.toFixed(1) : "—"} />
              </div>
              {matches.length > 0 && (() => {
                const top = matches[0];
                if (!top) return null;
                return (
                  <div className="mt-2 border-t border-border/50 pt-2">
                    <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                      Match Confidence
                    </p>
                    <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-muted">
                      <div
                        className="h-full bg-primary"
                        style={{ width: `${Math.min(100, top.ocr_confidence * 100)}%` }}
                      />
                    </div>
                    <p className="mt-1 font-mono text-[10px] text-primary">
                      {Math.round(top.ocr_confidence * 100)}% plate OCR
                    </p>
                  </div>
                );
              })()}
            </Panel>

            <Panel
              title="Predictive Interception Corridor"
              subtitle="top-3 interception nodes"
              bodyClassName="p-3 space-y-2"
            >
              {!plate || !triggerCamera ? (
                <p className="font-mono text-[10px] text-muted-foreground">
                  Plot a route to compute a predictive interception vector.
                </p>
              ) : interception.isLoading ? (
                <p className="animate-pulse font-mono text-[10px] text-muted-foreground">
                  Computing corridor from trigger {triggerCamera.slice(0, 8)}…
                </p>
              ) : interception.data?.nodes.length ? (
                <>
                  <div className="rounded-md border border-primary/40 bg-primary/5 p-2.5">
                    <p className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground">
                      {interception.data.recommendation}
                    </p>
                    <div className="mt-1 flex items-center gap-2">
                      <Radar className="h-3.5 w-3.5 text-[#ffdd00]" />
                      <span className="font-mono text-[10px] text-primary">
                        {Math.round(interception.data.confidence * 100)}% ·{" "}
                        {interception.data.basis}
                      </span>
                    </div>
                  </div>
                  <ol className="space-y-1.5">
                    {interception.data.nodes.map((n) => (
                      <li
                        key={n.camera_id}
                        className="rounded-md border border-border/60 bg-card/50 p-2"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <p className="truncate font-mono text-[11px] font-semibold text-foreground">
                            {n.rank}. {n.camera_name}
                          </p>
                          <Badge
                            variant={n.is_junction ? "default" : "outline"}
                            className="font-mono text-[8px]"
                          >
                            {n.is_junction ? "JUNCTION" : "NODE"}
                          </Badge>
                        </div>
                        <p className="mt-0.5 font-mono text-[9px] uppercase tracking-widest text-muted-foreground">
                          {n.location} · {n.road_distance_km.toFixed(1)} km ·{" "}
                          {n.travel_time_minutes.toFixed(0)} min
                        </p>
                        <p className="mt-1 font-mono text-[9px] text-[#ffdd00]">
                          ETA {formatDateTime(new Date(n.eta_utc))}
                          <span className="text-muted-foreground">
                            {" "}
                            · window{" "}
                            {formatDateTime(new Date(n.window_start_utc)).slice(
                              11,
                            )}–
                            {formatDateTime(new Date(n.window_end_utc)).slice(
                              11,
                            )}
                          </span>
                        </p>
                      </li>
                    ))}
                  </ol>
                </>
              ) : (
                <p className="font-mono text-[10px] text-muted-foreground">
                  No reachable corridor within radius.
                </p>
              )}
            </Panel>

            <Panel
              title="Sighting Log"
              subtitle="chronological"
              bodyClassName="p-0"
            >
              <div className="max-h-[320px] overflow-y-auto">
                {routeStops.length === 0 ? (
                  <p className="p-4 font-mono text-[11px] text-muted-foreground">
                    No sightings.
                  </p>
                ) : (
                  <ol className="p-2">
                    {routeStops.map((stop, i) => (
                      <li
                        key={stop.camera_id + stop.ts}
                        className="relative flex items-center gap-3 rounded-md px-2 py-2 hover:bg-accent/40"
                      >
                        <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-primary/40 bg-primary/10 font-mono text-[9px] text-primary">
                          {i + 1}
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="truncate font-mono text-[11px] text-foreground">
                            {stop.camera_name ?? stop.camera_id}
                          </p>
                          <p className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground">
                            {formatDateTime(new Date(stop.ts * 1000).toISOString())}
                          </p>
                        </div>
                        {stop.lat !== null && stop.lng !== null && (
                          <span className="font-mono text-[9px] text-muted-foreground">
                            {stop.lat.toFixed(4)}, {stop.lng.toFixed(4)}
                          </span>
                        )}
                      </li>
                    ))}
                  </ol>
                )}
              </div>
            </Panel>
          </div>
        </div>
      )}

      {!plate && (
        <Panel bodyClassName="p-3" className="mt-4">
          <div className="flex items-center justify-center gap-3 py-12 text-center">
            <MapPin className="h-6 w-6 text-muted-foreground/40" />
            <p className="font-mono text-sm text-muted-foreground">
              Enter a registration number above to plot its movement across
              Gujarat&apos;s ANPR camera network.
            </p>
          </div>
        </Panel>
      )}
    </>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md border border-border/50 bg-card/50 p-2.5">
      <p className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground">
        {label}
      </p>
      <p className="mt-0.5 font-mono text-lg font-bold tabular-nums text-primary">
        {value}
      </p>
    </div>
  );
}