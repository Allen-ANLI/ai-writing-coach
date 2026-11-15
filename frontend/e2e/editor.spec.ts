import { expect, test, type Page } from "@playwright/test";

/**
 * Writing editor E2E against the isolated stack (see playwright.config.ts).
 * Covers autosave persistence, word count, undo/redo, checkpoints + restore,
 * conflict recovery, outline and manual save.
 */

const PASSWORD = "SecurePassword123";

function uniqueEmail(): string {
  return `e2e-editor-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
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
  await expect(page).toHaveURL(/\/essays\/[0-9a-f-]{36}/);
  await expect(page.getByTestId("editor-content")).toBeVisible();
}

async function typeInEditor(page: Page, text: string): Promise<void> {
  await page.getByTestId("editor-content").click();
  await page.keyboard.type(text);
}

async function expectSaved(page: Page): Promise<void> {
  await expect(page.getByTestId("save-status")).toContainText("已保存", { timeout: 15_000 });
}

test("typing autosaves and survives a full reload", async ({ page }) => {
  await openNewEssay(page, "Autosave essay");
  await typeInEditor(page, "The first draft of my essay.");
  await expect(page.getByTestId("save-status")).toContainText("有未保存修改");
  await expectSaved(page);

  await page.reload();
  await expect(page.getByTestId("editor-content")).toContainText("The first draft of my essay.");
  await expectSaved(page);
});

test("word count mirrors the server rule", async ({ page }) => {
  await openNewEssay(page, "Word count essay");
  await expect(page.getByTestId("word-count")).toHaveText("0 词");
  await typeInEditor(page, "Hello world");
  await expect(page.getByTestId("word-count")).toHaveText("2 词");
  await expectSaved(page);
});

test("undo and redo work", async ({ page }) => {
  await openNewEssay(page, "Undo essay");
  await typeInEditor(page, "Some text");
  await page.getByTestId("undo").click();
  await expect(page.getByTestId("editor-content")).toHaveText("");
  await page.getByTestId("redo").click();
  await expect(page.getByTestId("editor-content")).toContainText("Some text");
});

test("Ctrl+S saves immediately", async ({ page }) => {
  await openNewEssay(page, "Manual save essay");
  await typeInEditor(page, "Manual save text.");
  await page.keyboard.press("Control+s");
  await expectSaved(page);
});

test("checkpoint appears in history and restore brings the text back", async ({ page }) => {
  await openNewEssay(page, "Checkpoint essay");
  await typeInEditor(page, "Version one text.");
  await expectSaved(page);

  await page.getByTestId("open-history").click();
  await page.getByLabel("为当前文本创建存档点").fill("Before changes");
  await page.getByTestId("create-checkpoint").click();
  await expect(page.getByTestId("version-list")).toContainText("Before changes");
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("version-list")).toBeHidden();

  await page.getByTestId("editor-content").click();
  await page.keyboard.press("Control+a");
  await page.keyboard.type("Version two text, completely different.");
  await expectSaved(page);

  await page.getByTestId("open-history").click();
  await page.getByTestId("restore-2").click();
  await page.getByTestId("confirm-restore").click();
  await expect(page.getByTestId("version-list")).toBeHidden();
  await expect(page.getByTestId("editor-content")).toContainText("Version one text.");
  await expect(page.getByTestId("editor-content")).not.toContainText("Version two");
  await expectSaved(page);

  // The restored checkpoint itself is unchanged and still viewable.
  // Versions list newest-first: the checkpoint (v2) is the first row.
  await page.getByTestId("open-history").click();
  await page.getByRole("button", { name: "查看" }).nth(0).click();
  await expect(page.getByTestId("version-content")).toContainText("Version one text.");
});

test("save conflict keeps local edits and offers recovery", async ({ page }) => {
  await openNewEssay(page, "Conflict essay");
  await typeInEditor(page, "Server side text.");
  await expectSaved(page);

  // Simulate a concurrent writer: the next autosave PUT loses the revision race.
  await page.route("**/working-document", async (route) => {
    if (route.request().method() === "PUT") {
      await route.fulfill({
        status: 409,
        contentType: "application/json",
        body: JSON.stringify({
          error: {
            code: "WORKING_DOCUMENT_CONFLICT",
            message: "The working document changed since your last save.",
            details: [],
          },
          meta: { request_id: "e2e-conflict" },
        }),
      });
    } else {
      await route.continue();
    }
  });

  await page.getByTestId("editor-content").click();
  await page.keyboard.press("Control+a");
  await page.keyboard.type("My local edits that must not vanish.");
  await expect(page.getByTestId("conflict-banner")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("editor-content")).toContainText("My local edits");

  // Recovery: load the server version (local text was kept until this choice).
  await page.unroute("**/working-document");
  await page.getByTestId("load-latest").click();
  await expect(page.getByTestId("conflict-banner")).toBeHidden();
  await expect(page.getByTestId("editor-content")).toContainText("Server side text.");
  await expectSaved(page);
});

test("headings render in the editor; left panel is the planner chat (ADR-024)", async ({ page }) => {
  await openNewEssay(page, "Outline essay");
  await page.getByRole("button", { name: "一级标题" }).click();
  await page.keyboard.type("Introduction");
  await page.keyboard.press("Enter");
  await page.getByRole("button", { name: "一级标题" }).click();
  await page.keyboard.type("Body paragraph");
  await expect(page.getByTestId("editor-content")).toContainText("Introduction");
  await expect(page.getByTestId("editor-content")).toContainText("Body paragraph");
  // 旧版文档大纲树已移除，左侧是对话式构思面板。
  await expect(page.getByTestId("outline-tree")).toHaveCount(0);
  await expect(page.getByTestId("planner-chat-panel")).toBeVisible();
});
