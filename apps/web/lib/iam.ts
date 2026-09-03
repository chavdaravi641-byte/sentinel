"use client";

/**
 * Federation IAM client.
 *
 * The IAM API authenticates via a federation bearer token (a JSON access-token
 * document minted by SessionManager), which is independent of the Phase 1-5
 * user JWT used by the main `api` client. This module bootstrap-obtains a
 * session token for the seeded platform admin and uses it for IAM requests.
 */

import { endpoints } from "./api";

const IAM_TOKEN_KEY = "sentinel.iam_access_token";
const IAM_META_KEY = "sentinel.iam_meta";

export interface IamMeta {
  officer_id: string;
  badge_number: string;
  full_name: string;
  role: string;
}

let cachedToken: string | null = null;

function getToken(): string | null {
  if (cachedToken === null && typeof window !== "undefined") {
    cachedToken = window.localStorage.getItem(IAM_TOKEN_KEY);
  }
  return cachedToken;
}

function setToken(token: string | null): void {
  cachedToken = token;
  if (typeof window !== "undefined") {
    if (token) window.localStorage.setItem(IAM_TOKEN_KEY, token);
    else window.localStorage.removeItem(IAM_TOKEN_KEY);
  }
}

export function getIamMeta(): IamMeta | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(IAM_META_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as IamMeta;
  } catch {
    return null;
  }
}

export async function bootstrapIam(): Promise<IamMeta> {
  const res = await fetch(endpoints.iamSession, { method: "POST" });
  if (!res.ok) throw new Error("IAM session bootstrap failed.");
  const data = (await res.json()) as {
    access_token: string;
    officer_id: string;
    badge_number: string;
    full_name: string;
    role: string;
  };
  setToken(data.access_token);
  const meta: IamMeta = {
    officer_id: data.officer_id,
    badge_number: data.badge_number,
    full_name: data.full_name,
    role: data.role,
  };
  if (typeof window !== "undefined") {
    window.localStorage.setItem(IAM_META_KEY, JSON.stringify(meta));
  }
  return meta;
}

/** Ensure a live federation token exists (bootstrap if absent). */
export async function ensureIamToken(): Promise<string> {
  let token = getToken();
  if (!token) {
    await bootstrapIam();
    token = getToken();
  }
  if (!token) throw new Error("Unable to obtain IAM session.");
  return token;
}

interface IamOptions {
  method?: "GET" | "POST" | "PUT" | "DELETE";
  body?: unknown;
  /** Re-bootstrap once if the session token is stale (default true). */
  retry?: boolean;
}

export class IamError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.name = "IamError";
    this.status = status;
    this.detail = detail;
  }
}

function inferMessage(payload: unknown): string {
  if (payload && typeof payload === "object") {
    const detail = (payload as Record<string, unknown>).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail[0]?.msg) {
      return String((detail[0] as Record<string, unknown>).msg);
    }
    if (typeof (payload as Record<string, unknown>).message === "string") {
      return String((payload as Record<string, unknown>).message);
    }
  }
  return "IAM request failed.";
}

export async function iamFetch<T>(
  path: string,
  options: IamOptions = {},
): Promise<T> {
  const { method = "GET", body, retry = true } = options;
  const token = await ensureIamToken();

  const doFetch = async (tok: string): Promise<Response> => {
    const headers: Record<string, string> = {
      accept: "application/json",
      authorization: `Bearer ${tok}`,
    };
    if (body !== undefined) headers["content-type"] = "application/json";
    return fetch(path, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  };

  let res = await doFetch(token);

  if (res.status === 401 && retry) {
    await bootstrapIam();
    const fresh = getToken();
    if (fresh) res = await doFetch(fresh);
  }

  if (res.status === 204) return undefined as T;

  const payload = await res.json().catch(() => null);
  if (!res.ok) {
    throw new IamError(res.status, inferMessage(payload), payload);
  }
  return payload as T;
}

/** Clear the federation token/meta (e.g., on sign-out). */
export function clearIam(): void {
  setToken(null);
  if (typeof window !== "undefined") {
    window.localStorage.removeItem(IAM_META_KEY);
  }
}

export { getToken };
