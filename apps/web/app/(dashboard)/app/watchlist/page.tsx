"use client";

import { useMemo, useState } from "react";
import { FileDown, Plus, RefreshCw, Search } from "lucide-react";
import { toast } from "sonner";
import type {
  Watchlist,
  WatchlistCategory,
} from "@sentinel/shared";
import {
  WATCHLIST_CATEGORY,
  WATCHLIST_CATEGORY_LABELS,
  WATCHLIST_SOURCE_DB,
  WATCHLIST_SOURCE_LABELS,
  WATCHLIST_TARGET_LABELS,
} from "@sentinel/shared";

import { PageHeader } from "@/components/layout/page-header";
import { Panel } from "@/components/layout/panel";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
import {
  useWatchlists,
  useWatchlistStats,
  useDeleteWatchlist,
} from "@/lib/queries";
import { downloadDossier } from "@/lib/api";
import { cn } from "@/lib/utils";
import { WatchlistFormSheet } from "@/components/watchlist/watchlist-form-sheet";

const CATEGORY_OPTIONS: { value: string; label: string; tone: string }[] = [
  { value: "all", label: "ALL", tone: "border-border/60" },
  { value: WATCHLIST_CATEGORY.STOLEN_VEHICLE, label: "STOLEN VEHICLE", tone: "border-red-400/50 text-red-400" },
  { value: WATCHLIST_CATEGORY.WANTED, label: "WANTED", tone: "border-amber-400/50 text-amber-400" },
  { value: WATCHLIST_CATEGORY.MISSING, label: "MISSING", tone: "border-sky-400/50 text-sky-400" },
  { value: WATCHLIST_CATEGORY.BLACKLISTED, label: "BLACKLISTED", tone: "border-purple-400/50 text-purple-400" },
  { value: WATCHLIST_CATEGORY.SUSPECT, label: "SUSPECT", tone: "border-orange-400/50 text-orange-400" },
  { value: WATCHLIST_CATEGORY.OTHER, label: "OTHER", tone: "border-border/60" },
];

const SOURCE_OPTIONS = [
  { value: "all", label: "ALL SOURCES" },
  { value: WATCHLIST_SOURCE_DB.VAHAN, label: "VAHAN" },
  { value: WATCHLIST_SOURCE_DB.EGUJCOP, label: "EGUJCOP" },
  { value: WATCHLIST_SOURCE_DB.SARTHI, label: "SARTHI" },
  { value: WATCHLIST_SOURCE_DB.INTERNAL, label: "INTERNAL" },
  { value: WATCHLIST_SOURCE_DB.MANUAL, label: "MANUAL" },
];

function categoryTone(cat: WatchlistCategory): string {
  switch (cat) {
    case "stolen_vehicle": return "border-red-400/50 text-red-400";
    case "wanted": return "border-amber-400/50 text-amber-400";
    case "missing": return "border-sky-400/50 text-sky-400";
    case "blacklisted": return "border-purple-400/50 text-purple-400";
    case "suspect": return "border-orange-400/50 text-orange-400";
    default: return "border-border/60 text-muted-foreground";
  }
}

