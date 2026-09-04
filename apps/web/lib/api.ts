"use client";

import type { TokenPair } from "@sentinel/shared";
import { tokenStore } from "./token-store";

/** Typed API error carrying the HTTP status and backend detail payload. */
export class ApiError extends Error {
  status: number;
  detail: unknown;
  requestId?: string;

  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = typeof detail === "string" ? detail : detail;
  }
}

function inferMessage(payload: unknown, status: number): string {
  if (payload && typeof payload === "object") {
    const detail = (payload as Record<string, unknown>).detail;
    if (Array.isArray(detail)) {
      const first = detail[0] as Record<string, unknown> | undefined;
      if (first?.msg) return String(first.msg);
    }
    if (typeof detail === "string") return detail;
    if (typeof (payload as Record<string, unknown>).message === "string") {
      return String((payload as Record<string, unknown>).message);
    }
  }
  return `Request failed with status ${status}.`;
}

async function readBody(res: Response): Promise<unknown> {
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

/* Single-flight refresh so a burst of 401s triggers exactly one rotation. */
let refreshing: Promise<boolean> | null = null;

async function tryRefresh(): Promise<boolean> {
  if (!refreshing) {
    refreshing = (async () => {
      const res = await fetch("/api/v1/auth/refresh", { method: "POST" });
      if (!res.ok) return false;
      const pair = (await res.json()) as TokenPair;
      tokenStore.set(pair.access_token);
      return true;
    })().finally(() => {
      refreshing = null;
    });
  }
  return refreshing;
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  /** skip auth header + auto-refresh (default: true) */
  auth?: boolean;
}

export async function apiFetch<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { method = "GET", body, auth = true } = options;

  const headers: Record<string, string> = { accept: "application/json" };
  const token = tokenStore.get();
  if (token) headers.authorization = `Bearer ${token}`;
  if (body !== undefined) headers["content-type"] = "application/json";

  const doFetch = async (): Promise<Response> =>
    fetch(path, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      credentials: "same-origin",
    });

  let res = await doFetch();

  if (res.status === 401 && auth) {
    const refreshed = await tryRefresh();
    if (refreshed) {
      const fresh = tokenStore.get();
      if (fresh) headers.authorization = `Bearer ${fresh}`;
      res = await doFetch();
    }
  }

  if (res.status === 204) return undefined as T;

  const payload = await readBody(res);
  if (!res.ok) {
    const message = inferMessage(payload, res.status);
    const err = new ApiError(res.status, message, payload);
    const requestId = res.headers.get("x-request-id");
    if (requestId) err.requestId = requestId;
    throw err;
  }
  return payload as T;
}

/** Convenience client with typed helpers. */
export const api = {
  get: <T>(path: string, opts?: RequestOptions) =>
    apiFetch<T>(path, { ...opts, method: "GET" }),
  post: <T>(path: string, body?: unknown, opts?: RequestOptions) =>
    apiFetch<T>(path, { ...opts, method: "POST", body }),
  patch: <T>(path: string, body?: unknown, opts?: RequestOptions) =>
    apiFetch<T>(path, { ...opts, method: "PATCH", body }),
  delete: <T>(path: string, opts?: RequestOptions) =>
    apiFetch<T>(path, { ...opts, method: "DELETE" }),
};

