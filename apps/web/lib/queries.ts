"use client";

import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import type {
  Alert,
  AlertStats,
  AlertUpdate,
  Camera,
  CameraCreate,
  CameraTestResult,
  CameraUpdate,
  DashboardSummary,
  HealthResponse,
  Incident,
  IncidentCreate,
  IncidentUpdate,
  Paginated,
  Recording,
  RecordStartResponse,
  StreamCapabilities,
  StreamHealth,
  StreamMediaUrls,
  StreamStartRequest,
  StreamTestResult,
  AiModel,
  CameraInferenceStats,
  InferenceAlertItem,
  InferenceBenchmark,
  InferenceConfig,
  InferenceDetection,
  InferenceRun,
  InferenceSummary,
} from "@sentinel/shared";
import { api, endpoints } from "./api";
import { qs } from "./utils";

/* ---------------------------------------------------------------------------
 * Dashboard
 * ------------------------------------------------------------------------- */

export function useDashboardSummary() {
  return useQuery({
    queryKey: ["dashboard", "summary"],
    queryFn: () => api.get<DashboardSummary>(endpoints.dashboardSummary),
    refetchInterval: 60_000,
  });
}

/* ---------------------------------------------------------------------------
 * Cameras
 * ------------------------------------------------------------------------- */

export interface CameraListParams {
  status?: string;
  search?: string;
  page?: number;
  pageSize?: number;
}

export function useCameras(params: CameraListParams = {}) {
  const path = `${endpoints.cameras}${qs({
    status: params.status,
    search: params.search,
    page: params.page ?? 1,
    page_size: params.pageSize ?? 100,
  })}`;
  return useQuery({
    queryKey: ["cameras", params],
    queryFn: () => api.get<Paginated<Camera>>(path),
    placeholderData: (prev) => prev,
  });
}

export function useCamera(id: string | undefined | null) {
  return useQuery({
    queryKey: ["cameras", id],
    queryFn: () => api.get<Camera>(endpoints.camera(id!)),
    enabled: Boolean(id),
  });
}

export function useCreateCamera() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: CameraCreate) =>
      api.post<Camera>(endpoints.cameras, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["cameras"] }),
  });
}

export function useUpdateCamera() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: CameraUpdate }) =>
      api.patch<Camera>(endpoints.camera(id), body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["cameras"] }),
  });
}

export function useDeleteCamera() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete<{ message: string }>(endpoints.camera(id)),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["cameras"] }),
  });
}

export function useCameraTest(id: string, enabled = false) {
  return useQuery({
    queryKey: ["cameras", id, "test"],
    queryFn: () => api.get<CameraTestResult>(endpoints.cameraHealth(id)),
    enabled,
  });
}

export function useRunCameraTest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      api.post<CameraTestResult>(endpoints.cameraTest(id)),
    onSuccess: (_, id) => {
      qc.invalidateQueries({ queryKey: ["cameras"] });
      qc.invalidateQueries({ queryKey: ["cameras", id, "test"] });
    },
  });
}

/* ---------------------------------------------------------------------------
 * Streams
 * ------------------------------------------------------------------------- */

export function useStreams(refetchInterval = 4_000) {
  return useQuery({
    queryKey: ["streams"],
    queryFn: () => api.get<StreamHealth[]>(endpoints.streams),
    refetchInterval,
  });
}

export function useStreamHealth(id: string | undefined | null) {
  return useQuery({
    queryKey: ["streams", id, "health"],
    queryFn: () => api.get<StreamHealth>(endpoints.streamHealth(id!)),
    enabled: Boolean(id),
    refetchInterval: 4_000,
  });
}

export function useStreamMedia(id: string | undefined | null) {
  return useQuery({
    queryKey: ["streams", id, "media"],
    queryFn: () => api.get<StreamMediaUrls>(endpoints.streamMedia(id!)),
    enabled: Boolean(id),
    refetchInterval: 3 * 60_000,
  });
}

export function useStreamConfig() {
  return useQuery({
    queryKey: ["streams", "config"],
    queryFn: () => api.get<StreamCapabilities>(endpoints.streamConfig),
    staleTime: 60_000,
  });
}

