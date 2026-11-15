import { expect, test, type Page } from "@playwright/test";

/**
 * Privacy E2E (Slice 11, R7/R9): password reset request + invalid-token
 * handling, data export download, and irreversible account deletion.
 * The full reset happy path (token from email) is covered by backend tests.
 */

const PASSWORD = "SecurePassword123";

function uniqueEmail(): string {
  return `e2e-priv-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
}

async function register(page: Page): Promise<string> {
  const email = uniqueEmail();
  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/profile/);
  return email;
}

test("password reset request and invalid token handling", async ({ page }) => {
  const email = await register(page);

  await page.goto("/forgot-password");
  await page.getByTestId("forgot-email").fill(email);
  await page.getByTestId("forgot-submit").click();
  await expect(page.getByTestId("reset-sent")).toBeVisible({ timeout: 10_000 });

  // A forged token is rejected with a clear error.
  await page.goto("/reset-password?token=forged-token-value-123456");
  await page.getByTestId("reset-password").fill("BrandNewPassword456");
  await page.getByTestId("reset-submit").click();
  await expect(page.getByTestId("reset-error")).toBeVisible({ timeout: 10_000 });

  // Missing token shows guidance instead of a form.
  await page.goto("/reset-password");
  await expect(page.getByTestId("reset-no-token")).toBeVisible();
});

test("data export downloads JSON", async ({ page }) => {
  await register(page);
  await expect(page.getByTestId("privacy-card")).toBeVisible();

  const downloadPromise = page.waitForEvent("download");
  await page.getByTestId("export-data").click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("ai-writing-coach-export.json");
  const stream = await download.createReadStream();
  const chunks: Buffer[] = [];
  for await (const chunk of stream) {
    chunks.push(chunk as Buffer);
  }
  const payload = JSON.parse(Buffer.concat(chunks).toString("utf-8"));
  expect(payload.account.email).toBeTruthy();
  expect(Array.isArray(payload.essays)).toBe(true);
});

test("account deletion is confirmed and irreversible", async ({ page }) => {
  const email = await register(page);
  await expect(page.getByTestId("privacy-card")).toBeVisible();

  await page.getByTestId("delete-account").click();
  await expect(page.getByTestId("delete-confirm")).toBeVisible();
  // Cancel keeps the account.
  await page.getByTestId("cancel-delete").click();
  await expect(page.getByTestId("delete-confirm")).toBeHidden();

  await page.getByTestId("delete-account").click();
  await page.getByTestId("confirm-delete").click();
  await expect(page).toHaveURL(/\/login/, { timeout: 15_000 });

  // The deleted account can no longer sign in.
  await page.locator("#login-email").fill(email);
  await page.locator("#login-password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("alert")).toBeVisible({ timeout: 10_000 });
  await expect(page).toHaveURL(/\/login/);
});
