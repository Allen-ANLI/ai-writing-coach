/**
 * UI screenshot capture for review (recreated 2026-11-15; the original file
 * referenced in the handoff was not present in the repository).
 *
 * Prerequisites: dev backend on :8000 and frontend on :3500 running against
 * the dev database (see root README). Uses the installed Edge channel because
 * the Playwright CDN download stalls on this machine.
 *
 * Run from frontend/ with the portable Node on PATH:
 *   node awc-screenshots.mjs
 *
 * Output: test-results/screenshots/*.png (gitignored). A throwaway user and
 * essay are created through the real API; nothing is written to the repo.
 */

import { mkdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { chromium } from "@playwright/test";

const here = path.dirname(fileURLToPath(import.meta.url));
const BASE = process.env.AWC_BASE_URL ?? "http://localhost:3500";
const API = process.env.AWC_API_URL ?? "http://localhost:8000/api/v1";
const OUT = path.join(here, "test-results", "screenshots");
const PASSWORD = "ScreenshotPassword123";

mkdirSync(OUT, { recursive: true });

async function api(pathname, { method = "GET", token, body } = {}) {
  const response = await fetch(`${API}${pathname}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`${method} ${pathname} -> ${response.status}: ${await response.text()}`);
  }
  return response.status === 204 ? null : response.json();
}

const email = `screenshots-${Date.now()}@example.com`;
const registered = await api("/auth/register", {
  method: "POST",
  body: { email, password: PASSWORD, display_name: "Screenshot User" },
});
const token = registered.data.access_token;

const essay = await api("/essays", {
  method: "POST",
  token,
  body: { title: "Should universities prioritize practical skills?", writing_type: "ielts_task2" },
});
const paragraphs = [
  { type: "heading", attrs: { level: 1 }, content: [{ type: "text", text: "Introduction" }] },
  {
    type: "paragraph",
    content: [
      {
        type: "text",
        text: "Some people argue that universities should focus on practical skills, while others believe theoretical knowledge matters more. This essay will discuss both views before giving my own opinion.",
      },
    ],
  },
  { type: "heading", attrs: { level: 1 }, content: [{ type: "text", text: "Body" }] },
  {
    type: "paragraph",
    content: [
      {
        type: "text",
        text: "On the one hand, practical skills prepare students for the job market. Graduates who can apply what they learned tend to find employment faster.",
      },
    ],
  },
];
await api(`/essays/${essay.data.id}/working-document`, {
  method: "PUT",
  token,
  body: {
    base_revision: 1,
    client_revision: 1,
    content_json: { type: "doc", content: paragraphs },
  },
});
await api(`/essays/${essay.data.id}/snapshots`, {
  method: "POST",
  token,
  body: { source_revision: 2, version_type: "checkpoint", label: "First draft" },
});

const browser = await chromium.launch({ channel: "msedge" });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const shots = [];

async function shot(name) {
  const file = path.join(OUT, `${name}.png`);
  await page.screenshot({ path: file, fullPage: false });
  shots.push(file);
  console.log(`captured ${name}`);
}

await page.goto(`${BASE}/`);
await page.waitForLoadState("networkidle");
await shot("01-landing");

await page.goto(`${BASE}/login`);
await page.waitForLoadState("networkidle");
await shot("02-login");

await page.goto(`${BASE}/register`);
await page.waitForLoadState("networkidle");
await shot("03-register");

await page.goto(`${BASE}/login`);
await page.getByLabel("Email").fill(email);
await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
await page.getByRole("button", { name: "Sign in" }).click();
await page.waitForURL(/\/profile/);
await page.waitForLoadState("networkidle");
await shot("04-profile");

await page.getByRole("link", { name: "Dashboard" }).click();
await page.waitForURL(/\/dashboard/);
await page.waitForLoadState("networkidle");
await shot("05-dashboard");

await page.getByTestId("essay-title").click();
await page.waitForURL(/\/essays\/[0-9a-f-]{36}/);
await page.getByTestId("editor-content").waitFor();
await page.waitForTimeout(800);
await shot("06-writing-editor");

await page.getByTestId("open-history").click();
await page.getByTestId("version-list").waitFor();
await shot("07-version-history");
await page.keyboard.press("Escape");

await browser.close();
console.log(`\n${shots.length} screenshots saved to ${OUT}`);
