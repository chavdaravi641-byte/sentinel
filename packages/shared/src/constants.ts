/**
 * Shared domain constants for Sentinel AI.
 * Mirrors the enums defined in the FastAPI backend (src/models).
 * Keep in sync with apps/api/src/models/*.py
 */

export const CAMERA_STATUS = {
  ONLINE: "online",
  OFFLINE: "offline",
  MAINTENANCE: "maintenance",
  UNKNOWN: "unknown",
} as const;

export type CameraStatus = (typeof CAMERA_STATUS)[keyof typeof CAMERA_STATUS];

export const ALERT_TYPE = {
  MOTION: "motion",
  INTRUSION: "intrusion",
  LOITERING: "loitering",
  CROWD: "crowd",
  ABANDONED_OBJECT: "abandoned_object",
  LICENSE_PLATE: "license_plate",
  SUSPICIOUS_BEHAVIOR: "suspicious_behavior",
  UNKNOWN: "unknown",
} as const;

export type AlertType = (typeof ALERT_TYPE)[keyof typeof ALERT_TYPE];

export const ALERT_SEVERITY = {
  CRITICAL: "critical",
  HIGH: "high",
  MEDIUM: "medium",
  LOW: "low",
  INFO: "info",
} as const;

export type AlertSeverity = (typeof ALERT_SEVERITY)[keyof typeof ALERT_SEVERITY];

export const ALERT_STATUS = {
  NEW: "new",
  ACKNOWLEDGED: "acknowledged",
  ESCALATED: "escalated",
  RESOLVED: "resolved",
} as const;

export type AlertStatus = (typeof ALERT_STATUS)[keyof typeof ALERT_STATUS];

export const INCIDENT_TYPE = {
  THEFT: "theft",
  ASSAULT: "assault",
  TRAFFIC: "traffic",
  FIRE: "fire",
  MISSING_PERSON: "missing_person",
  SUSPICIOUS_ACTIVITY: "suspicious_activity",
  VANDALISM: "vandalism",
  OTHER: "other",
} as const;

export type IncidentType = (typeof INCIDENT_TYPE)[keyof typeof INCIDENT_TYPE];

export const INCIDENT_STATUS = {
  OPEN: "open",
  IN_PROGRESS: "in_progress",
  CLOSED: "closed",
} as const;

export type IncidentStatus = (typeof INCIDENT_STATUS)[keyof typeof INCIDENT_STATUS];

export const USER_ROLE = {
  ADMIN: "admin",
  OPERATOR: "operator",
  VIEWER: "viewer",
} as const;

export type UserRole = (typeof USER_ROLE)[keyof typeof USER_ROLE];

export const ALERT_TYPE_LABELS: Record<AlertType, string> = {
  motion: "Motion Detected",
  intrusion: "Perimeter Intrusion",
  loitering: "Loitering",
  crowd: "Crowd Formation",
  abandoned_object: "Abandoned Object",
  license_plate: "License Plate Match",
  suspicious_behavior: "Suspicious Behavior",
  unknown: "Unknown",
};

export const CAMERA_STATUS_LABELS: Record<CameraStatus, string> = {
  online: "Online",
  offline: "Offline",
  maintenance: "Maintenance",
  unknown: "Unknown",
};

export const INCIDENT_TYPE_LABELS: Record<IncidentType, string> = {
  theft: "Theft",
  assault: "Assault",
  traffic: "Traffic Violation",
  fire: "Fire",
  missing_person: "Missing Person",
  suspicious_activity: "Suspicious Activity",
  vandalism: "Vandalism",
  other: "Other",
};

/** Phase 3 — the six approved detection classes (YOLOv12 person/car/bike/bus/truck/bicycle). */
export const SENTINEL_CLASSES = [
  "person",
  "car",
  "bike",
  "bus",
  "truck",
  "bicycle",
] as const;

export type SentinelClass = (typeof SENTINEL_CLASSES)[number];

export const INFERENCE_WS_PATH = "/api/v1/ws/inference";
export const ANPR_WS_PATH = "/api/v1/ws/anpr";

export const CLIENT_VERSION = "1.0.0";

/* ---------------------------------------------------------------------------
 * Watchlists
 * ------------------------------------------------------------------------- */

export const WATCHLIST_TARGET_TYPE = {
  VEHICLE: "vehicle",
  PERSON: "person",
} as const;

export type WatchlistTargetType =
  (typeof WATCHLIST_TARGET_TYPE)[keyof typeof WATCHLIST_TARGET_TYPE];

export const WATCHLIST_CATEGORY = {
  STOLEN_VEHICLE: "stolen_vehicle",
  WANTED: "wanted",
  MISSING: "missing",
  UNINSURED: "uninsured",
  BLACKLISTED: "blacklisted",
  SUSPECT: "suspect",
  OTHER: "other",
} as const;

export type WatchlistCategory =
  (typeof WATCHLIST_CATEGORY)[keyof typeof WATCHLIST_CATEGORY];

export const WATCHLIST_SOURCE_DB = {
  VAHAN: "vahan",
  EGUJCOP: "egujcop",
  SARTHI: "sarthi",
  INTERNAL: "internal",
  MANUAL: "manual",
} as const;

export type WatchlistSourceDB =
  (typeof WATCHLIST_SOURCE_DB)[keyof typeof WATCHLIST_SOURCE_DB];

export const WATCHLIST_CATEGORY_LABELS: Record<WatchlistCategory, string> = {
  stolen_vehicle: "Stolen Vehicle",
  wanted: "Wanted",
  missing: "Missing",
  uninsured: "Uninsured",
  blacklisted: "Blacklisted",
  suspect: "Suspect",
  other: "Other",
};

export const WATCHLIST_SOURCE_LABELS: Record<WatchlistSourceDB, string> = {
  vahan: "VAHAN",
  egujcop: "eGujCop",
  sarthi: "SARTHI",
  internal: "Internal",
  manual: "Manual",
};

export const WATCHLIST_TARGET_LABELS: Record<WatchlistTargetType, string> = {
  vehicle: "Vehicle",
  person: "Person",
};