"use client";

import { useMemo, useState } from "react";
import { Plus, RefreshCw, Search } from "lucide-react";
import { toast } from "sonner";
import type { Camera, CameraStatus } from "@sentinel/shared";
import { CAMERA_STATUS } from "@sentinel/shared";

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
import { CameraTable } from "@/components/cameras/camera-table";
import { CameraFormSheet } from "@/components/cameras/camera-form-sheet";
import { CameraTestDialog } from "@/components/cameras/camera-test-dialog";
import { CameraDetailsDialog } from "@/components/cameras/camera-details-dialog";
import { useCameras, useDeleteCamera } from "@/lib/queries";
import { statusMeta } from "@/lib/status";
import { cn } from "@/lib/utils";

const STATUS_OPTIONS = [
  { value: "all", label: "ALL" },
  { value: CAMERA_STATUS.ONLINE, label: "ONLINE" },
  { value: CAMERA_STATUS.OFFLINE, label: "OFFLINE" },
  { value: CAMERA_STATUS.MAINTENANCE, label: "MAINTENANCE" },
  { value: CAMERA_STATUS.UNKNOWN, label: "UNKNOWN" },
] as const;

export default function CamerasPage() {
  const [status, setStatus] = useState<string>("all");
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");

  const [createOpen, setCreateOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<Camera | null>(null);
  const [viewTarget, setViewTarget] = useState<Camera | null>(null);
  const [testTarget, setTestTarget] = useState<Camera | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Camera | null>(null);

  const { data, isLoading, refetch, isFetching } = useCameras({
    status: status === "all" ? undefined : status,
    search: query || undefined,
    pageSize: 100,
  });

  const deleteCamera = useDeleteCamera();

  const cameras = useMemo(() => data?.items ?? [], [data]);
  const counts = useMemo(() => {
    const by: { [k: string]: number } = {};
    for (const c of cameras) by[c.status] = (by[c.status] ?? 0) + 1;
    return by;
  }, [cameras]);

  async function handleDelete() {
    if (!deleteTarget) return;
    try {
      await deleteCamera.mutateAsync(deleteTarget.id);
      toast.success(`Camera ${deleteTarget.name} removed from grid.`);
      setDeleteTarget(null);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Delete failed.");
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Sensor Inventory"
        title="Cameras"
        description={`${cameras.length} registered sensors · ${counts[CAMERA_STATUS.ONLINE] ?? 0} online`}
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
              Register Camera
            </Button>
          </>
        }
      />

      {/* Filter bar */}
      <Panel bodyClassName="flex flex-wrap items-center gap-3 p-3">
        <div className="relative w-full max-w-xs">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search designation / location…"
            className="pl-9 font-mono text-xs"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") setQuery(search.trim());
            }}
          />
        </div>
        <Select value={status} onValueChange={setStatus}>
          <SelectTrigger className="w-40 font-mono text-xs uppercase">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {STATUS_OPTIONS.map((o) => (
              <SelectItem key={o.value} value={o.value} className="font-mono uppercase">
                {o.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <div className="ml-auto flex flex-wrap gap-1.5">
          {STATUS_OPTIONS.filter((o) => o.value !== "all").map((o) => {
            const meta =
              statusMeta.camera[o.value as CameraStatus] ??
              statusMeta.camera.unknown;
            return (
              <Badge
                key={o.value}
                variant="outline"
                className="gap-1.5 font-mono text-[9px] uppercase tracking-wider"
              >
                <span className={cn("h-1.5 w-1.5 rounded-full", meta.dot)} />
                {o.label} · {counts[o.value] ?? 0}
              </Badge>
            );
          })}
        </div>
      </Panel>

      {/* Camera table */}
      <div className="mt-5">
        <Panel bodyClassName="overflow-x-auto p-0">
          <CameraTable
            cameras={cameras}
            loading={isLoading}
            actions={{
              onView: setViewTarget,
              onEdit: setEditTarget,
              onTest: setTestTarget,
              onDelete: setDeleteTarget,
            }}
          />
        </Panel>
      </div>

      {/* Actions */}
      <CameraFormSheet open={createOpen} onOpenChange={setCreateOpen} />
      <CameraFormSheet
        open={Boolean(editTarget)}
        onOpenChange={(o) => {
          if (!o) setEditTarget(null);
        }}
        camera={editTarget}
      />
      <CameraDetailsDialog
        camera={viewTarget}
        open={Boolean(viewTarget)}
        onOpenChange={(o) => {
          if (!o) setViewTarget(null);
        }}
      />
      <CameraTestDialog
        camera={testTarget}
        open={Boolean(testTarget)}
        onOpenChange={(o) => {
          if (!o) setTestTarget(null);
        }}
      />
      <AlertDialog
        open={Boolean(deleteTarget)}
        onOpenChange={(o) => {
          if (!o) setDeleteTarget(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="font-mono">
              Remove sensor {deleteTarget?.name}?
            </AlertDialogTitle>
            <AlertDialogDescription>
              This permanently removes the camera from the grid. Its alert and
              incident history is retained.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => {
                e.preventDefault();
                void handleDelete();
              }}
              className="bg-destructive font-mono uppercase tracking-widest text-destructive-foreground hover:bg-destructive/90"
              disabled={deleteCamera.isPending}
            >
              {deleteCamera.isPending ? "Removing…" : "Remove"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}