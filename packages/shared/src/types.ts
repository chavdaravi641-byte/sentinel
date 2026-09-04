import type {
  AlertSeverity,
  AlertStatus,
  AlertType,
  CameraStatus,
  IncidentStatus,
  IncidentType,
  UserRole,
} from "./constants";

/* ---------------------------------------------------------------------------
 * Common
 * ------------------------------------------------------------------------- */

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface ApiErrorDetail {
  detail: string | Array<{ loc: unknown[]; msg: string; type: string }>;
}

/* ---------------------------------------------------------------------------
 * Auth / Users
 * ------------------------------------------------------------------------- */

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  last_login_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenPair {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  user: User;
}

export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}

/* ---------------------------------------------------------------------------
 * Cameras
 * ------------------------------------------------------------------------- */

export interface Camera {
  id: string;
  name: string;
  rtsp_url: string;
  location: string;
  latitude: number;
  longitude: number;
  status: CameraStatus;
  description: string | null;
  is_active: boolean;
  last_seen_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface CameraCreate {
  name: string;
  rtsp_url: string;
  location: string;
  latitude: number;
  longitude: number;
  description?: string | null;
  status?: CameraStatus;
  is_active?: boolean;
}

export interface CameraUpdate {
  name?: string;
  rtsp_url?: string;
  location?: string;
  latitude?: number;
  longitude?: number;
  description?: string | null;
  status?: CameraStatus;
  is_active?: boolean;
}

export interface CameraTestResult {
  id: string;
  name: string;
  ok: boolean;
  reachable: boolean;
  host: string | null;
  port: number | null;
  latency_ms: number | null;
  rtt_ms: number | null;
  message: string;
  tested_at: string;
}

/* ---------------------------------------------------------------------------
 * Streams
 * ------------------------------------------------------------------------- */

export type StreamState =
  | "stopped"
  | "idle"
  | "starting"
  | "connecting"
  | "running"
  | "error";

export interface StreamHealth {
  camera_id: string;
  name: string | null;
  state: StreamState;
  running: boolean;
  live: boolean;
  error: string | null;
  reconnect_count: number;
  kind: string | null;
  started_at: string | null;
  stopped_at: string | null;
  uptime_s: number | null;
  startup_ms: number | null;
  latency_ms: number | null;
  hls_latency_ms: number | null;
  fps: number | null;
  bitrate_kbps: number | null;
  jitter_ms: number | null;
  last_frame_age_ms: number | null;
  recording: boolean;
  recording_trigger: string | null;
  motion_detections: number;
  last_motion_score: number | null;
  publisher: Record<string, unknown>;
}

export interface StreamMediaUrls {
  camera_id: string;
  hls_url: string | null;
  mjpeg_url: string | null;
  snapshot_url: string | null;
  whep_url: string | null;
  expires_in: number;
  published_at: string;
}

export interface StreamTestResult {
  id: string;
  name: string;
  kind: string | null;
  ok: boolean;
  message: string;
  codec: string | null;
  width: number | null;
  height: number | null;
  fps: number | null;
  bit_rate: number | null;
  duration: number | null;
  format: string | null;
  decode_ms: number | null;
  tested_at: string;
}

export interface StreamStartRequest {
  record?: boolean;
  record_trigger?: string;
  record_seconds?: number;
  motion?: boolean;
}

export interface StreamCapabilities {
  ffmpeg: Record<string, unknown>;
  opencv: Record<string, unknown>;
  publisher: Record<string, unknown>;
  source_types: string[];
  profile: Record<string, unknown>;
  max_cameras: number;
  active_streams: number;
  recording_dir: string;
  recording_max_seconds: number;
  motion: Record<string, unknown>;
}

export interface RecordStartResponse {
  status: string;
  recording_id: string | null;
  camera_id: string | null;
  trigger: string | null;
  file_path: string | null;
}

export interface Recording {
  id: string;
  camera_id: string;
  stream_id: string | null;
  started_by: string | null;
  trigger: string;
  status: string;
  file_path: string;
  size_bytes: number | null;
  duration_seconds: number | null;
  segment_seconds: number;
  started_at: string | null;
  ended_at: string | null;
  created_at: string;
  updated_at: string;
  camera_name: string | null;
}

export interface OnvifDeviceInfo {
  name?: string;
  ip?: string;
  mac?: string;
  model?: string;
  location?: string;
  rtsp_url?: string;
  reachable: boolean;
}

export interface OnvifDiscoverResult {
  mode: string;
  devices: OnvifDeviceInfo[];
  count: number;
  reachable: number;
  duration_ms: number;
}

/* ---------------------------------------------------------------------------
 * Alerts
 * ------------------------------------------------------------------------- */

export interface Alert {
  id: string;
  camera_id: string | null;
  camera_name: string | null;
  type: AlertType;
  severity: AlertSeverity;
  status: AlertStatus;
  message: string;
  confidence: number | null;
  snapshot_url: string | null;
  occurred_at: string;
  created_at: string;
  updated_at: string;
}

export interface AlertUpdate {
  status?: AlertStatus;
  severity?: AlertSeverity;
}

export interface AlertStats {
  total: number;
  new: number;
  critical: number;
  acknowledged: number;
  escalated: number;
  resolved: number;
  by_type: Record<AlertType, number>;
  by_severity: Record<AlertSeverity, number>;
}

/* ---------------------------------------------------------------------------
 * Incidents
 * ------------------------------------------------------------------------- */

export interface Incident {
  id: string;
  camera_id: string | null;
  camera_name: string | null;
  title: string;
  description: string | null;
  type: IncidentType;
  severity: AlertSeverity;
  status: IncidentStatus;
  location: string | null;
  latitude: number | null;
  longitude: number | null;
  reported_by: string | null;
  occurred_at: string;
  created_at: string;
  updated_at: string;
}

export interface IncidentCreate {
  title: string;
  description?: string | null;
  type: IncidentType;
  severity?: AlertSeverity;
  status?: IncidentStatus;
  camera_id?: string | null;
  location?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  occurred_at?: string | null;
}

export interface IncidentUpdate {
  title?: string;
  description?: string | null;
  type?: IncidentType;
  severity?: AlertSeverity;
  status?: IncidentStatus;
}

/* ---------------------------------------------------------------------------
 * Dashboard
 * ------------------------------------------------------------------------- */

export interface CameraGeoPoint {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  status: CameraStatus;
}

export interface SystemHealth {
  api: "ok" | "degraded";
  database: "ok" | "degraded";
  redis: "ok" | "degraded";
  version: string;
}

export interface DashboardSummary {
  cameras: {
    total: number;
    active: number;
    offline: number;
    maintenance: number;
    unknown: number;
  };
  alerts: {
    total: number;
    new: number;
    critical: number;
  };
  recent_alerts: Alert[];
  camera_geo: CameraGeoPoint[];
  system: SystemHealth;
}

export interface HealthResponse {
  status: "ok" | "degraded";
  version: string;
  components: {
    database: { status: "ok" | "degraded"; latency_ms: number | null };
    redis: { status: "ok" | "degraded"; latency_ms: number | null };
  };
}

/* ---------------------------------------------------------------------------
 * Phase 3 — AI inference engine
 * ------------------------------------------------------------------------- */

export interface InferenceDevice {
  accelerator: "cpu" | "cuda";
  device_name: string;
  providers: string[];
  gpu: { name?: string; utilization_pct?: number } | null;
}

export interface AiModel {
  name: string;
  version: string;
  backend: "sim" | "onnx";
  status: "loaded" | "unloaded" | "error";
  generation: number;
  accelerator: string | null;
  device: string | null;
  providers: string[] | null;
  weights_path: string | null;
  classes: string[];
  error: string | null;
  loaded_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface InferenceConfig {
  enabled: boolean;
  model: string;
  weights_dir: string;
  accel_mode: string;
  plugins: AiModel[];
  device: InferenceDevice;
  batch: { size: number; window_ms: number };
  confidence: number;
  max_fps_per_camera: number;
  store_enabled: boolean;
  alert_enabled: boolean;
  processes_active: number;
}

/** One bounding box drawn on the overlay (normalized 0..1 coordinates). */
export interface DetectionBox {
  class_name: string;
  confidence: number;
  track_id: number | null;
  x: number;
  y: number;
  w: number;
  h: number;
  cx: number;
  cy: number;
}

/** Realtime overlay payload broadcast over the inference WebSocket. */
export interface InferenceOverlay {
  type: "overlay";
  camera_id: string;
  camera_name: string | null;
  model: string;
  generation: number;
  backend: string;
  accelerator: string | null;
  device_name: string | null;
  ts: string;
  pre_ms: number;
  infer_ms: number;
  post_ms: number;
  total_ms: number;
  fps: number;
  frame_seq: number;
  detection_count: number;
  boxes: DetectionBox[];
}

/** Per-camera runtime statistics (also streamed on the "stats" channel). */
export interface CameraInferenceStats {
  camera_id: string;
  camera_name: string | null;
  inference_active: boolean;
  stream_running?: boolean;
  model?: string;
  backend?: string | null;
  accelerator?: string | null;
  device_name?: string | null;
  generation?: number;
  frames_analyzed: number;
  total_detections: number;
  last_frame_counts: Record<string, number>;
  fps: number;
  avg_infer_ms: number;
  avg_total_ms: number;
  frame_seq: number;
  started_ts: number;
  uptime_s: number;
  last_overlay: InferenceOverlay | null;
  device: InferenceDevice;
}

export interface InferenceRun {
  id: string;
  camera_id: string;
  model_name: string;
  model_version: string;
  model_generation: number;
  frame_seq: number;
  ts: string;
  width: number;
  height: number;
  pre_ms: number;
  infer_ms: number;
  post_ms: number;
  total_ms: number;
  batch_size: number;
  detections: number;
  fps: number;
  accelerator: string | null;
  backend: string | null;
}

export interface InferenceDetection {
  id: string;
  run_id: string;
  camera_id: string;
  model_name: string;
  class_name: string;
  confidence: number;
  track_id: number | null;
  x: number;
  y: number;
  w: number;
  h: number;
  cx: number;
  cy: number;
  frame_seq: number;
  ts: string;
}

export interface InferenceAlertItem {
  id: string;
  camera_id: string;
  model_name: string;
  rule: string;
  class_name: string;
  level: string;
  message: string;
  confidence: number | null;
  count: number;
  first_seen_at: string;
  last_seen_at: string;
  resolved: boolean;
  resolved_at: string | null;
  created_at: string;
}

export interface InferenceSummary {
  runs_total: number;
  detections_total: number;
  by_class: Record<string, number>;
  alerts_open: number;
  runs_last_minute: number;
  avg_infer_ms_recent: number;
  active_cameras: number;
  up: boolean;
}

export interface InferenceBenchmark {
  model: string;
  backend: string;
  accelerator: string;
  device_name: string;
  providers: string[];
  image_width: number;
  image_height: number;
  batch_size: number;
  iterations: number;
  frames_processed: number;
  pre_ms_avg: number;
  infer_ms_avg: number;
  post_ms_avg: number;
  total_ms_avg: number;
  fps: number;
  objects_per_second: number;
  objects_per_frame_avg: number;
  run_ms: number;
  ts: string;
  report_file: string | null;
}

/* ---------------------------------------------------------------------------
 * Watchlists
 * ------------------------------------------------------------------------- */

// Type aliases are defined canonically in ./constants and re-exported from
// ./index. Here we import them (aliased) only for use inside this file's
// interfaces so there is no double-export collision in index.ts.
import type {
  WatchlistCategory as _WatchlistCategory,
  WatchlistSourceDB as _WatchlistSourceDB,
  WatchlistTargetType as _WatchlistTargetType,
} from "./constants";

type WatchlistTargetType = _WatchlistTargetType;
type WatchlistCategory = _WatchlistCategory;
type WatchlistSourceDB = _WatchlistSourceDB;

export interface Watchlist {
  id: string;
  target_type: WatchlistTargetType;
  identifier_number: string;
  category: WatchlistCategory;
  source_db: WatchlistSourceDB;
  notes: string | null;
  active: boolean;
  added_by: string | null;
  added_at: string;
  created_at: string;
  updated_at: string;
}

export interface WatchlistCreate {
  target_type: WatchlistTargetType;
  identifier_number: string;
  category: WatchlistCategory;
  source_db: WatchlistSourceDB;
  notes?: string | null;
  active?: boolean;
}

export interface WatchlistUpdate {
  target_type?: WatchlistTargetType;
  identifier_number?: string;
  category?: WatchlistCategory;
  source_db?: WatchlistSourceDB;
  notes?: string | null;
  active?: boolean;
}

export interface WatchlistStats {
  total: number;
  active: number;
  inactive: number;
  by_type: Record<string, number>;
  by_category: Record<string, number>;
  by_source: Record<string, number>;
}

/* ---------------------------------------------------------------------------
 * Vehicle Route Reconstruction
 * ------------------------------------------------------------------------- */

export interface RouteSighting {
  id: string;
  camera_id: string;
  camera_name: string | null;
  latitude: number;
  longitude: number;
  plate: string;
  normalized_plate: string;
  ocr_confidence: number;
  detection_confidence: number;
  vehicle_type: string | null;
  color: string | null;
  make: string | null;
  model: string | null;
  ts: string;
}

export interface VehicleRoute {
  plate: string;
  sightings: RouteSighting[];
  total_sightings: number;
  first_seen: string;
  last_seen: string;
  cameras_visited: number;
}

/* ---------------------------------------------------------------------------
 * Forensic Evidence Dossier (killer feature #1)
 * ------------------------------------------------------------------------- */

export interface DossierWatchlist {
  matched: boolean;
  target_type?: string | null;
  category?: string | null;
  source_db?: string | null;
  notes?: string | null;
  active?: boolean | null;
  added_at?: string | null;
}

export interface DossierSighting {
  detection_id: string;
  camera_id: string;
  cctv_code: string | null;
  camera_name: string | null;
  location: string | null;
  district_code: string | null;
  department_code: string | null;
  latitude: number | null;
  longitude: number | null;
  ts: string;
  ocr_confidence: number;
  detection_confidence: number;
  vehicle_type: string | null;
  color: string | null;
  make: string | null;
  model: string | null;
  state_code: string | null;
  rto_code: string | null;
}

export interface DossierSummary {
  sightings: number;
  distinct_cameras: number;
  distinct_departments: number;
  distinct_districts: number;
}

export interface ForensicDossier {
  plate: string;
  normalized_plate: string;
  version: string;
  schema: string;
  generated_at: string;
  integrity_sha256: string;
  source: string;
  watchlist: DossierWatchlist | null;
  summary: DossierSummary;
  sightings: DossierSighting[];
}

export interface DossierVerify {
  plate: string;
  integrity_sha256: string;
  valid: boolean;
}

/* ---------------------------------------------------------------------------
 * Predictive Interception Corridor (killer feature #2)
 * ------------------------------------------------------------------------- */

export interface InterceptionNode {
  camera_id: string;
  camera_name: string;
  location: string;
  latitude: number;
  longitude: number;
  rank: number;
  road_distance_km: number;
  travel_time_minutes: number;
  eta_utc: string;
  window_start_utc: string;
  window_end_utc: string;
  is_junction: boolean;
  corridor_path: string[];
}

export interface InterceptionVector {
  plate: string;
  trigger_camera: string;
  assumed_speed_kph: number;
  radius_km: number;
  observed_ts: string;
  basis: string;
  confidence: number;
  recommendation: string;
  nodes: InterceptionNode[];
}

export interface InterceptionRequest {
  plate: string;
  trigger_camera: string;
  observed_ts?: number;
  speed_kph?: number;
  radius_km?: number;
}