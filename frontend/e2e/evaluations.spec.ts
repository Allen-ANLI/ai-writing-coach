import { expect, test, type Page } from "@playwright/test";

/**
 * Evaluations & rewrites E2E (Slice 7): post-writing evaluation bound to an
 * immutable snapshot, estimate labeling, rewrite preview and atomic accept.
 * The isolated E2E backend uses the deterministic mock LLM.
 */

const PASSWORD = "SecurePassword123";

function uniqueEmail(): string {
  return `e2e-eval-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
}

async function register(page: Page): Promise<void> {
  await page.goto("/register");
  await page.getByLabel("邮箱").fill(uniqueEmail());
  await page.getByLabel("密码", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "注册账号" }).click();
  await expect(page).toHaveURL(/\/profile/);
}

async function openNewEssay(page: Page, title: string): Promise<void> {
  await register(page);
  await page.getByRole("link", { name: "我的作文" }).click();
  await page.getByTestId("new-essay").click();
  await page.getByTestId("essay-title-input").fill(title);
  await page.getByTestId("submit-create").click();
  await expect(page.getByTestId("create-dialog")).toBeHidden();
  await page.getByTestId("essay-title").click();
  await expect(page).toHaveURL(/\/essays\/[0-9a-f-]{36}/);
  await expect(page.getByTestId("editor-content")).toBeVisible();
}

async function typeAndSave(page: Page, text: string): Promise<void> {
  await page.getByTestId("editor-content").click();
  await page.keyboard.type(text);
  await expect(page.getByTestId("save-status")).toContainText("已保存", { timeout: 15_000 });
}

async function evaluateCurrentText(page: Page): Promise<void> {
  await page.getByTestId("open-evaluation").click();
  await expect(page.getByTestId("evaluation-dialog")).toBeVisible();
  await page.getByTestId("run-evaluation").click();
  await expect(page.getByTestId("evaluation-status")).toHaveText("已完成", {
    timeout: 20_000,
  });
}

test("evaluation shows estimated band, criteria and history", async ({ page }) => {
  await openNewEssay(page, "Evaluation essay");
  await typeAndSave(page, "Technology changes how students learn every day.");

  await evaluateCurrentText(page);
  await expect(page.getByTestId("evaluation-band")).toContainText("分");
  await expect(page.getByTestId("estimated-badge")).toHaveText("AI 估分");
  // General evaluation has three dimensions.
  await expect(page.getByTestId("criteria-list").locator("li")).toHaveCount(3);
  await expect(page.getByTestId("evaluation-history").getByTestId("evaluation-item")).toHaveCount(1);

  // Deleting removes it from history.
  await page.getByTestId("delete-evaluation").click();
  await expect(page.getByTestId("evaluation-history").getByTestId("evaluation-item")).toHaveCount(0);
});

test("rewrite preview and accept replace the essay text atomically", async ({ page }) => {
  await openNewEssay(page, "Rewrite essay");
  await typeAndSave(page, "Original draft about city life.");

  await evaluateCurrentText(page);
  await page.getByTestId("rewrite-level").selectOption("level_2");
  await page.getByTestId("generate-rewrite").click();
  await expect(page.getByTestId("rewrite-status")).toHaveText("改写 · 已完成", {
    timeout: 20_000,
  });
  const result = page.getByTestId("rewrite-result");
  await expect(result).toContainText("[mock:rewritten_text]");
  const rewrittenText = await result.innerText();

  await page.getByTestId("accept-rewrite").click();
  // Dialog closes and the editor now holds the server-stored rewrite.
  await expect(page.getByTestId("evaluation-dialog")).toBeHidden({ timeout: 15_000 });
  await expect(page.getByTestId("editor-content")).toContainText(rewrittenText.slice(0, 40));

  // The ai_rewrite snapshot is in history; the original stays empty.
  await page.getByTestId("open-history").click();
  await expect(
    page.getByTestId("version-list").locator("li").filter({ hasText: "AI rewrite" }),
  ).toHaveCount(1);
});

test("IELTS task 2 evaluation from a bank question uses four criteria", async ({ page }) => {
  await register(page);
  await page.goto("/ielts");
  await expect(page.getByTestId("question-card").first()).toBeVisible({ timeout: 15_000 });
  await page.getByTestId("filter-task-type").selectOption("task2");
  await page.getByTestId("question-card").first().getByTestId("view-question").click();
  await expect(page.getByTestId("question-detail")).toBeVisible();
  await page.getByTestId("start-writing").click();
  await expect(page).toHaveURL(/\/essays\/[0-9a-f-]+/, { timeout: 20_000 });
  await expect(page.getByTestId("question-section")).toBeVisible();

  await typeAndSave(page, "I agree that public transport should be free in big cities.");
  await evaluateCurrentText(page);
  await expect(page.getByTestId("evaluation-band")).toContainText("分");
  const criteria = page.getByTestId("criteria-list");
  await expect(criteria.locator("li")).toHaveCount(4);
  await expect(criteria).toContainText("任务回应");
});
