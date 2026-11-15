import { expect, test, type Page } from "@playwright/test";

/**
 * IELTS question bank E2E (Slice 6): browse/filter the seeded original bank,
 * favorite persistence, random question, and starting an essay bound to a
 * bank question (question section visible in the editor).
 */

const PASSWORD = "SecurePassword123";

function uniqueEmail(): string {
  return `e2e-ielts-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
}

async function register(page: Page): Promise<void> {
  await page.goto("/register");
  await page.getByLabel("邮箱").fill(uniqueEmail());
  await page.getByLabel("密码", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "注册账号" }).click();
  await expect(page).toHaveURL(/\/profile/);
}

test("browse and filter the question bank", async ({ page }) => {
  await register(page);
  await page.goto("/ielts");
  await expect(page.getByTestId("ielts-page")).toBeVisible();
  await expect(page.getByTestId("question-card").first()).toBeVisible({ timeout: 15_000 });

  // Filter to Task 2 opinion questions.
  await page.getByTestId("filter-task-type").selectOption("task2");
  await page.getByTestId("filter-question-type").selectOption("opinion");
  await expect(page.getByTestId("question-card").first()).toBeVisible();
  const cards = page.getByTestId("question-card");
  const count = await cards.count();
  expect(count).toBe(7);
  for (let i = 0; i < count; i += 1) {
    await expect(cards.nth(i)).toContainText("Task 2");
    await expect(cards.nth(i)).toContainText("观点类");
  }

  // Topic filter narrows further; unknown combination shows the empty state.
  await page.getByTestId("filter-topic").selectOption("education");
  await expect(page.getByTestId("question-card").first()).toBeVisible();
  expect(await page.getByTestId("question-card").count()).toBeLessThan(count);
});

test("favorites persist across reload and can be removed", async ({ page }) => {
  await register(page);
  await page.goto("/ielts");
  await expect(page.getByTestId("question-card").first()).toBeVisible({ timeout: 15_000 });

  const firstCard = page.getByTestId("question-card").first();
  await firstCard.getByTestId("favorite-toggle").click();
  await expect(firstCard.getByTestId("favorite-toggle")).toHaveText("★ 已收藏");

  await page.reload();
  await expect(page.getByTestId("question-card").first()).toBeVisible({ timeout: 15_000 });
  // The bank ordering is stable (created_at, id), so the first card is the same.
  await expect(page.getByTestId("question-card").first().getByTestId("favorite-toggle")).toHaveText(
    "★ 已收藏",
  );

  await page.getByTestId("question-card").first().getByTestId("favorite-toggle").click();
  await expect(page.getByTestId("question-card").first().getByTestId("favorite-toggle")).toHaveText(
    "☆ 收藏",
  );
});

test("random question opens a detail view with translation", async ({ page }) => {
  await register(page);
  await page.goto("/ielts");
  await expect(page.getByTestId("ielts-page")).toBeVisible();
  await page.getByTestId("random-question").click();

  const detail = page.getByTestId("question-detail");
  await expect(detail).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("detail-prompt")).not.toBeEmpty();
  await expect(page.getByTestId("detail-translation")).toBeVisible();

  await page.getByTestId("back-to-list").click();
  await expect(page.getByTestId("question-list")).toBeVisible();
});

test("start writing from a bank question binds it to the essay", async ({ page }) => {
  await register(page);
  await page.goto("/ielts");
  await expect(page.getByTestId("question-card").first()).toBeVisible({ timeout: 15_000 });

  await page.getByTestId("filter-task-type").selectOption("task2");
  await page.getByTestId("question-card").first().getByTestId("view-question").click();
  await expect(page.getByTestId("question-detail")).toBeVisible({ timeout: 15_000 });
  const promptText = await page.getByTestId("detail-prompt").innerText();

  await page.getByTestId("start-writing").click();
  await expect(page).toHaveURL(/\/essays\/[0-9a-f-]+/, { timeout: 20_000 });

  // The finalized editor shows the question in its own non-editable section.
  const questionSection = page.getByTestId("question-section");
  await expect(questionSection).toBeVisible({ timeout: 15_000 });
  await expect(questionSection).toContainText(promptText.split("\n")[0]);
});