export default function WatchlistPage() {
  const [category, setCategory] = useState<string>("all");
  const [source, setSource] = useState<string>("all");
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [activeOnly, setActiveOnly] = useState(false);

  const [createOpen, setCreateOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<Watchlist | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Watchlist | null>(null);

  const { data, isLoading, refetch, isFetching } = useWatchlists({
    category: category === "all" ? undefined : category,
    source_db: source === "all" ? undefined : source,
    search: query || undefined,
    active_only: activeOnly || undefined,
    page_size: 100,
  });
  const stats = useWatchlistStats();
  const deleteEntry = useDeleteWatchlist();

  const entries = useMemo(() => data?.items ?? [], [data]);

  async function handleDelete() {
    if (!deleteTarget) return;
    try {
      await deleteEntry.mutateAsync(deleteTarget.id);
      toast.success(`Removed ${deleteTarget.identifier_number} from watchlist.`);
      setDeleteTarget(null);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Delete failed.");
    }
  }

  const [exportingId, setExportingId] = useState<string | null>(null);

  async function handleExport(id: string) {
    if (exportingId || !id) return;
    setExportingId(id);
    try {
      const integrity = await downloadDossier(id, "pdf");
      toast.success(`Evidence dossier exported for ${id}`, {
        description: integrity ? `SHA-256 ${integrity.slice(0, 16)}…` : undefined,
      });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Export failed.");
    } finally {
      setExportingId(null);
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Flagged Targets"
        title="Watchlist"
        description={`${entries.length} flagged identifiers · cross-referenced in real time by the ANPR engine`}
        actions={
          <>
            <Button
              variant="outline"
              onClick={() => refetch()}
              disabled={isFetching}
              className="font-mono uppercase tracking-widest"
            >
              <RefreshCw className={isFetching ? "animate-spin" : ""} />
              Refresh
            </Button>
            <Button
              onClick={() => setCreateOpen(true)}
              className="font-mono uppercase tracking-widest"
            >
              <Plus />
              Add
            </Button>
          </>
        }
      />

      {/* Stat strip */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { label: "TOTAL", value: stats.data?.total ?? 0, tone: "text-primary" },
          { label: "ACTIVE", value: stats.data?.active ?? 0, tone: "text-success" },
          { label: "STOLEN", value: stats.data?.by_category?.["stolen_vehicle"] ?? 0, tone: "text-red-400" },
          { label: "WANTED", value: stats.data?.by_category?.["wanted"] ?? 0, tone: "text-amber-400" },
        ].map((s) => (
          <div
            key={s.label}
            className="rounded-md border border-border/60 bg-card/60 p-4"
          >
            <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
              {s.label}
            </p>
            <p className={cn("mt-1 font-mono text-2xl font-bold tabular-nums", s.tone)}>
              {s.value}
            </p>
          </div>
        ))}
      </div>

      <div className="mt-4 grid gap-4">
        <Panel
          title="Flagged Identifiers"
          subtitle="active watchlist"
          bodyClassName="p-3 flex flex-col gap-3"
        >
          {/* Filters */}
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative flex-1 basis-64">
              <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search plate / notes..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && setQuery(search)}
                className="pl-8 font-mono"
              />
            </div>
            <Select value={category} onValueChange={setCategory}>
              <SelectTrigger className="w-auto font-mono text-[11px] uppercase tracking-widest">
                <SelectValue placeholder="Category" />
              </SelectTrigger>
              <SelectContent>
                {CATEGORY_OPTIONS.map((o) => (
                  <SelectItem key={o.value} value={o.value}>
                    {o.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={source} onValueChange={setSource}>
              <SelectTrigger className="w-auto font-mono text-[11px] uppercase tracking-widest">
                <SelectValue placeholder="Source" />
              </SelectTrigger>
              <SelectContent>
                {SOURCE_OPTIONS.map((o) => (
                  <SelectItem key={o.value} value={o.value}>
                    {o.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <button
              onClick={() => setActiveOnly((v) => !v)}
              className={cn(
                "rounded-md border px-3 py-2 font-mono text-[11px] uppercase tracking-widest transition-colors",
                activeOnly
                  ? "border-primary/50 bg-primary/10 text-primary"
                  : "border-border/60 text-muted-foreground hover:text-foreground",
              )}
            >
              Active only
            </button>
          </div>

          {/* Table */}
          {isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="h-12 animate-pulse rounded-md bg-card/40" />
              ))}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-border/60 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                    <th className="pb-2 pr-4">Identifier</th>
                    <th className="pb-2 pr-4">Type</th>
                    <th className="pb-2 pr-4">Category</th>
                    <th className="pb-2 pr-4">Source</th>
                    <th className="pb-2 pr-4">Status</th>
                    <th className="pb-2 pr-4">Notes</th>
                    <th className="pb-2 pr-4">Added</th>
                    <th className="pb-2 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {entries.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="py-8 text-center font-mono text-xs text-muted-foreground">
                        No watchlist entries. Add a flagged vehicle or person above.
                      </td>
                    </tr>
                  ) : (
                    entries.map((entry) => (
                      <tr
                        key={entry.id}
                        className={cn(
                          "border-b border-border/40 text-sm transition-colors hover:bg-accent/40",
                          !entry.active && "opacity-50",
                        )}
                      >
                        <td className="py-3 pr-4 font-mono text-primary">
                          {entry.identifier_number}
                        </td>
                        <td className="py-3 pr-4">
                          <Badge variant="outline" className="font-mono text-[9px] uppercase">
                            {WATCHLIST_TARGET_LABELS[entry.target_type]}
                          </Badge>
                        </td>
                        <td className="py-3 pr-4">
                          <Badge variant="outline" className={cn("font-mono text-[9px] uppercase", categoryTone(entry.category))}>
                            {WATCHLIST_CATEGORY_LABELS[entry.category]}
                          </Badge>
                        </td>
                        <td className="py-3 pr-4">
                          <Badge variant="outline" className="font-mono text-[9px] uppercase">
                            {WATCHLIST_SOURCE_LABELS[entry.source_db]}
                          </Badge>
                        </td>
                        <td className="py-3 pr-4">
                          <span className={cn(
                            "font-mono text-[10px] uppercase tracking-widest",
                            entry.active ? "text-success" : "text-muted-foreground",
                          )}>
                            {entry.active ? "ACTIVE" : "INACTIVE"}
                          </span>
                        </td>
                        <td className="max-w-48 truncate py-3 pr-4 text-xs text-muted-foreground">
                          {entry.notes ?? "—"}
                        </td>
                        <td className="py-3 pr-4 font-mono text-[11px] text-muted-foreground">
                          {new Date(entry.added_at).toLocaleDateString()}
                        </td>
                        <td className="py-3 text-right">
                          <div className="flex justify-end gap-1.5">
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 font-mono text-[10px]"
                              onClick={() => handleExport(entry.identifier_number)}
                              disabled={exportingId !== null}
                              title="Export court-admissible evidence dossier (PDF)"
                            >
                              <FileDown className="h-3 w-3 text-[#ffdd00]" />
                              {exportingId === entry.identifier_number
                                ? "…"
                                : "DOSSIER"}
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 font-mono text-[10px]"
                              onClick={() => setEditTarget(entry)}
                            >
                              EDIT
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 font-mono text-[10px] text-destructive hover:text-destructive"
                              onClick={() => setDeleteTarget(entry)}
                            >
                              DEL
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      </div>

      <WatchlistFormSheet
        open={createOpen}
        onOpenChange={setCreateOpen}
      />
      {editTarget && (
        <WatchlistFormSheet
          open
          entry={editTarget}
          onOpenChange={(open) => !open && setEditTarget(null)}
        />
      )}
      <AlertDialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove watchlist entry?</AlertDialogTitle>
            <AlertDialogDescription>
              {deleteTarget?.identifier_number} will no longer trigger ANPR alerts.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete} className="bg-destructive text-destructive-foreground">
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}