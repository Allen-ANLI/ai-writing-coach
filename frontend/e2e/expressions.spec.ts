import { expect, test, type Page } from "@playwright/test";

/**
 * Expression assistance + knowledge base E2E (Slice 4, mock LLM on the
 * isolated stack). Covers polish accept flow, Chinese translation flow,
 * save-to-knowledge-base, KB CRUD/search, and independent-mode enforcement.
 */

const PASSWORD = "SecurePassword123";

function uniqueEmail(): string {
  return `e2e-expr-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
}

async function register(page: Page): Promise<void> {
  await page.goto("/register");
  await page.getByLabel("邮箱").fill(uniqueEmail());
  await page.getByLabel("密码", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "注册账号" }).click();
  await expect(page).toHaveURL(/\/profile/);
}

async function openEditorWithSession(page: Page, mode: "assisted" | "independent"): Promise<void> {
  await page.getByRole("link", { name: "我的作文" }).click();
  await page.getByTestId("new-essay").click();
  await page.getByTestId("essay-title-input").fill("Expression essay");
  await page.getByTestId("submit-create").click();
  await expect(page.getByTestId("create-dialog")).toBeHidden();
  await page.getByTestId("essay-title").click();
  await expect(page.getByTestId("editor-content")).toBeVisible();
  // ADR-024：辅助会话自动创建；独立模式需先取消再显式启动。
  await expect(page.getByTestId("session-mode-chip")).toBeVisible({ timeout: 15_000 });
  if (mode === "independent") {
    await page.getByTestId("cancel-session").click();
    await expect(page.getByTestId("start-session")).toBeVisible({ timeout: 15_000 });
    await page.getByTestId("start-session").click();
    await page.getByTestId("mode-independent").check();
    await page.getByTestId("confirm-start-session").click();
    await expect(page.getByTestId("session-mode-chip")).toContainText("独立写作");
  }
}

test("knowledge base: add, search, archive, delete", async ({ page }) => {
  await register(page);
  await page.goto("/knowledge");
  await expect(page.getByTestId("kb-empty")).toBeVisible();

  await page.getByTestId("add-expression").click();
  await page.getByTestId("kb-english-input").fill("gain hands-on experience");
  await page.getByTestId("kb-chinese-input").fill("获得实践经验");
  await page.getByTestId("kb-topic-input").fill("Career");
  await page.getByTestId("kb-save").click();
  await expect(page.getByTestId("kb-item")).toHaveCount(1);
  await expect(page.getByTestId("kb-list")).toContainText("gain hands-on experience");

  await page.getByTestId("kb-search").fill("hands-on");
  await expect(page.getByTestId("kb-item")).toHaveCount(1);
  await page.getByTestId("kb-search").fill("nonexistent-term");
  await expect(page.getByTestId("kb-empty")).toBeVisible({ timeout: 10_000 });
  await page.getByTestId("kb-search").fill("");
  await expect(page.getByTestId("kb-item")).toHaveCount(1);

  const archiveButton = page.locator("[data-testid^='kb-archive-']").first();
  await archiveButton.click();
  await expect(page.getByTestId("kb-list")).toContainText("已归档", { timeout: 10_000 });

  const deleteButton = page.locator("[data-testid^='kb-delete-']").first();
  await deleteButton.click();
  await expect(page.getByTestId("kb-empty")).toBeVisible({ timeout: 10_000 });
});

test("polish: select text, accept a candidate, save to knowledge base", async ({ page }) => {
  await register(page);
  await openEditorWithSession(page, "assisted");

  await page.getByTestId("editor-content").click();
  await page.keyboard.type("I want to get more experience in this field.");
  await expect(page.getByTestId("save-status")).toContainText("已保存", { timeout: 15_000 });

  // Select the sentence (deterministic keyboard selection).
  await page.getByTestId("editor-content").click();
  await page.keyboard.press("Control+a");

  const assist = page.getByTestId("expression-assist");
  await expect(assist).toBeVisible({ timeout: 10_000 });
  await page.getByTestId("request-suggestions").click();
  await expect(page.getByTestId("expression-candidates")).toBeVisible({ timeout: 15_000 });

  const firstItem = page.locator("[data-testid^='expression-item-']").first();
  await firstItem.click();
  await expect(page.getByTestId("expression-accepted")).toBeVisible({ timeout: 15_000 });

  await page.getByTestId("save-to-kb").click();
  await expect(assist).toContainText("已保存到知识库", { timeout: 10_000 });

  await page.getByTestId("close-expression-assist").click();
  await page.goto("/knowledge");
  await expect(page.getByTestId("kb-item")).toHaveCount(1, { timeout: 10_000 });
});

test("translation: Chinese text gets English candidates and can be applied", async ({ page }) => {
  await register(page);
  await openEditorWithSession(page, "assisted");

  await page.getByTestId("editor-content").click();
  await page.keyboard.type("提高公众环保意识");
  await expect(page.getByTestId("save-status")).toContainText("已保存", { timeout: 15_000 });

  await page.keyboard.press("Control+a");
  const assist = page.getByTestId("expression-assist");
  await expect(assist).toBeVisible({ timeout: 10_000 });
  await expect(assist).toContainText("中译英");

  await page.getByTestId("request-suggestions").click();
  await expect(page.getByTestId("expression-candidates")).toBeVisible({ timeout: 15_000 });
  const firstItem = page.locator("[data-testid^='expression-item-']").first();
  await firstItem.click();
  await expect(page.getByTestId("expression-accepted")).toBeVisible({ timeout: 15_000 });

  // The Chinese text was replaced by the accepted candidate (the mock
  // provider's output is labeled [mock:english_text]).
  await expect(page.getByTestId("editor-content")).toContainText("[mock:english_text]", {
    timeout: 10_000,
  });
});

test("independent mode: no expression assistance", async ({ page }) => {
  await register(page);
  await openEditorWithSession(page, "independent");

  await page.getByTestId("editor-content").click();
  await page.keyboard.type("I want to get more experience.");
  await expect(page.getByTestId("save-status")).toContainText("已保存", { timeout: 15_000 });
  await page.keyboard.press("Control+a");
  await page.waitForTimeout(1000);
  await expect(page.getByTestId("expression-assist")).toHaveCount(0);
});

test("knowledge base: semantic and hybrid search modes", async ({ page }) => {
  await register(page);
  await page.goto("/knowledge");
  await page.getByTestId("add-expression").click();
  await page.getByTestId("kb-english-input").fill("gain hands-on experience");
  await page.getByTestId("kb-chinese-input").fill("获得实践经验");
  await page.getByTestId("kb-save").click();
  await expect(page.getByTestId("kb-item")).toHaveCount(1);

  await page.getByTestId("kb-search-mode").selectOption("semantic");
  await page.getByTestId("kb-search").fill("practical skills");
  await expect(page.getByTestId("kb-item")).toHaveCount(1, { timeout: 10_000 });

  await page.getByTestId("kb-search-mode").selectOption("hybrid");
  await expect(page.getByTestId("kb-item")).toHaveCount(1, { timeout: 10_000 });
});

test("extraction: candidates from a version require confirmation before saving", async ({ page }) => {
  await register(page);
  await openEditorWithSession(page, "assisted");

  await page.getByTestId("editor-content").click();
  await page.keyboard.type("Students should gain hands-on experience before graduation.");
  await expect(page.getByTestId("save-status")).toContainText("已保存", { timeout: 15_000 });

  // Create a checkpoint, then extract from it via History.
  await page.getByTestId("open-history").click();
  await page.getByTestId("create-checkpoint").click();
  await expect(page.getByTestId("version-list")).toContainText("存档点", { timeout: 10_000 });
  await page.getByTestId("extract-2").click();

  await expect(page.getByTestId("extraction-candidates")).toBeVisible({ timeout: 20_000 });
  // Nothing saved before confirmation.
  await page.goto("/knowledge");
  await expect(page.getByTestId("kb-empty")).toBeVisible();

  // Back to the editor, confirm extraction.
  await page.goBack();
  await page.getByTestId("open-history").click();
  await page.getByTestId("extract-2").click();
  await expect(page.getByTestId("extraction-candidates")).toBeVisible({ timeout: 20_000 });
  await page.getByTestId("extraction-save").click();
  await expect(page.getByTestId("extraction-saved")).toBeVisible({ timeout: 15_000 });

  await page.goto("/knowledge");
  await expect(page.getByTestId("kb-item")).toHaveCount(1, { timeout: 10_000 });
});
