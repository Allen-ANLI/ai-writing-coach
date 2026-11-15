import { expect, test, type Page } from "@playwright/test";

/**
 * Inline grammar feedback E2E — finalized UX (user decision 2026-11-15):
 * automatic sentence-completion checking (no manual button), hover feedback
 * card, click-blurred-to-reveal, Tab-to-replace, teaching icon, independent
 * mode enforcement. Real LanguageTool on the isolated stack.
 */

const PASSWORD = "SecurePassword123";
const BAD_TEXT = "He go to school yesterday.";
const FIXED_TEXT = "He went to school yesterday.";

function uniqueEmail(): string {
  return `e2e-grammar-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
}

async function openEditorWithSession(
  page: Page,
  mode: "assisted" | "independent" = "assisted",
): Promise<void> {
  await page.goto("/register");
  await page.getByLabel("Email").fill(uniqueEmail());
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/profile/);
  await page.getByRole("link", { name: "Dashboard" }).click();
  await page.getByTestId("new-essay").click();
  await page.getByTestId("essay-title-input").fill("Grammar essay");
  await page.getByTestId("submit-create").click();
  await expect(page.getByTestId("create-dialog")).toBeHidden();
  await page.getByTestId("essay-title").click();
  await expect(page.getByTestId("editor-content")).toBeVisible();

  await page.getByTestId("start-session").click();
  await page.getByTestId(mode === "assisted" ? "mode-assisted" : "mode-independent").check();
  await page.getByTestId("confirm-start-session").click();
  await expect(page.getByTestId("session-mode-chip")).toBeVisible();
}

async function typeAndWaitSaved(page: Page, text: string): Promise<void> {
  await page.getByTestId("editor-content").click();
  await page.keyboard.press("Control+a");
  await page.keyboard.type(text);
  await expect(page.getByTestId("save-status")).toContainText("Saved", { timeout: 15_000 });
}

async function waitForFirstIssue(page: Page): Promise<void> {
  await expect(page.locator(".awc-issue").first()).toBeVisible({ timeout: 30_000 });
}

test("completed sentence is checked automatically; hover shows floating hint", async ({ page }) => {
  await openEditorWithSession(page);
  // No manual check button exists anywhere.
  await expect(page.getByTestId("check-now")).toHaveCount(0);

  await typeAndWaitSaved(page, BAD_TEXT);
  await waitForFirstIssue(page);
  await expect(page.locator(".awc-issue--grammar").first()).toBeVisible();

  // No always-visible hint block; feedback floats on hover.
  await expect(page.locator(".awc-hint")).toHaveCount(0);
  await page.locator(".awc-issue--grammar").first().hover();
  const card = page.getByTestId("grammar-hover-card");
  await expect(card).toBeVisible({ timeout: 10_000 });
  await expect(card).toContainText(/主谓一致|语法/);
  await expect(page.getByTestId("blurred-answer")).toBeVisible();
  await expect(page.getByTestId("revealed-answer")).toHaveCount(0);
});

test("clicking the blurred answer reveals it; Tab replaces the original", async ({ page }) => {
  await openEditorWithSession(page);
  await typeAndWaitSaved(page, BAD_TEXT);
  await waitForFirstIssue(page);

  await page.locator(".awc-issue--grammar").first().hover();
  await expect(page.getByTestId("grammar-hover-card")).toBeVisible({ timeout: 10_000 });
  await page.getByTestId("blurred-answer").click();

  const revealed = page.getByTestId("revealed-answer");
  await expect(revealed).toBeVisible({ timeout: 10_000 });
  await expect(revealed).toHaveText(/went|goes/);
  await expect(page.getByTestId("tab-instruction")).toContainText("Tab");

  await page.keyboard.press("Tab");
  await expect(page.locator(".awc-issue")).toHaveCount(0, { timeout: 15_000 });
  const content = await page.getByTestId("editor-content").textContent();
  expect(content).toMatch(/He (went|goes) to school yesterday\./);
  await expect(page.getByTestId("grammar-hover-card")).toBeHidden();
});

test("Tab without an active correction keeps normal editor behavior", async ({ page }) => {
  await openEditorWithSession(page);
  await typeAndWaitSaved(page, BAD_TEXT);
  await waitForFirstIssue(page);

  // Focus the editor away from any pinned correction; Tab must not replace.
  await page.getByTestId("editor-content").click();
  await page.keyboard.press("End");
  await page.keyboard.press("Tab");
  const content = await page.getByTestId("editor-content").textContent();
  expect(content).toContain("He go to school yesterday.");
});

test("correct self-edit clears the highlight automatically", async ({ page }) => {
  await openEditorWithSession(page);
  await typeAndWaitSaved(page, BAD_TEXT);
  await waitForFirstIssue(page);

  await typeAndWaitSaved(page, FIXED_TEXT);
  await expect(page.locator(".awc-issue")).toHaveCount(0, { timeout: 30_000 });
});

test("incorrect self-edit keeps the highlight", async ({ page }) => {
  await openEditorWithSession(page);
  await typeAndWaitSaved(page, BAD_TEXT);
  await waitForFirstIssue(page);

  await typeAndWaitSaved(page, "He go to school today.");
  await expect(page.locator(".awc-issue").first()).toBeVisible({ timeout: 30_000 });
});

test("teaching icon opens the contextual floating card", async ({ page }) => {
  await openEditorWithSession(page);
  await typeAndWaitSaved(page, BAD_TEXT);
  await waitForFirstIssue(page);

  await page.locator(".awc-issue--grammar").first().hover();
  await expect(page.getByTestId("grammar-hover-card")).toBeVisible({ timeout: 10_000 });
  await page.getByTestId("teaching-icon").click();

  const card = page.getByTestId("teaching-card");
  await expect(card).toBeVisible({ timeout: 15_000 });
  await expect(card).toContainText("Why it is wrong here", { timeout: 15_000 });
  await page.getByTestId("close-teaching").click();
  await expect(card).toBeHidden();
});

test("Alt+I ignores the issue at the caret", async ({ page }) => {
  await openEditorWithSession(page);
  await typeAndWaitSaved(page, BAD_TEXT);
  await waitForFirstIssue(page);

  await page.locator(".awc-issue--grammar").first().click();
  // Clicking the error opens teaching; close it, then ignore via shortcut.
  const teaching = page.getByTestId("teaching-card");
  if (await teaching.isVisible()) {
    await page.getByTestId("close-teaching").click();
  }
  await page.locator(".awc-issue--grammar").first().hover();
  await page.keyboard.press("Alt+i");
  await expect(page.locator(".awc-issue")).toHaveCount(0, { timeout: 15_000 });
});

test("independent mode shows no grammar assistance", async ({ page }) => {
  await openEditorWithSession(page, "independent");
  await typeAndWaitSaved(page, BAD_TEXT);
  await page.waitForTimeout(3000);
  await expect(page.locator(".awc-issue")).toHaveCount(0);
  await expect(page.getByTestId("issue-count")).toHaveCount(0);
});

test("incomplete sentence is not checked prematurely", async ({ page }) => {
  await openEditorWithSession(page);
  await page.getByTestId("editor-content").click();
  // No sentence-final punctuation: must not trigger a check.
  await page.keyboard.type("He go to school");
  await expect(page.getByTestId("save-status")).toContainText("Saved", { timeout: 15_000 });
  await page.waitForTimeout(2500);
  await expect(page.locator(".awc-issue")).toHaveCount(0);
});
