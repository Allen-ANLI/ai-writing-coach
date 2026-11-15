import { expect, test, type Page } from "@playwright/test";

/**
 * 写作会话 E2E（Slice 2D + ADR-024）：首次打开自动辅助会话、模式切换、
 * 模拟考试倒计时、取消后不自动重建。隔离栈运行。
 */

const PASSWORD = "SecurePassword123";

function uniqueEmail(): string {
  return `e2e-sessions-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
}

async function openNewEssay(page: Page, title: string): Promise<void> {
  await page.goto("/register");
  await page.getByLabel("邮箱").fill(uniqueEmail());
  await page.getByLabel("密码", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "注册账号" }).click();
  await expect(page).toHaveURL(/\/profile/);
  await page.getByRole("link", { name: "我的作文" }).click();
  await page.getByTestId("new-essay").click();
  await page.getByTestId("essay-title-input").fill(title);
  await page.getByTestId("submit-create").click();
  await expect(page.getByTestId("create-dialog")).toBeHidden();
  await page.getByTestId("essay-title").click();
  await expect(page.getByTestId("editor-content")).toBeVisible();
}

async function cancelAutoSession(page: Page): Promise<void> {
  await expect(page.getByTestId("session-mode-chip")).toBeVisible({ timeout: 15_000 });
  await page.getByTestId("cancel-session").click();
  await expect(page.getByTestId("start-session")).toBeVisible({ timeout: 15_000 });
}

async function startSession(
  page: Page,
  mode: "assisted" | "independent",
  activity: "free_writing" | "practice" | "mock_exam" = "practice",
): Promise<void> {
  await page.getByTestId("start-session").click();
  await page.getByTestId(mode === "assisted" ? "mode-assisted" : "mode-independent").check();
  await page.getByTestId("activity-type").selectOption(activity);
  await page.getByTestId("confirm-start-session").click();
  await expect(page.getByTestId("session-mode-chip")).toBeVisible();
}

test("first open auto-starts an assisted session; no submit button during writing", async ({ page }) => {
  await openNewEssay(page, "Assisted session essay");
  // ADR-024：无需手动启动会话，语法辅助即时可用。
  await expect(page.getByTestId("session-mode-chip")).toHaveText("辅助学习", { timeout: 15_000 });

  await page.getByTestId("editor-content").click();
  await page.keyboard.type("This is my essay in progress.");
  await expect(page.getByTestId("save-status")).toContainText("已保存", { timeout: 15_000 });

  // 评分/改写是写后动作，写作中没有强制提交按钮。
  await expect(page.getByTestId("submit-session")).toHaveCount(0);
  await expect(page.getByTestId("confirm-submit")).toHaveCount(0);
});

test("independent session disables assistance controls", async ({ page }) => {
  await openNewEssay(page, "Independent session essay");
  await cancelAutoSession(page);
  await startSession(page, "independent");
  await expect(page.getByTestId("session-mode-chip")).toHaveText("独立写作");
  await expect(page.getByTestId("independent-notice")).toBeVisible();
  await expect(page.getByTestId("submit-session")).toHaveCount(0);
});

test("mock exam session shows a countdown", async ({ page }) => {
  await openNewEssay(page, "Mock exam essay");
  await cancelAutoSession(page);
  await page.getByTestId("start-session").click();
  await page.getByTestId("mode-independent").check();
  await page.getByTestId("activity-type").selectOption("mock_exam");
  await page.getByTestId("exam-task").selectOption("task2");
  await page.getByTestId("exam-duration").fill("20");
  await page.getByTestId("confirm-start-session").click();
  await expect(page.getByTestId("exam-countdown")).toBeVisible();
  await expect(page.getByTestId("exam-countdown")).toContainText(/\d+:\d{2}/);
});

test("cancel frees the essay and does not auto-recreate a session", async ({ page }) => {
  await openNewEssay(page, "Cancel session essay");
  await cancelAutoSession(page);
  // 显式取消后不自动重建（否则无法切换独立写作）。
  await page.waitForTimeout(2000);
  await expect(page.getByTestId("start-session")).toBeVisible();
  await startSession(page, "independent");
  await expect(page.getByTestId("session-mode-chip")).toHaveText("独立写作");
});
