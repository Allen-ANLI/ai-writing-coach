import { expect, test, type Page } from "@playwright/test";

/**
 * Slice 9 E2E: preferences persistence, study-plan/task lifecycle (planner
 * confirmation creates a plan with tasks), and the AI usage card.
 */

const PASSWORD = "SecurePassword123";

function uniqueEmail(): string {
  return `e2e-s9-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
}

async function register(page: Page): Promise<void> {
  await page.goto("/register");
  await page.getByLabel("Email").fill(uniqueEmail());
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/profile/);
}

test("preferences persist across reload", async ({ page }) => {
  await register(page);
  await expect(page.getByTestId("preferences-card")).toBeVisible();

  await page.getByTestId("pref-language").selectOption("en");
  await expect(page.getByTestId("pref-saved")).toBeVisible({ timeout: 10_000 });
  await page.getByTestId("pref-grammar").uncheck();
  await expect(page.getByTestId("pref-saved")).toBeVisible();

  await page.reload();
  await expect(page.getByTestId("pref-language")).toHaveValue("en", { timeout: 10_000 });
  await expect(page.getByTestId("pref-grammar")).not.toBeChecked();
});

test("planner confirmation creates a plan with completable tasks", async ({ page }) => {
  await register(page);
  await page.goto("/learning");
  await expect(page.getByTestId("plans-card")).toBeVisible();
  await expect(page.getByTestId("no-plans")).toBeVisible();

  await page.getByTestId("generate-plan").click();
  await expect(page.getByTestId("plan-suggestions")).toBeVisible({ timeout: 20_000 });
  await page.getByTestId("confirm-plan").click();
  await expect(page.getByTestId("plan-done")).toContainText("Plan confirmed", { timeout: 15_000 });

  await expect(page.getByTestId("plan-item")).toHaveCount(1, { timeout: 10_000 });
  const tasks = page.getByTestId("task-item");
  expect(await tasks.count()).toBeGreaterThanOrEqual(2);

  await tasks.first().getByTestId("task-toggle").click();
  await expect(tasks.first().getByTestId("task-toggle")).toBeChecked({ timeout: 10_000 });
  await page.reload();
  await expect(page.getByTestId("task-item").first().getByTestId("task-toggle")).toBeChecked({
    timeout: 10_000,
  });
});

test("manual plan creation and AI usage card", async ({ page }) => {
  await register(page);
  await page.goto("/learning");
  await page.getByTestId("plan-title").fill("March sprint");
  await page.getByTestId("create-plan").click();
  await expect(page.getByTestId("plan-item")).toHaveCount(1, { timeout: 10_000 });
  await expect(page.getByTestId("plan-item").first()).toContainText("March sprint");

  await page.goto("/profile");
  await expect(page.getByTestId("ai-usage-card")).toBeVisible();
  await expect(page.getByTestId("usage-totals")).toBeVisible({ timeout: 10_000 });
  await expect(page.getByTestId("usage-trend")).toBeVisible();
});