export function useStartStream() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body?: StreamStartRequest }) =>
      api.post<StreamHealth>(endpoints.streamStart(id), body),
    onSuccess: (_, { id }) => {
      qc.invalidateQueries({ queryKey: ["streams"] });
      qc.invalidateQueries({ queryKey: ["streams", id] });
    },
  });
}

export function useStopStream() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      api.post<{ message: string }>(endpoints.streamStop(id)),
    onSuccess: (_, id) => {
      qc.invalidateQueries({ queryKey: ["streams"] });
      qc.invalidateQueries({ queryKey: ["streams", id] });
    },
  });
}

export function useRunStreamTest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      api.post<StreamTestResult>(endpoints.streamTest(id)),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["streams"] }),
  });
}

export function useRecordStart() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, trigger = "manual" }: { id: string; trigger?: string }) =>
      api.post<RecordStartResponse>(endpoints.streamRecordStart(id), {
        trigger,
      }),
    onSuccess: (_, { id }) => {
      qc.invalidateQueries({ queryKey: ["streams"] });
      qc.invalidateQueries({ queryKey: ["streams", id] });
      qc.invalidateQueries({ queryKey: ["streams", id, "health"] });
    },
  });
}

export function useRecordStop() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      api.post<RecordStartResponse>(endpoints.streamRecordStop(id)),
    onSuccess: (_, id) => {
      qc.invalidateQueries({ queryKey: ["streams"] });
      qc.invalidateQueries({ queryKey: ["streams", id] });
      qc.invalidateQueries({ queryKey: ["streams", id, "health"] });
      qc.invalidateQueries({ queryKey: ["streams", "recordings"] });
    },
  });
}

export interface RecordingListParams {
  cameraId?: string;
  status?: string;
  page?: number;
  pageSize?: number;
}

export function useRecordings(params: RecordingListParams = {}) {
  const path = `${endpoints.streamRecordings}${qs({
    camera_id: params.cameraId,
    status: params.status,
    page: params.page ?? 1,
    page_size: params.pageSize ?? 50,
  })}`;
  return useQuery({
    queryKey: ["streams", "recordings", params],
    queryFn: () => api.get<Paginated<Recording>>(path),
  });
}

/* ---------------------------------------------------------------------------
 * Alerts
 * ------------------------------------------------------------------------- */

export interface AlertListParams {
  severity?: string;
  status?: string;
  type?: string;
  cameraId?: string;
  page?: number;
  pageSize?: number;
}

export function useAlerts(params: AlertListParams = {}) {
  const path = `${endpoints.alerts}${qs({
    severity: params.severity,
    status: params.status,
    type: params.type,
    camera_id: params.cameraId,
    page: params.page ?? 1,
    page_size: params.pageSize ?? 50,
  })}`;
  return useQuery({
    queryKey: ["alerts", params],
    queryFn: () => api.get<Paginated<Alert>>(path),
  });
}

export function useAlertStats() {
  return useQuery({
    queryKey: ["alerts", "stats"],
    queryFn: () => api.get<AlertStats>(endpoints.alertStats),
    refetchInterval: 60_000,
  });
}

export function useUpdateAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: AlertUpdate }) =>
      api.patch<Alert>(endpoints.alert(id), body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["alerts"] });
      qc.invalidateQueries({ queryKey: ["alerts", "stats"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

/* ---------------------------------------------------------------------------
 * Incidents
 * ------------------------------------------------------------------------- */

export interface IncidentListParams {
  status?: string;
  type?: string;
  page?: number;
  pageSize?: number;
}

export function useIncidents(params: IncidentListParams = {}) {
  const path = `${endpoints.incidents}${qs({
    status: params.status,
    type: params.type,
    page: params.page ?? 1,
    page_size: params.pageSize ?? 50,
  })}`;
  return useQuery({
    queryKey: ["incidents", params],
    queryFn: () => api.get<Paginated<Incident>>(path),
  });
}

export function useCreateIncident() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: IncidentCreate) =>
      api.post<Incident>(endpoints.incidents, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["incidents"] }),
  });
}

export function useUpdateIncident() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: IncidentUpdate }) =>
      api.patch<Incident>(endpoints.incident(id), body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["incidents"] }),
  });
}

