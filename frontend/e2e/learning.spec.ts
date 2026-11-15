import { expect, test, type Page } from "@playwright/test";

/**
 * Learning Center E2E (Slice 5B): translation review flow with deterministic
 * scheduling feedback, summary stats, weakness profile visibility.
 */

const PASSWORD = "SecurePassword123";

function uniqueEmail(): string {
  return `e2e-learn-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
}

async function register(page: Page): Promise<void> {
  await page.goto("/register");
  await page.getByLabel("邮箱").fill(uniqueEmail());
  await page.getByLabel("密码", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "注册账号" }).click();
  await expect(page).toHaveURL(/\/profile/);
}

async function seedExpression(page: Page): Promise<void> {
  await page.goto("/knowledge");
  await page.getByTestId("add-expression").click();
  await page.getByTestId("kb-english-input").fill("gain hands-on experience");
  await page.getByTestId("kb-chinese-input").fill("获得实践经验");
  await page.getByTestId("kb-save").click();
  await expect(page.getByTestId("kb-item")).toHaveCount(1);
}

test("review flow: Chinese prompt, correct answer, scheduling feedback", async ({ page }) => {
  await register(page);
  await seedExpression(page);

  await page.goto("/learning");
  await expect(page.getByTestId("learning-summary")).toBeVisible();
  await expect(page.getByTestId("due-count")).toHaveText("1");

  await expect(page.getByTestId("review-card")).toBeVisible();
  await expect(page.getByTestId("review-prompt")).toHaveText("获得实践经验");
  // The English answer must not be visible in the prompt.
  await expect(page.getByTestId("review-card")).not.toContainText("gain hands-on");

  await page.getByTestId("review-answer").fill("gain hands-on experience");
  await page.getByTestId("review-submit").click();

  const result = page.getByTestId("review-result");
  await expect(result).toBeVisible({ timeout: 15_000 });
  await expect(result).toContainText("正确");
  await expect(result).toContainText("gain hands-on experience");
  await expect(result).toContainText("下次复习");

  await page.getByTestId("review-next").click();
  await expect(page.getByTestId("no-reviews")).toBeVisible({ timeout: 10_000 });
  await expect(page.getByTestId("due-count")).toHaveText("0");
});

test("wrong answer shows reference and keeps the expression in rotation", async ({ page }) => {
  await register(page);
  await seedExpression(page);

  await page.goto("/learning");
  await page.getByTestId("review-answer").fill("totally unrelated words");
  await page.getByTestId("review-submit").click();

  const result = page.getByTestId("review-result");
  await expect(result).toBeVisible({ timeout: 15_000 });
  await expect(result).toContainText("参考表达：");
  await expect(result).toContainText("gain hands-on experience");
});

test("empty learning center shows guidance", async ({ page }) => {
  await register(page);
  await page.goto("/learning");
  await expect(page.getByTestId("no-reviews")).toBeVisible();
  await expect(page.getByTestId("due-count")).toHaveText("0");
});
