import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { login, mockApi } from "./fixtures";

test.describe("Sentinel command center journeys", () => {
  test("logs in and renders the dashboard", async ({ page }) => {
    await login(page);
    await expect(page.getByText(/API\s+NOMINAL/)).toBeVisible();
    await expect(page.getByText("AHM-SGH-01").first()).toBeVisible();
  });

  test("registers a camera", async ({ page }) => {
    await login(page);
    await page.locator('a[href="/app/cameras"]').click();
    await page.getByRole("button", { name: "Register Camera" }).click();
    await expect(page.getByRole("heading", { name: "REGISTER CAMERA" })).toBeVisible();
    await page.getByLabel("Designation").fill("TEST-CAM-01");
    await page.getByLabel("Stream URL (RTSP)").fill("rtsp://example.test/live");
    await page.getByLabel("Location").fill("Ahmedabad");
    await page.getByLabel("Latitude").fill("23.02");
    await page.getByLabel("Longitude").fill("72.57");
    await page.getByRole("button", { name: "Register", exact: true }).click();
    await expect(page.getByText("Camera TEST-CAM-01 registered.")).toBeVisible();
  });

  test("opens the live stream wall", async ({ page }) => {
    await login(page);
    await page.getByRole("link", { name: "Live Wall", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Live Wall" })).toBeVisible();
  });

  test("searches a vehicle and reconstructs its route", async ({ page }) => {
    await login(page);
    await page.locator('a[href="/app/routes"]').click();
    const input = page.getByPlaceholder(/Enter vehicle registration/);
    await input.fill("GJ01AB1234");
    await page.getByRole("button", { name: "Trace" }).click();
    await expect(page.getByText("GJ01AB1234", { exact: true })).toBeVisible();
    await expect(page.getByText("Route Summary")).toBeVisible();
  });

  test("opens watchlist alert workflow", async ({ page }) => {
    await login(page);
    await page.locator('a[href="/app/watchlist"]').click();
    await expect(page.getByRole("heading", { name: "Watchlist" })).toBeVisible();
    await page.getByRole("button", { name: "Add" }).click();
    await expect(page.getByRole("heading", { name: "Add Watchlist Entry" })).toBeVisible();
    await page.getByPlaceholder("GJ01AB1234").fill("GJ01AB1234");
    await page.getByRole("button", { name: "Add Entry" }).click();
    await expect(page.getByText("Added GJ01AB1234 to watchlist.")).toBeVisible();
  });

  test("opens settings", async ({ page }) => {
    await login(page);
    await page.locator('a[href="/app/settings"]').click();
    await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
    await expect(page.getByText("Operator Profile")).toBeVisible();
  });
});

test.describe("Accessibility and responsive visual regression", () => {
  test("login page has no serious axe violations", async ({ page }) => {
    await mockApi(page, false);
    await page.goto("/login");
    const results = await new AxeBuilder({ page }).analyze();
    expect(results.violations.filter((v) => ["critical", "serious"].includes(v.impact ?? ""))).toEqual([]);
  });

  test("dashboard has no serious axe violations", async ({ page }) => {
    await login(page);
    const results = await new AxeBuilder({ page }).analyze();
    expect(results.violations.filter((v) => ["critical", "serious"].includes(v.impact ?? ""))).toEqual([]);
  });

  test("desktop dashboard visual baseline", async ({ page }) => {
    test.skip(test.info().project.name !== "desktop", "Desktop baseline runs in the desktop project.");
    await login(page);
    await expect(page).toHaveScreenshot("dashboard-desktop.png", { animations: "disabled", maxDiffPixels: 250 });
  });

  test("mobile dashboard visual baseline", async ({ page }) => {
    test.skip(test.info().project.name !== "mobile", "Mobile baseline runs in the mobile project.");
    await login(page);
    await expect(page).toHaveScreenshot("dashboard-mobile.png", { animations: "disabled", maxDiffPixels: 250 });
  });
});
