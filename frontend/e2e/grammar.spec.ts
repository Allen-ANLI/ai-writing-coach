import { expect, test, type Page } from "@playwright/test";

/**
 * 行内语法反馈 E2E（ADR-024）：句子完成自动检查（无手动按钮）、
 * 悬浮直接显示修改建议与详细讲解、Tab 替换、Alt+I 忽略、独立模式禁用。
 * 隔离栈上使用真实 LanguageTool；LLM 为 mock（仅验证管线）。
 */

const PASSWORD = "SecurePassword123";
const BAD_TEXT = "He go to school yesterday.";
const FIXED_TEXT = "He went to school yesterday.";

function uniqueEmail(): string {
  return `e2e-grammar-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
}

async function openEditor(
  page: Page,
  mode: "assisted" | "independent" = "assisted",
): Promise<void> {
  await page.goto("/register");
  await page.getByLabel("邮箱").fill(uniqueEmail());
  await page.getByLabel("密码", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "注册账号" }).click();
  await expect(page).toHaveURL(/\/profile/);
  await page.getByRole("link", { name: "我的作文" }).click();
  await page.getByTestId("new-essay").click();
  await page.getByTestId("essay-title-input").fill("Grammar essay");
  await page.getByTestId("submit-create").click();
  await expect(page.getByTestId("create-dialog")).toBeHidden();
  await page.getByTestId("essay-title").click();
  await expect(page.getByTestId("editor-content")).toBeVisible();

  // 辅助学习会话自动创建（ADR-024），无需手动启动。
  await expect(page.getByTestId("session-mode-chip")).toBeVisible({ timeout: 15_000 });

  if (mode === "independent") {
    await page.getByTestId("cancel-session").click();
    await expect(page.getByTestId("start-session")).toBeVisible({ timeout: 15_000 });
    await page.getByTestId("start-session").click();
    await page.getByTestId("mode-independent").check();
    await page.getByTestId("confirm-start-session").click();
    await expect(page.getByTestId("session-mode-chip")).toContainText("独立写作");
  } else {
    await expect(page.getByTestId("session-mode-chip")).toContainText("辅助学习");
  }
}

async function typeAndWaitSaved(page: Page, text: string): Promise<void> {
  await page.getByTestId("editor-content").click();
  await page.keyboard.press("Control+a");
  await page.keyboard.type(text);
  await expect(page.getByTestId("save-status")).toContainText("已保存", { timeout: 15_000 });
}

async function waitForFirstIssue(page: Page): Promise<void> {
  await expect(page.locator(".awc-issue").first()).toBeVisible({ timeout: 30_000 });
}

test("completed sentence is checked automatically; hover shows correction directly", async ({ page }) => {
  await openEditor(page);
  // No manual check button exists anywhere.
  await expect(page.getByTestId("check-now")).toHaveCount(0);

  await typeAndWaitSaved(page, BAD_TEXT);
  await waitForFirstIssue(page);
  await expect(page.locator(".awc-issue--grammar").first()).toBeVisible();

  await page.locator(".awc-issue--grammar").first().hover();
  const card = page.getByTestId("grammar-hover-card");
  await expect(card).toBeVisible({ timeout: 10_000 });
  // 取消模糊显示：悬浮即直接看到推荐修改（ADR-024）。
  const revealed = page.getByTestId("revealed-answer");
  await expect(revealed).toBeVisible({ timeout: 15_000 });
  await expect(revealed).toHaveText(/went|goes/);
  await expect(page.getByTestId("blurred-answer")).toHaveCount(0);
});

test("detailed explanation is requested via button and rendered structured (ADR-026)", async ({ page }) => {
  await openEditor(page);
  await typeAndWaitSaved(page, BAD_TEXT);
  await waitForFirstIssue(page);

  await page.locator(".awc-issue--grammar").first().hover();
  const card = page.getByTestId("grammar-hover-card");
  await expect(card).toBeVisible({ timeout: 10_000 });
  // 不自动请求：先有按钮，点击后才加载。
  await expect(page.getByTestId("teaching-content")).toHaveCount(0);
  await page.getByTestId("request-teaching").click();
  const teaching = page.getByTestId("teaching-content");
  await expect(teaching).toBeVisible({ timeout: 20_000 });
  // v2 结构：先语法知识点（含结构公式与对错对照），后本句原因。
  await expect(teaching).toContainText("语法知识点");
  await expect(teaching).toContainText("本句为什么这样改");
  await expect(teaching).toContainText("mock");
  await expect(page.getByTestId("teaching-card")).toHaveCount(0);
  await expect(page.getByTestId("teaching-icon")).toHaveCount(0);
});

test("Tab while the hover card is visible replaces the original", async ({ page }) => {
  await openEditor(page);
  await typeAndWaitSaved(page, BAD_TEXT);
  await waitForFirstIssue(page);

  await page.locator(".awc-issue--grammar").first().hover();
  await expect(page.getByTestId("grammar-hover-card")).toBeVisible({ timeout: 10_000 });
  await expect(page.getByTestId("revealed-answer")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("tab-instruction")).toContainText("Tab");

  await page.keyboard.press("Tab");
  await expect(page.locator(".awc-issue")).toHaveCount(0, { timeout: 15_000 });
  const content = await page.getByTestId("editor-content").textContent();
  expect(content).toMatch(/He (went|goes) to school yesterday\./);
  await expect(page.getByTestId("grammar-hover-card")).toBeHidden();
});

test("Tab without a visible correction keeps normal editor behavior", async ({ page }) => {
  await openEditor(page);
  await typeAndWaitSaved(page, BAD_TEXT);
  await waitForFirstIssue(page);

  // Move the pointer away so the card closes; Tab must not replace anything.
  await page.getByTestId("essay-detail-title").hover();
  await expect(page.getByTestId("grammar-hover-card")).toBeHidden({ timeout: 10_000 });
  await page.getByTestId("editor-content").click();
  await page.keyboard.press("End");
  await page.keyboard.press("Tab");
  const content = await page.getByTestId("editor-content").textContent();
  expect(content).toContain("He go to school yesterday.");
});

test("multiple sentences keep their own underlines (ADR-025)", async ({ page }) => {
  await openEditor(page);
  await typeAndWaitSaved(page, "He go to school.");
  await waitForFirstIssue(page);
  // 继续写第二句（快速输入，光标越过句点）——第一句的标记必须保留。
  await page.keyboard.type(" She like apples.");
  await expect(page.getByTestId("save-status")).toContainText("已保存", { timeout: 15_000 });
  await expect(page.locator(".awc-issue")).toHaveCount(2, { timeout: 30_000 });
});

test("accepting one correction keeps the other sentence's underline (ADR-027)", async ({ page }) => {
  await openEditor(page);
  await typeAndWaitSaved(page, "He go to school.");
  await waitForFirstIssue(page);
  await page.keyboard.type(" He run fast.");
  await expect(page.getByTestId("save-status")).toContainText("已保存", { timeout: 15_000 });
  await expect(page.locator(".awc-issue")).toHaveCount(2, { timeout: 30_000 });

  // 接受第一句的修改：第二句的下划线必须保留。
  await page.locator(".awc-issue").first().hover();
  await expect(page.getByTestId("grammar-hover-card")).toBeVisible({ timeout: 10_000 });
  await expect(page.getByTestId("revealed-answer")).toBeVisible({ timeout: 15_000 });
  await page.keyboard.press("Tab");
  await expect(page.getByTestId("editor-content")).toContainText(/He (went|goes) to school\./, {
    timeout: 15_000,
  });
  await expect(page.locator(".awc-issue")).toHaveCount(1, { timeout: 15_000 });

  // 保留的问题可以接着被接受（偏移已随替换平移）。
  await page.locator(".awc-issue").first().hover();
  await expect(page.getByTestId("grammar-hover-card")).toBeVisible({ timeout: 10_000 });
  await expect(page.getByTestId("revealed-answer")).toBeVisible({ timeout: 15_000 });
  await page.keyboard.press("Tab");
  await expect(page.locator(".awc-issue")).toHaveCount(0, { timeout: 15_000 });
  await expect(page.getByTestId("editor-content")).toContainText(/He (runs|ran) fast\./);
});

test("correct self-edit clears the highlight automatically", async ({ page }) => {
  await openEditor(page);
  await typeAndWaitSaved(page, BAD_TEXT);
  await waitForFirstIssue(page);

  await typeAndWaitSaved(page, FIXED_TEXT);
  await expect(page.locator(".awc-issue")).toHaveCount(0, { timeout: 30_000 });
});

test("incorrect self-edit keeps the highlight", async ({ page }) => {
  await openEditor(page);
  await typeAndWaitSaved(page, BAD_TEXT);
  await waitForFirstIssue(page);

  await typeAndWaitSaved(page, "He go to school today.");
  await expect(page.locator(".awc-issue").first()).toBeVisible({ timeout: 30_000 });
});

test("Alt+I ignores the hovered issue", async ({ page }) => {
  await openEditor(page);
  await typeAndWaitSaved(page, BAD_TEXT);
  await waitForFirstIssue(page);

  await page.locator(".awc-issue--grammar").first().hover();
  await expect(page.getByTestId("grammar-hover-card")).toBeVisible({ timeout: 10_000 });
  await page.keyboard.press("Alt+i");
  await expect(page.locator(".awc-issue")).toHaveCount(0, { timeout: 15_000 });
});

test("clicking an error only places the caret (no teaching popup)", async ({ page }) => {
  await openEditor(page);
  await typeAndWaitSaved(page, BAD_TEXT);
  await waitForFirstIssue(page);

  await page.locator(".awc-issue--grammar").first().click();
  await expect(page.getByTestId("teaching-card")).toHaveCount(0);
  await expect(page.getByTestId("editor-content")).toBeFocused();
});

test("independent mode shows no grammar assistance", async ({ page }) => {
  await openEditor(page, "independent");
  await typeAndWaitSaved(page, BAD_TEXT);
  await page.waitForTimeout(3000);
  await expect(page.locator(".awc-issue")).toHaveCount(0);
  await expect(page.getByTestId("issue-count")).toHaveCount(0);
});

test("records dialog reviews grammar errors and expression optimizations (ADR-026)", async ({ page }) => {
  await openEditor(page);
  await typeAndWaitSaved(page, BAD_TEXT);
  await waitForFirstIssue(page);

  await page.getByTestId("open-records").click();
  await expect(page.getByTestId("records-dialog")).toBeVisible();
  await expect(page.getByTestId("grammar-record").first()).toBeVisible({ timeout: 10_000 });
  await expect(page.getByTestId("grammar-record").first()).toContainText("主谓一致");

  await page.getByTestId("records-tab-expression").click();
  await expect(page.getByTestId("expression-records")).toBeVisible();
});

test("incomplete sentence is not checked prematurely", async ({ page }) => {
  await openEditor(page);
  await page.getByTestId("editor-content").click();
  // No sentence-final punctuation: must not trigger a check.
  await page.keyboard.type("He go to school");
  await expect(page.getByTestId("save-status")).toContainText("已保存", { timeout: 15_000 });
  await page.waitForTimeout(2500);
  await expect(page.locator(".awc-issue")).toHaveCount(0);
});