/* ---------------------------------------------------------------------------
 * Misc
 * ------------------------------------------------------------------------- */

export function useHealth(enabled = true) {
  return useQuery({
    queryKey: ["health"],
    queryFn: () => api.get<HealthResponse>(endpoints.health),
    refetchInterval: 30_000,
    enabled,
  });
}

/* ---------------------------------------------------------------------------
 * Phase 3 — AI inference engine
 * ------------------------------------------------------------------------- */

export function useInferenceConfig() {
  return useQuery({
    queryKey: ["inference", "config"],
    queryFn: () => api.get<InferenceConfig>(endpoints.inferenceConfig),
    refetchInterval: 15_000,
  });
}

export function useInferenceModels() {
  return useQuery({
    queryKey: ["inference", "models"],
    queryFn: () => api.get<AiModel[]>(endpoints.inferenceModels),
    refetchInterval: 15_000,
  });
}

export function useInferenceSummary() {
  return useQuery({
    queryKey: ["inference", "summary"],
    queryFn: () => api.get<InferenceSummary>(endpoints.inferenceSummary),
    refetchInterval: 10_000,
  });
}

export function useInferenceCameraStats(cameraId: string | undefined | null) {
  return useQuery({
    queryKey: ["inference", cameraId, "stats"],
    queryFn: () => api.get<CameraInferenceStats>(endpoints.inferenceCameraStats(cameraId!)),
    enabled: Boolean(cameraId),
    refetchInterval: 4_000,
  });
}

export function useStartInference() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      api.post<CameraInferenceStats>(endpoints.inferenceCameraStart(id)),
    onSuccess: (_, id) => {
      qc.invalidateQueries({ queryKey: ["inference", id, "stats"] });
      qc.invalidateQueries({ queryKey: ["inference", "summary"] });
    },
  });
}

export function useStopInference() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      api.post<{ message: string }>(endpoints.inferenceCameraStop(id)),
    onSuccess: (_, id) => {
      qc.invalidateQueries({ queryKey: ["inference", id, "stats"] });
      qc.invalidateQueries({ queryKey: ["inference", "summary"] });
    },
  });
}

export interface InferenceRunListParams {
  cameraId?: string;
  page?: number;
  pageSize?: number;
}

export function useInferenceRuns(params: InferenceRunListParams = {}) {
  const path = `${endpoints.inferenceRuns}${qs({
    camera_id: params.cameraId,
    page: params.page ?? 1,
    page_size: params.pageSize ?? 50,
  })}`;
  return useQuery({
    queryKey: ["inference", "runs", params],
    queryFn: () => api.get<Paginated<InferenceRun>>(path),
  });
}

export function useInferenceDetections(params: { cameraId?: string; pageSize?: number } = {}) {
  const path = `${endpoints.inferenceDetections}${qs({
    camera_id: params.cameraId,
    page_size: params.pageSize ?? 50,
  })}`;
  return useQuery({
    queryKey: ["inference", "detections", params],
    queryFn: () => api.get<Paginated<InferenceDetection>>(path),
  });
}

export function useInferenceAlerts(params: { cameraId?: string; resolved?: boolean; pageSize?: number } = {}) {
  const query: Record<string, string | number | undefined | null> = {
    camera_id: params.cameraId,
    page_size: params.pageSize ?? 50,
  };
  if (params.resolved !== undefined) query.resolved = params.resolved ? "1" : "0";
  const path = `${endpoints.inferenceAlerts}${qs(query)}`;
  return useQuery({
    queryKey: ["inference", "alerts", params],
    queryFn: () => api.get<Paginated<InferenceAlertItem>>(path),
  });
}

export function useResolveInferenceAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      api.post<InferenceAlertItem>(endpoints.inferenceAlertResolve(id)),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["inference", "alerts"] }),
  });
}

export function useInferenceBenchmark() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      iterations?: number;
      image_width?: number;
      image_height?: number;
      batch_size?: number;
    }) => api.post<InferenceBenchmark>(endpoints.inferenceBenchmark, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["inference", "models"] });
      qc.invalidateQueries({ queryKey: ["inference", "config"] });
    },
  });
}