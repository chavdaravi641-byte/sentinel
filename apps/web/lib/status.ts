"use client";

import type {
  AlertSeverity,
  AlertStatus,
  AlertType,
  CameraStatus,
  IncidentStatus,
  IncidentType,
  StreamState,
} from "@sentinel/shared";
import {
  ALERT_SEVERITY,
  ALERT_STATUS,
  CAMERA_STATUS,
  INCIDENT_STATUS,
} from "@sentinel/shared";

/* Status → presentation metadata (labels + phosphor colors). */

interface StatusMeta {
  label: string;
  /** Tailwind text color class */
  text: string;
  /** Tailwind background/border color class */
  badge: string;
  /** dot color */
  dot: string;
}

const cameraMeta: Record<CameraStatus, StatusMeta> = {
  [CAMERA_STATUS.ONLINE]: {
    label: "ONLINE",
    text: "text-emerald-400",
    badge: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
    dot: "bg-emerald-400",
  },
  [CAMERA_STATUS.OFFLINE]: {
    label: "OFFLINE",
    text: "text-rose-400",
    badge: "border-rose-500/30 bg-rose-500/10 text-rose-300",
    dot: "bg-rose-500",
  },
  [CAMERA_STATUS.MAINTENANCE]: {
    label: "MAINTENANCE",
    text: "text-amber-400",
    badge: "border-amber-500/30 bg-amber-500/10 text-amber-300",
    dot: "bg-amber-400",
  },
  [CAMERA_STATUS.UNKNOWN]: {
    label: "UNKNOWN",
    text: "text-slate-400",
    badge: "border-slate-500/30 bg-slate-500/10 text-slate-300",
    dot: "bg-slate-400",
  },
};

const severityMeta: Record<AlertSeverity, StatusMeta> = {
  [ALERT_SEVERITY.CRITICAL]: {
    label: "CRITICAL",
    text: "text-rose-400",
    badge: "border-rose-500/40 bg-rose-500/10 text-rose-300",
    dot: "bg-rose-500",
  },
  [ALERT_SEVERITY.HIGH]: {
    label: "HIGH",
    text: "text-orange-400",
    badge: "border-orange-500/40 bg-orange-500/10 text-orange-300",
    dot: "bg-orange-400",
  },
  [ALERT_SEVERITY.MEDIUM]: {
    label: "MEDIUM",
    text: "text-amber-400",
    badge: "border-amber-500/40 bg-amber-500/10 text-amber-300",
    dot: "bg-amber-300",
  },
  [ALERT_SEVERITY.LOW]: {
    label: "LOW",
    text: "text-sky-400",
    badge: "border-sky-500/40 bg-sky-500/10 text-sky-300",
    dot: "bg-sky-400",
  },
  [ALERT_SEVERITY.INFO]: {
    label: "INFO",
    text: "text-slate-400",
    badge: "border-slate-500/40 bg-slate-500/10 text-slate-300",
    dot: "bg-slate-400",
  },
};

const alertStatusMeta: Record<AlertStatus, StatusMeta> = {
  [ALERT_STATUS.NEW]: {
    label: "NEW",
    text: "text-cyan-300",
    badge: "border-cyan-500/40 bg-cyan-500/10 text-cyan-200",
    dot: "bg-cyan-300",
  },
  [ALERT_STATUS.ACKNOWLEDGED]: {
    label: "ACK",
    text: "text-sky-300",
    badge: "border-sky-500/40 bg-sky-500/10 text-sky-200",
    dot: "bg-sky-300",
  },
  [ALERT_STATUS.ESCALATED]: {
    label: "ESCALATED",
    text: "text-orange-300",
    badge: "border-orange-500/40 bg-orange-500/10 text-orange-200",
    dot: "bg-orange-300",
  },
  [ALERT_STATUS.RESOLVED]: {
    label: "RESOLVED",
    text: "text-slate-400",
    badge: "border-slate-500/30 bg-slate-500/10 text-slate-300",
    dot: "bg-slate-500/70",
  },
};

const streamMeta: Record<StreamState, StatusMeta> = {
  running: {
    label: "RUNNING",
    text: "text-emerald-400",
    badge: "border-emerald-500/40 bg-emerald-500/10 text-emerald-300",
    dot: "bg-emerald-400",
  },
  connecting: {
    label: "CONNECTING",
    text: "text-amber-400",
    badge: "border-amber-500/40 bg-amber-500/10 text-amber-300",
    dot: "bg-amber-400",
  },
  starting: {
    label: "STARTING",
    text: "text-sky-400",
    badge: "border-sky-500/40 bg-sky-500/10 text-sky-300",
    dot: "bg-sky-400",
  },
  error: {
    label: "ERROR",
    text: "text-rose-400",
    badge: "border-rose-500/40 bg-rose-500/10 text-rose-300",
    dot: "bg-rose-500",
  },
  stopped: {
    label: "STOPPED",
    text: "text-slate-400",
    badge: "border-slate-500/30 bg-slate-500/10 text-slate-300",
    dot: "bg-slate-400",
  },
  idle: {
    label: "IDLE",
    text: "text-slate-400",
    badge: "border-slate-500/30 bg-slate-500/10 text-slate-300",
    dot: "bg-slate-400",
  },
};

const incidentStatusMeta: Record<IncidentStatus, StatusMeta> = {
  [INCIDENT_STATUS.OPEN]: {
    label: "OPEN",
    text: "text-rose-300",
    badge: "border-rose-500/40 bg-rose-500/10 text-rose-200",
    dot: "bg-rose-400",
  },
  [INCIDENT_STATUS.IN_PROGRESS]: {
    label: "IN PROGRESS",
    text: "text-amber-300",
    badge: "border-amber-500/40 bg-amber-500/10 text-amber-200",
    dot: "bg-amber-300",
  },
  [INCIDENT_STATUS.CLOSED]: {
    label: "CLOSED",
    text: "text-slate-400",
    badge: "border-slate-500/30 bg-slate-500/10 text-slate-300",
    dot: "bg-slate-500/70",
  },
};

export const statusMeta = {
  camera: cameraMeta,
  severity: severityMeta,
  alert: alertStatusMeta,
  incident: incidentStatusMeta,
  stream: streamMeta,
};

/* Human labels for enums (mirror @sentinel/shared). */
export const alertTypeLabel: Record<AlertType, string> = {
  motion: "Motion",
  intrusion: "Perimeter Intrusion",
  loitering: "Loitering",
  crowd: "Crowd Formation",
  abandoned_object: "Abandoned Object",
  license_plate: "License Plate",
  suspicious_behavior: "Suspicious Behaviour",
  unknown: "Unknown",
};

export const incidentTypeLabel: Record<IncidentType, string> = {
  theft: "Theft",
  assault: "Assault",
  traffic: "Traffic",
  fire: "Fire",
  missing_person: "Missing Person",
  suspicious_activity: "Suspicious Activity",
  vandalism: "Vandalism",
  other: "Other",
};