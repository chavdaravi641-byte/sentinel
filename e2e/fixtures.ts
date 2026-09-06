import { expect, type Page } from "@playwright/test";

export const user = {
  id: "00000000-0000-0000-0000-000000000001",
  email: "admin@sentinel.gp",
  full_name: "Demo Operator",
  role: "admin",
  is_active: true,
};

const camera = {
  id: "00000000-0000-0000-0000-000000000010",
  name: "AHM-SGH-01",
  rtsp_url: "rtsp://example.test/stream",
  location: "Ahmedabad SG Highway",
  latitude: 23.0225,
  longitude: 72.5714,
  status: "online",
  description: "Fixture camera",
};

export async function mockApi(page: Page, authenticated = true) {
  let sessionAuthenticated = authenticated;
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;

    if (path.endsWith("/auth/me")) {
      if (!sessionAuthenticated) {
        await route.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ detail: "Unauthenticated" }) });
        return;
      }
      await route.fulfill({ json: user });
      return;
    }
    if (path.endsWith("/auth/login")) {
      sessionAuthenticated = true;
      await route.fulfill({
        json: { access_token: "playwright-token", refresh_token: "playwright-refresh", token_type: "bearer", user },
      });
      return;
    }
    if (path.endsWith("/auth/refresh")) {
      await route.fulfill({ json: { access_token: "playwright-token", refresh_token: "playwright-refresh", token_type: "bearer", user } });
      return;
    }
    if (path.endsWith("/health")) {
      await route.fulfill({ json: { status: "ok", components: { database: "ok", redis: "ok" } } });
      return;
    }
    if (path.endsWith("/dashboard/summary")) {
      await route.fulfill({ json: { cameras: { total: 1, active: 1, offline: 0, maintenance: 0, unknown: 0 }, alerts: { total: 1, new: 1, critical: 0 }, camera_geo: [camera], recent_alerts: [] } });
      return;
    }
    if (path.endsWith("/cameras") && request.method() === "GET") {
      await route.fulfill({ json: { items: [camera], total: 1, page: 1, page_size: 100, pages: 1 } });
      return;
    }
    if (path.endsWith("/cameras") && request.method() === "POST") {
      await route.fulfill({ status: 201, json: { ...camera, id: "00000000-0000-0000-0000-000000000011" } });
      return;
    }
    if (path.endsWith("/streams") && request.method() === "GET") {
      await route.fulfill({ json: [{ camera_id: camera.id, running: false, recording: false, status: "offline" }] });
      return;
    }
    if (path.includes("/watchlists/stats")) {
      await route.fulfill({ json: { total: 1, active: 1, by_category: { wanted: 1 } } });
      return;
    }
    if (path.endsWith("/watchlists") && request.method() === "GET") {
      await route.fulfill({ json: { items: [{ id: "watch-1", identifier_number: "GJ01AB1234", target_type: "vehicle", category: "wanted", source_db: "manual", active: true, notes: "Fixture target" }], total: 1, page: 1, page_size: 100, pages: 1 } });
      return;
    }
    if (path.endsWith("/watchlists") && request.method() === "POST") {
      await route.fulfill({ status: 201, json: { id: "watch-2", identifier_number: "GJ01AB1234", target_type: "vehicle", category: "wanted", source_db: "manual", active: true } });
      return;
    }
    if (path.endsWith("/vehicle-intel/investigate")) {
      await route.fulfill({ json: { matches: [], route_summary: { ordered_stops: [], total_distance_km: 0, total_travel_time_minutes: 0, confidence: 0 } } });
      return;
    }
    if (path.includes("/dossier")) {
      await route.fulfill({ json: { summary: { sightings: 0, distinct_departments: 0, distinct_districts: 0 }, integrity_sha256: "fixture-integrity" } });
      return;
    }
    if (path.includes("/vehicles/") || path.includes("/vehicle-intel/")) {
      await route.fulfill({ json: { nodes: [], confidence: 0, matches: [], route_summary: { ordered_stops: [], total_distance_km: 0, total_travel_time_minutes: 0, confidence: 0 } } });
      return;
    }
    if (path.endsWith("/alerts/stats")) {
      await route.fulfill({ json: { total: 0, critical: 0, by_type: {}, by_severity: {} } });
      return;
    }
    if (path.includes("/incidents")) {
      await route.fulfill({ json: { items: [], total: 0, page: 1, page_size: 500, pages: 1 } });
      return;
    }
    await route.fulfill({ json: {} });
  });
}

export async function login(page: Page) {
  await mockApi(page, false);
  await page.addInitScript(() => localStorage.clear());
  await page.goto("/login");
  await page.getByPlaceholder("operator@sentinel.gp").fill(user.email);
  await page.getByPlaceholder("••••••••••••").fill("Admin@2026");
  await page.getByRole("button", { name: "Sign In" }).click();
  await expect(page).toHaveURL(/\/app$/);
  await expect(page.getByRole("heading", { name: "Road Room" })).toBeVisible();
}
