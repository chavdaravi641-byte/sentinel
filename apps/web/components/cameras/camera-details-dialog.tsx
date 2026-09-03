"use client";

import { MapPin, Radio, Server, Video } from "lucide-react";
import type { Camera } from "@sentinel/shared";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { LivePlayer } from "@/components/cameras/live-player";
import { StatusBadge } from "@/components/cameras/status-badge";
import { formatDateTime, timeAgo } from "@/lib/utils";

function DetailRow({
  icon,
  label,
  value,
}: {
  icon?: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-center gap-3 border-b border-border/60 py-2.5 font-mono text-xs last:border-0">
      {icon}
      <span className="w-32 uppercase tracking-widest text-muted-foreground">
        {label}
      </span>
      <span className="break-all text-foreground">{value}</span>
    </div>
  );
}

export function CameraDetailsDialog({
  camera,
  open,
  onOpenChange,
}: {
  camera: Camera | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 font-mono">
            <Video className="h-4 w-4 text-primary" />
            {camera?.name}
          </DialogTitle>
          <DialogDescription className="flex items-center gap-2">
            Sensor dossier
            {camera && <StatusBadge status={camera.status} />}
          </DialogDescription>
        </DialogHeader>

        {camera && (
          <div className="grid gap-4 sm:grid-cols-2">
            <LivePlayer
              cameraName={camera.name}
              muted
              playing={camera.status === "online"}
              className="aspect-video rounded-md border border-border"
            />

            <div className="space-y-1 rounded-md border border-border/60 bg-card/60 p-3">
              <DetailRow
                icon={<Server className="h-3.5 w-3.5 shrink-0 text-primary" />}
                label="Status"
                value={camera.status.toUpperCase()}
              />
              <DetailRow
                icon={<MapPin className="h-3.5 w-3.5 shrink-0 text-primary" />}
                label="Location"
                value={camera.location}
              />
              <DetailRow
                icon={<Radio className="h-3.5 w-3.5 shrink-0 text-primary" />}
                label="Coordinates"
                value={`${camera.latitude.toFixed(4)}, ${camera.longitude.toFixed(4)}`}
              />
              <DetailRow
                icon={<Video className="h-3.5 w-3.5 shrink-0 text-primary" />}
                label="Stream"
                value={camera.rtsp_url}
              />
              <DetailRow
                label="Registered"
                value={formatDateTime(camera.created_at)}
              />
              <DetailRow
                label="Last Signal"
                value={
                  camera.last_seen_at
                    ? `${formatDateTime(camera.last_seen_at)} (${timeAgo(camera.last_seen_at)})`
                    : "never"
                }
              />
              <DetailRow
                label="Broadcasting"
                value={
                  camera.is_active || camera.status === "online" ? "YES" : "NO"
                }
              />
            </div>
          </div>
        )}

        {camera?.description && (
          <p className="rounded-md border border-border/60 bg-card/60 p-3 font-mono text-xs leading-relaxed text-muted-foreground">
            {camera.description}
          </p>
        )}
      </DialogContent>
    </Dialog>
  );
}