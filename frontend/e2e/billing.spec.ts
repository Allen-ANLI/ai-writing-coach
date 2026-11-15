import { expect, test, type Page } from "@playwright/test";

/**
 * Billing E2E (Slice 10): sandbox upgrade flow, quota display, cancellation,
 * history. No real payment provider is involved (ADR-021).
 */

const PASSWORD = "SecurePassword123";

function uniqueEmail(): string {
  return `e2e-bill-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
}

async function register(page: Page): Promise<void> {
  await page.goto("/register");
  await page.getByLabel("邮箱").fill(uniqueEmail());
  await page.getByLabel("密码", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "注册账号" }).click();
  await expect(page).toHaveURL(/\/profile/);
}

test("sandbox upgrade activates pro and records history", async ({ page }) => {
  await register(page);
  await page.goto("/billing");
  await expect(page.getByTestId("billing-page")).toBeVisible();
  await expect(page.getByTestId("current-subscription")).toContainText("Free", {
    timeout: 10_000,
  });
  await expect(page.getByTestId("plan-card")).toHaveCount(3);
  await expect(page.getByTestId("quota-usage")).toContainText("AI 调用：0 / 100");
  await expect(page.getByTestId("no-history")).toBeVisible();

  await page.getByTestId("upgrade-pro").click();
  await expect(page.getByTestId("sandbox-checkout")).toBeVisible({ timeout: 10_000 });
  await page.getByTestId("confirm-payment").click();

  await expect(page.getByTestId("current-subscription")).toContainText("Pro", {
    timeout: 10_000,
  });
  await expect(page.getByTestId("current-plan-badge")).toHaveCount(1);
  await expect(page.getByTestId("history-item")).toHaveCount(1);
  await expect(page.getByTestId("history-item").first()).toContainText("已完成");
  await expect(page.getByTestId("quota-usage")).toContainText("AI 调用：0 / 1000");
});

test("cancellation keeps access until period end", async ({ page }) => {
  await register(page);
  await page.goto("/billing");
  await expect(page.getByTestId("current-subscription")).toContainText("Free", {
    timeout: 10_000,
  });
  await page.getByTestId("upgrade-pro").click();
  await expect(page.getByTestId("sandbox-checkout")).toBeVisible();
  await page.getByTestId("confirm-payment").click();
  await expect(page.getByTestId("current-subscription")).toContainText("Pro", {
    timeout: 10_000,
  });

  await page.getByTestId("cancel-subscription").click();
  await expect(page.getByTestId("current-subscription")).toContainText("已取消", {
    timeout: 10_000,
  });
  await expect(page.getByTestId("current-subscription")).toContainText("可用至本周期结束");
  // Still on pro until the period ends.
  await expect(page.getByTestId("current-subscription")).toContainText("Pro");
});
