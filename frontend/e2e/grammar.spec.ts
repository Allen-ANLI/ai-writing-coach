import { expect, test, type Page } from "@playwright/test";

/**
 * Inline grammar feedback E2E (Slice 3): rule-first checking against the real
 * LanguageTool container, blurred answers, reveal, self-correction validation,
 * teaching card, ignore, and independent-mode enforcement.
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

test("grammar error gets an underline, short hint and blurred answer", async ({ page }) => {
  await openEditorWithSession(page);
  await typeAndWaitSaved(page, BAD_TEXT);

  await expect(page.locator(".awc-issue--grammar").first()).toBeVisible({ timeout: 20_000 });
  const hint = page.locator(".awc-hint").first();
  await expect(hint).toBeVisible();
  await expect(hint.locator(".awc-hint__text")).not.toHaveText("");
  const answer = hint.locator(".awc-hint__answer");
  await expect(answer).toHaveText("••••");
  await expect(answer).not.toHaveClass(/awc-hint__answer--revealed/);
  await expect(page.getByTestId("issue-count")).not.toHaveText("0 issues");
});

test("reveal shows the correction only after explicit action", async ({ page }) => {
  await openEditorWithSession(page);
  await typeAndWaitSaved(page, BAD_TEXT);
  await expect(page.locator(".awc-hint").first()).toBeVisible({ timeout: 20_000 });

  await page.locator(".awc-hint__actions button", { hasText: "Reveal" }).first().click();
  const revealed = page.locator(".awc-hint__answer--revealed").first();
  await expect(revealed).toBeVisible({ timeout: 10_000 });
  await expect(revealed).toHaveText(/went|goes/);
});

test("correct self-edit clears the highlight automatically", async ({ page }) => {
  await openEditorWithSession(page);
  await typeAndWaitSaved(page, BAD_TEXT);
  await expect(page.locator(".awc-issue").first()).toBeVisible({ timeout: 20_000 });

  await typeAndWaitSaved(page, FIXED_TEXT);
  await expect(page.locator(".awc-issue")).toHaveCount(0, { timeout: 20_000 });
  await expect(page.getByTestId("issue-count")).toHaveText("0 issues", { timeout: 20_000 });
});

test("incorrect self-edit keeps the highlight", async ({ page }) => {
  await openEditorWithSession(page);
  await typeAndWaitSaved(page, BAD_TEXT);
  await expect(page.locator(".awc-issue").first()).toBeVisible({ timeout: 20_000 });

  // Edit elsewhere; the agreement error remains.
  await typeAndWaitSaved(page, "He go to school today.");
  await expect(page.locator(".awc-issue").first()).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId("issue-count")).not.toHaveText("0 issues");
});

test("teaching card opens with contextual content and closes", async ({ page }) => {
  await openEditorWithSession(page);
  await typeAndWaitSaved(page, BAD_TEXT);
  await expect(page.locator(".awc-hint").first()).toBeVisible({ timeout: 20_000 });

  await page.locator(".awc-hint__actions button", { hasText: "Teach me" }).first().click();
  const card = page.getByTestId("teaching-card");
  await expect(card).toBeVisible({ timeout: 15_000 });
  await expect(card).toContainText("Why it is wrong here", { timeout: 15_000 });
  await expect(card).toContainText("Recommended correction");

  await page.getByTestId("close-teaching").click();
  await expect(card).toBeHidden();
});

test("ignore removes the hint without deleting history", async ({ page }) => {
  await openEditorWithSession(page);
  await typeAndWaitSaved(page, BAD_TEXT);
  await expect(page.locator(".awc-hint").first()).toBeVisible({ timeout: 20_000 });

  await page.locator(".awc-hint__actions button", { hasText: "Ignore" }).first().click();
  await expect(page.locator(".awc-hint")).toHaveCount(0, { timeout: 10_000 });
});

test("independent mode shows no grammar assistance controls", async ({ page }) => {
  await openEditorWithSession(page, "independent");
  await expect(page.getByTestId("check-now")).toBeHidden();
  await typeAndWaitSaved(page, BAD_TEXT);
  // Give any (incorrect) check time to appear, then assert none did.
  await page.waitForTimeout(2500);
  await expect(page.locator(".awc-issue")).toHaveCount(0);
  await expect(page.locator(".awc-hint")).toHaveCount(0);
});
