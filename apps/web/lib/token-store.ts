"use client";

/**
 * Access-token store shared by the auth context and the fetch client.
 * The token is mirrored to localStorage for reload resilience; a httpOnly
 * refresh cookie is managed by the backend for silent re-authentication.
 */

const STORAGE_KEY = "sentinel.access_token";

let cached: string | null = null;

export const tokenStore = {
  get(): string | null {
    if (cached === null && typeof window !== "undefined") {
      cached = window.localStorage.getItem(STORAGE_KEY);
    }
    return cached;
  },
  set(token: string | null): void {
    cached = token;
    if (typeof window !== "undefined") {
      if (token) window.localStorage.setItem(STORAGE_KEY, token);
      else window.localStorage.removeItem(STORAGE_KEY);
    }
  },
  clear(): void {
    this.set(null);
  },
};