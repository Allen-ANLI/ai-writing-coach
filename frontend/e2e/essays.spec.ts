import { expect, test, type Page } from "@playwright/test";

/**
 * Essay management E2E against the isolated stack (see playwright.config.ts).
 * Each test registers a unique user through the real UI.
 */

const PASSWORD = "SecurePassword123";

function uniqueEmail(): string {
  return `e2e-essays-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
}

async function registerAndOpenDashboard(page: Page): Promise<void> {
  await page.goto("/register");
  await page.getByLabel("Email").fill(uniqueEmail());
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/profile/);
  await page.getByRole("link", { name: "Dashboard" }).click();
  await expect(page).toHaveURL(/\/dashboard/);
}

async function createEssayViaUi(page: Page, title: string): Promise<void> {
  await page.getByTestId("new-essay").click();
  await page.getByTestId("essay-title-input").fill(title);
  await page.getByTestId("submit-create").click();
  await expect(page.getByTestId("create-dialog")).toBeHidden();
}

test("dashboard shows a loading state then the empty state", async ({ page }) => {
  await page.goto("/register");
  await page.getByLabel("Email").fill(uniqueEmail());
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/profile/);

  // Delay only the FIRST essays request so the loading state is observable;
  // later requests (e.g. a post-refresh retry) must pass through immediately.
  let firstRequest = true;
  await page.route("**/api/v1/essays*", async (route) => {
    if (firstRequest) {
      firstRequest = false;
      await new Promise((resolve) => setTimeout(resolve, 1200));
    }
    await route.continue();
  });
  await page.getByRole("link", { name: "Dashboard" }).click();
  await expect(page.getByTestId("essays-loading")).toBeVisible();
  await expect(page.getByTestId("essays-empty")).toBeVisible({ timeout: 15_000 });
  await page.unroute("**/api/v1/essays*");
});

test("create essay appears in the list and refreshes without reload", async ({ page }) => {
  await registerAndOpenDashboard(page);
  await expect(page.getByTestId("essays-empty")).toBeVisible();

  await createEssayViaUi(page, "My first essay");
  await expect(page.getByTestId("essay-item")).toHaveCount(1);
  await expect(page.getByTestId("essay-title")).toHaveText("My first essay");

  await createEssayViaUi(page, "Second essay");
  await expect(page.getByTestId("essay-item")).toHaveCount(2);
});

test("rename essay updates the list", async ({ page }) => {
  await registerAndOpenDashboard(page);
  await createEssayViaUi(page, "Before rename");

  await page.getByTestId("rename-essay").click();
  await expect(page.getByTestId("rename-dialog")).toBeVisible();
  await page.getByTestId("essay-title-input").fill("After rename");
  await page.getByTestId("save-rename").click();

  await expect(page.getByTestId("rename-dialog")).toBeHidden();
  await expect(page.getByTestId("essay-title")).toHaveText("After rename");
});

test("delete requires confirmation; cancel keeps the essay", async ({ page }) => {
  await registerAndOpenDashboard(page);
  await createEssayViaUi(page, "Doomed essay");

  await page.getByTestId("delete-essay").click();
  await expect(page.getByTestId("delete-dialog")).toBeVisible();
  await page.getByTestId("cancel-delete").click();
  await expect(page.getByTestId("delete-dialog")).toBeHidden();
  await expect(page.getByTestId("essay-item")).toHaveCount(1);

  await page.getByTestId("delete-essay").click();
  await page.getByTestId("confirm-delete").click();
  await expect(page.getByTestId("delete-dialog")).toBeHidden();
  await expect(page.getByTestId("essay-item")).toHaveCount(0);
  await expect(page.getByTestId("essays-empty")).toBeVisible();
});

test("essay title navigates to the detail page and back", async ({ page }) => {
  await registerAndOpenDashboard(page);
  await createEssayViaUi(page, "Detail navigation");

  await page.getByTestId("essay-title").click();
  await expect(page).toHaveURL(/\/essays\/[0-9a-f-]{36}/);
  await expect(page.getByTestId("essay-detail-title")).toHaveText("Detail navigation");

  await page.getByRole("link", { name: "← Back to essays" }).click();
  await expect(page).toHaveURL(/\/dashboard/);
  await expect(page.getByTestId("essay-item")).toHaveCount(1);
});

test("deleted essay detail shows an error state", async ({ page }) => {
  await registerAndOpenDashboard(page);
  await createEssayViaUi(page, "Gone soon");

  await page.getByTestId("essay-title").click();
  await expect(page).toHaveURL(/\/essays\/[0-9a-f-]{36}/);
  const detailUrl = page.url();

  await page.getByRole("link", { name: "← Back to essays" }).click();
  await page.getByTestId("delete-essay").click();
  await page.getByTestId("confirm-delete").click();
  await expect(page.getByTestId("essays-empty")).toBeVisible();

  await page.goto(detailUrl);
  await expect(page.getByTestId("essay-detail-error")).toBeVisible();
});

test("anonymous visitors cannot reach the dashboard", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login/);
});
