import { expect, test, type Page } from "@playwright/test";

/**
 * Writing session E2E (Slice 2D): modes, submit flow, exam countdown.
 * Runs against the isolated stack (see playwright.config.ts).
 */

const PASSWORD = "SecurePassword123";

function uniqueEmail(): string {
  return `e2e-sessions-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
}

async function openNewEssay(page: Page, title: string): Promise<void> {
  await page.goto("/register");
  await page.getByLabel("Email").fill(uniqueEmail());
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/profile/);
  await page.getByRole("link", { name: "Dashboard" }).click();
  await page.getByTestId("new-essay").click();
  await page.getByTestId("essay-title-input").fill(title);
  await page.getByTestId("submit-create").click();
  await expect(page.getByTestId("create-dialog")).toBeHidden();
  await page.getByTestId("essay-title").click();
  await expect(page.getByTestId("editor-content")).toBeVisible();
}

async function startSession(
  page: Page,
  mode: "assisted" | "independent",
  activity: "free_writing" | "practice" | "mock_exam" = "practice",
): Promise<void> {
  await page.getByTestId("start-session").click();
  await page.getByTestId(mode === "assisted" ? "mode-assisted" : "mode-independent").check();
  await page.getByTestId("activity-type").selectOption(activity);
  await page.getByTestId("confirm-start-session").click();
  await expect(page.getByTestId("session-mode-chip")).toBeVisible();
}

test("assisted session shows mode; no submit button during writing", async ({ page }) => {
  await openNewEssay(page, "Assisted session essay");
  await startSession(page, "assisted");
  await expect(page.getByTestId("session-mode-chip")).toHaveText("Assisted learning");

  await page.getByTestId("editor-content").click();
  await page.keyboard.type("This is my essay in progress.");
  await expect(page.getByTestId("save-status")).toContainText("Saved", { timeout: 15_000 });

  // UX decision 2026-11-15 §2.7: evaluation/rewrite are post-writing actions,
  // not a mandatory submit button during normal writing.
  await expect(page.getByTestId("submit-session")).toHaveCount(0);
  await expect(page.getByTestId("confirm-submit")).toHaveCount(0);
});

test("independent session disables assistance controls", async ({ page }) => {
  await openNewEssay(page, "Independent session essay");
  await startSession(page, "independent");
  await expect(page.getByTestId("session-mode-chip")).toHaveText("Independent writing");
  await expect(page.getByTestId("independent-notice")).toBeVisible();
  await expect(page.getByTestId("submit-session")).toHaveCount(0);
});

test("mock exam session shows a countdown", async ({ page }) => {
  await openNewEssay(page, "Mock exam essay");
  await page.getByTestId("start-session").click();
  await page.getByTestId("mode-independent").check();
  await page.getByTestId("activity-type").selectOption("mock_exam");
  await page.getByTestId("exam-task").selectOption("task2");
  await page.getByTestId("exam-duration").fill("20");
  await page.getByTestId("confirm-start-session").click();
  await expect(page.getByTestId("exam-countdown")).toBeVisible();
  await expect(page.getByTestId("exam-countdown")).toContainText(/\d+:\d{2}/);
});

test("writing continues without submission; cancel frees the essay", async ({ page }) => {
  await openNewEssay(page, "Cancel session essay");
  await startSession(page, "assisted");
  await page.getByTestId("cancel-session").click();
  await expect(page.getByTestId("start-session")).toBeVisible({ timeout: 15_000 });
  await startSession(page, "independent");
  await expect(page.getByTestId("session-mode-chip")).toHaveText("Independent writing");
});
