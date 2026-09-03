"use client";

import { useState } from "react";
import {
  Crosshair,
  Eye,
  Pencil,
  ScanSearch,
  Trash2,
} from "lucide-react";
import type { Camera } from "@sentinel/shared";

import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/cameras/status-badge";
import { cn, timeAgo } from "@/lib/utils";

export interface CameraTableActions {
  onView: (camera: Camera) => void;
  onEdit: (camera: Camera) => void;
  onTest: (camera: Camera) => void;
  onDelete: (camera: Camera) => void;
}

export function CameraTable({
  cameras,
  loading,
  actions,
}: {
  cameras: Camera[];
  loading: boolean;
  actions: CameraTableActions;
}) {
  const [expanded, setExpanded] = useState<string | null>(null);

  if (loading) {
    return (
      <div className="space-y-2 p-4">
        {Array.from({ length: 8 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full rounded-md" />
        ))}
      </div>
    );
  }

  if (!cameras.length) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
        <ScanSearch className="h-10 w-10 text-muted-foreground/40" />
        <p className="font-mono text-sm uppercase tracking-widest text-muted-foreground">
          No sensors in this view
        </p>
        <p className="text-xs text-muted-foreground/70">
          Adjust filters or register a new camera.
        </p>
      </div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead className="font-mono text-[10px] uppercase tracking-widest">
            Designation
          </TableHead>
          <TableHead className="font-mono text-[10px] uppercase tracking-widest">
            Location
          </TableHead>
          <TableHead className="hidden font-mono text-[10px] uppercase tracking-widest md:table-cell">
            Coordinates
          </TableHead>
          <TableHead className="font-mono text-[10px] uppercase tracking-widest">
            Status
          </TableHead>
          <TableHead className="hidden font-mono text-[10px] uppercase tracking-widest lg:table-cell">
            Last Signal
          </TableHead>
          <TableHead className="w-10" />
        </TableRow>
      </TableHeader>
      <TableBody>
        {cameras.map((camera) => (
          <TableRow
            key={camera.id}
            className="group cursor-pointer"
            onClick={() => actions.onView(camera)}
          >
            <TableCell className="font-mono text-sm font-semibold">
              <span className="flex items-center gap-2">
                {camera.name}
                {camera.status === "online" && (
                  <span className="h-1.5 w-1.5 rounded-full bg-success radar-pulse" />
                )}
              </span>
            </TableCell>
            <TableCell className="max-w-[220px] truncate text-xs text-muted-foreground">
              {camera.location}
            </TableCell>
            <TableCell className="hidden font-mono text-xs text-muted-foreground md:table-cell">
              {camera.latitude.toFixed(4)}, {camera.longitude.toFixed(4)}
            </TableCell>
            <TableCell>
              <StatusBadge status={camera.status} />
            </TableCell>
            <TableCell className="hidden font-mono text-xs text-muted-foreground lg:table-cell">
              {camera.last_seen_at ? timeAgo(camera.last_seen_at) : "—"}
            </TableCell>
            <TableCell
              className="text-right"
              onClick={(e) => e.stopPropagation()}
            >
              <DropdownMenu
                open={expanded === camera.id}
                onOpenChange={(o) => setExpanded(o ? camera.id : null)}
              >
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className={cn(
                      "h-8 w-8 opacity-0 transition-opacity group-hover:opacity-100",
                      expanded === camera.id && "opacity-100",
                    )}
                    onClick={(e) => e.preventDefault()}
                  >
                    <span className="sr-only">Actions</span>
                    <span className="text-muted-foreground">•••</span>
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem
                    onClick={() => actions.onView(camera)}
                  >
                    <Eye className="h-4 w-4" /> View live
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => actions.onEdit(camera)}>
                    <Pencil className="h-4 w-4" /> Edit sensor
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => actions.onTest(camera)}>
                    <Crosshair className="h-4 w-4" /> Run connectivity probe
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    className="text-destructive focus:text-destructive"
                    onClick={() => actions.onDelete(camera)}
                  >
                    <Trash2 className="h-4 w-4" /> Remove
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}