export const endpoints = {
  login: "/api/v1/auth/login",
  refresh: "/api/v1/auth/refresh",
  logout: "/api/v1/auth/logout",
  me: "/api/v1/auth/me",
  changePassword: "/api/v1/auth/change-password",
  cameras: "/api/v1/cameras",
  camera: (id: string) => `/api/v1/cameras/${id}`,
  cameraTest: (id: string) => `/api/v1/cameras/${id}/test`,
  cameraHealth: (id: string) => `/api/v1/cameras/${id}/health`,
  streams: "/api/v1/streams",
  streamConfig: "/api/v1/streams/config",
  streamRecordings: "/api/v1/streams/recordings",
  onvifDiscover: "/api/v1/streams/devices/discover",
  streamHealth: (id: string) => `/api/v1/streams/${id}/health`,
  streamStats: (id: string) => `/api/v1/streams/${id}/stats`,
  streamMedia: (id: string) => `/api/v1/streams/${id}/media`,
  streamStart: (id: string) => `/api/v1/streams/${id}/start`,
  streamStop: (id: string) => `/api/v1/streams/${id}/stop`,
  streamTest: (id: string) => `/api/v1/streams/${id}/test`,
  streamRecordStart: (id: string) => `/api/v1/streams/${id}/record/start`,
  streamRecordStop: (id: string) => `/api/v1/streams/${id}/record/stop`,
  alerts: "/api/v1/alerts",
  alertStats: "/api/v1/alerts/stats",
  alert: (id: string) => `/api/v1/alerts/${id}`,
  incidents: "/api/v1/incidents",
  incident: (id: string) => `/api/v1/incidents/${id}`,
  dashboardSummary: "/api/v1/dashboard/summary",
  health: "/api/v1/health",
  // --- Phase 3: AI inference ---
  inferenceConfig: "/api/v1/inference/config",
  inferenceModels: "/api/v1/inference/models",
  inferenceModel: (name: string) => `/api/v1/inference/models/${encodeURIComponent(name)}`,
  inferenceModelLoad: (name: string) => `/api/v1/inference/models/${encodeURIComponent(name)}/load`,
  inferenceModelReload: (name: string) => `/api/v1/inference/models/${encodeURIComponent(name)}/reload`,
  inferenceModelUnload: (name: string) => `/api/v1/inference/models/${encodeURIComponent(name)}/unload`,
  inferenceModelHealth: (name: string) => `/api/v1/inference/models/${encodeURIComponent(name)}/health`,
  inferenceInfer: "/api/v1/inference/infer",
  inferenceCameraStatus: (id: string) => `/api/v1/inference/cameras/${id}/status`,
  inferenceCameraStats: (id: string) => `/api/v1/inference/cameras/${id}/stats`,
  inferenceCameraStart: (id: string) => `/api/v1/inference/cameras/${id}/start`,
  inferenceCameraStop: (id: string) => `/api/v1/inference/cameras/${id}/stop`,
  inferenceOverlayLast: (id: string) => `/api/v1/inference/cameras/${id}/overlay/last`,
  inferenceRuns: "/api/v1/inference/runs",
  inferenceDetections: "/api/v1/inference/detections",
  inferenceAlerts: "/api/v1/inference/alerts",
  inferenceAlertResolve: (id: string) => `/api/v1/inference/alerts/${id}/resolve`,
  inferenceSummary: "/api/v1/inference/summary",
  inferenceBenchmark: "/api/v1/inference/benchmark",
  inferenceWs: (token: string) =>
    `/api/v1/ws/inference?token=${encodeURIComponent(token)}&channels=overlay,stats,alert`,
  // --- Phase 6.1: IAM (federation) ---
  iamSession: "/api/v1/iam/auth/session",
  iamDepartments: "/api/v1/iam/departments",
  iamDepartmentTree: "/api/v1/iam/departments/tree",
  iamDepartment: (id: string) => `/api/v1/iam/departments/${id}`,
  iamOfficers: "/api/v1/iam/officers",
  iamOfficer: (id: string) => `/api/v1/iam/officers/${id}`,
  iamOfficerStatus: (id: string) => `/api/v1/iam/officers/${id}/status`,
  iamOfficerRole: (id: string) => `/api/v1/iam/officers/${id}/role`,
  iamRoles: "/api/v1/iam/roles",
  iamRolePermissions: (id: string) => `/api/v1/iam/roles/${id}/permissions`,
  iamPermissions: "/api/v1/iam/permissions",
  iamPermissionCatalog: "/api/v1/iam/permissions/catalog",
  iamAudit: "/api/v1/iam/audit",
  iamEmergency: "/api/v1/iam/emergency",
  iamEmergencyRequest: "/api/v1/iam/emergency/request",
  iamEmergencyApprove: (id: string) => `/api/v1/iam/emergency/${id}/approve`,
  iamEmergencyActivate: (id: string) => `/api/v1/iam/emergency/${id}/activate`,
  iamEmergencyRevoke: (id: string) => `/api/v1/iam/emergency/${id}/revoke`,
  iamSessions: "/api/v1/iam/sessions",
  iamSessionRevoke: (id: string) => `/api/v1/iam/sessions/${id}/revoke`,
  iamSessionsRevokeAll: "/api/v1/iam/sessions/revoke-all",
  // --- Watchlists ---
  watchlists: "/api/v1/watchlists",
  watchlist: (id: string) => `/api/v1/watchlists/${id}`,
  watchlistStats: "/api/v1/watchlists/stats",
  watchlistLookup: (plate: string) => `/api/v1/watchlists/lookup/${encodeURIComponent(plate)}`,
  // --- Vehicle Intelligence ---
  vehicleIntelSearch: "/api/v1/vehicle-intel/investigate",
  vehicleIntelRoute: "/api/v1/vehicle-intel/route/reconstruct",
  vehicleIntelTimeline: "/api/v1/vehicle-intel/timeline",
  vehicleIntelIdentity: "/api/v1/vehicle-intel/identity",
  // --- Phase 7 killer features: forensics + interception ---
  vehicleDossier: (plate: string) =>
    `/api/v1/vehicles/${encodeURIComponent(plate)}/dossier`,
  vehicleDossierVerify: (plate: string) =>
    `/api/v1/vehicles/${encodeURIComponent(plate)}/dossier/verify`,
  vehicleInterception: (plate: string) =>
    `/api/v1/vehicles/${encodeURIComponent(plate)}/interception`,
};

/**
 * Download a forensic dossier (PDF or Markdown) as a browser file download.
 * Returns the integrity hash reported by the server so callers can display
 * the court-admissible SHA-256 alongside the saved artifact.
 */
export async function downloadDossier(
  plate: string,
  format: "pdf" | "markdown" = "pdf",
): Promise<string | null> {
  const auth = tokenStore.get();
  const headers: Record<string, string> = {};
  if (auth) headers.authorization = `Bearer ${auth}`;

  const res = await fetch(endpoints.vehicleDossier(plate) + `?format=${format}`, {
    headers,
    credentials: "same-origin",
  });
  if (!res.ok) {
    const err = new ApiError(
      res.status,
      `Dossier export failed with status ${res.status}.`,
    );
    throw err;
  }

  const integrity = res.headers.get("x-dossier-integrity");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const ext = format === "pdf" ? "pdf" : "md";
  const a = document.createElement("a");
  a.href = url;
  a.download = `dossier_${plate.replace(/[^A-Za-z0-9]/g, "")}.${ext}`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
  return integrity;
}