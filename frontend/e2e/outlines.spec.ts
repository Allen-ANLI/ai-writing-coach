import { expect, test, type Page } from "@playwright/test";

/**
 * 对话式构思 E2E（ADR-024）：左侧聊天 → 大纲卡片 → 确认 → 灰色中文指引；
 * 个性化学习规划工作流的人工确认/拒绝。E2E 栈使用 mock LLM（确定性 propose）。
 */

const PASSWORD = "SecurePassword123";

function uniqueEmail(): string {
  return `e2e-outline-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
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

test("chat planner proposes an outline; confirmation drives ghost hints", async ({ page }) => {
  await openNewEssay(page, "Planned essay");

  // 左侧是对话面板；旧版 Plan 按钮与文档大纲树已移除（ADR-024）。
  await expect(page.getByTestId("planner-chat-panel")).toBeVisible();
  await expect(page.getByTestId("open-planner")).toHaveCount(0);
  await expect(page.getByTestId("outline-tree")).toHaveCount(0);

  await page.getByTestId("planner-input").fill("我同意大城市公共交通应该免费。");
  await page.getByTestId("planner-send").click();

  // mock 确定性返回 propose：助手消息 + 大纲卡片 + 中文范文（ADR-031）。
  await expect(page.getByTestId("planner-message-assistant").first()).toBeVisible({ timeout: 20_000 });
  const card = page.getByTestId("planner-outline-card").first();
  await expect(card).toBeVisible({ timeout: 20_000 });
  // ADR-033：大纲以嵌套 Markdown 渲染（粗体概括+详解+子要点缩进）。
  const outlineMd = card.getByTestId("outline-markdown");
  await expect(outlineMd).toBeVisible();
  await expect(outlineMd).toContainText("背景与立场");
  await expect(outlineMd).toContainText("主张公共交通免费");
  await expect(outlineMd).toContainText("通勤成本下降"); // 嵌套子要点
  const essayDetails = card.getByTestId("model-essay-details");
  await expect(essayDetails).toBeVisible();
  await essayDetails.locator("summary").click();
  // 中文翻译（幽灵来源）+ 英文范文均展示。
  await expect(essayDetails).toContainText("大城市的公共交通应该免费。");
  await expect(essayDetails).toContainText("Public transport should be free in big cities.");
  await page.getByTestId("confirm-outline").first().click();
  await expect(card).toContainText("已确认", { timeout: 15_000 });

  // 光标进入空段落 → 灰色中文范文句指引 widget（不写入正文）。
  await page.getByTestId("editor-content").click();
  const hint = page.getByTestId("ghost-hint");
  await expect(hint).toBeVisible({ timeout: 15_000 });
  await expect(hint).toContainText("mock");
  // ADR-031：幽灵提示是中文（让用户自行译成英文，而非抄英文）。
  await expect(hint).toContainText("大城市的公共交通应该免费。");
  await expect(hint).toHaveAttribute("data-ghost-index", "0");
  // 指引只是 DOM widget：字数保持 0，绝不进入文档。
  await expect(page.getByTestId("word-count")).toHaveText("0 词");

  // ADR-025：开关在构思助手面板，关闭后隐藏，开启后恢复。
  await page.getByTestId("ghost-toggle").click();
  await expect(page.getByTestId("ghost-hint")).toHaveCount(0);
  await page.getByTestId("ghost-toggle").click();
  await expect(page.getByTestId("ghost-hint")).toBeVisible({ timeout: 15_000 });

  // ADR-033：位置定位——完成一句英文 → 索引推进到 1。
  await page.getByTestId("editor-content").click();
  await page.keyboard.type("Public transport should be free.");
  await expect(page.getByTestId("ghost-hint")).toHaveAttribute("data-ghost-index", "1", {
    timeout: 20_000,
  });
  // 再写一句 → 索引推进到 2。
  await page.keyboard.type(" Free buses and trains reduce private car use.");
  await expect(page.getByTestId("ghost-hint")).toHaveAttribute("data-ghost-index", "2", {
    timeout: 20_000,
  });
  // 删除回退到一句（Ctrl+A 重写）→ 索引回退到 1（修复删除后定位错）。
  await page.keyboard.press("Control+a");
  await page.keyboard.type("Public transport should be free.");
  await expect(page.getByTestId("ghost-hint")).toHaveAttribute("data-ghost-index", "1", {
    timeout: 20_000,
  });
});

test("ghost insight card shows pre-extracted expressions + pattern; click adds to KB (ADR-037)", async ({
  page,
}) => {
  await openNewEssay(page, "Ghost insight essay");
  await page.getByTestId("planner-input").fill("我同意大城市公共交通应该免费。");
  await page.getByTestId("planner-send").click();
  await expect(page.getByTestId("planner-outline-card").first()).toBeVisible({ timeout: 20_000 });
  await page.getByTestId("confirm-outline").first().click();
  await expect(page.getByTestId("planner-outline-card").first()).toContainText("已确认", {
    timeout: 15_000,
  });

  await page.getByTestId("editor-content").click();
  await expect(page.getByTestId("ghost-hint")).toBeVisible({ timeout: 15_000 });

  // 打开注释卡：注释在范文生成时预提取，打开零 LLM 调用。
  await page.getByTestId("ghost-insight-open").click();
  const insight = page.getByTestId("ghost-insight-card");
  await expect(insight).toBeVisible({ timeout: 10_000 });
  await expect(insight).toContainText("第 1 句");
  const expressions = page.getByTestId("ghost-insight-expressions");
  await expect(expressions).toContainText("public transport");
  await expect(expressions).toContainText("公共交通");
  const pattern = page.getByTestId("ghost-insight-pattern");
  await expect(pattern).toContainText("情态动词被动");
  await expect(pattern).toContainText("should be");

  // 点击表达 → 加入知识库。
  await page.getByTestId("ghost-expression-public transport").click();
  await expect(page.getByTestId("ghost-expression-added")).toBeVisible({ timeout: 10_000 });
  await page.goto("/knowledge");
  await expect(page.getByTestId("kb-item").first()).toContainText("public transport", {
    timeout: 10_000,
  });

  // 回到编辑器：指引推进后，旧句子的卡片自动消失（渲染条件失效）。
  await page.goBack();
  await expect(page.getByTestId("ghost-hint")).toBeVisible({ timeout: 15_000 });
  await page.getByTestId("ghost-insight-open").click();
  await expect(page.getByTestId("ghost-insight-card")).toBeVisible({ timeout: 10_000 });
  // 卡片悬浮在编辑器上方会拦截点击（Esc/✕ 可关）；用 focus 取得焦点继续输入。
  await page.getByTestId("editor-content").focus();
  await page.keyboard.type("Public transport should be free.");
  await expect(page.getByTestId("ghost-hint")).toHaveAttribute("data-ghost-index", "1", {
    timeout: 20_000,
  });
  await expect(page.getByTestId("ghost-insight-card")).toHaveCount(0);
});

test("study planner workflow confirms suggestions", async ({ page }) => {
  await register(page);
  await page.goto("/learning");
  await expect(page.getByTestId("study-planner")).toBeVisible();

  await page.getByTestId("planner-goal").fill("三个月达到 7 分");
  await page.getByTestId("generate-plan").click();
  await expect(page.getByTestId("plan-suggestions")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId("plan-status")).toContainText("等待确认");

  await page.getByTestId("confirm-plan").click();
  await expect(page.getByTestId("plan-done")).toContainText("计划已确认", { timeout: 15_000 });
});

test("study planner can be rejected", async ({ page }) => {
  await register(page);
  await page.goto("/learning");
  await page.getByTestId("generate-plan").click();
  await expect(page.getByTestId("plan-suggestions")).toBeVisible({ timeout: 20_000 });
  await page.getByTestId("reject-plan").click();
  await expect(page.getByTestId("plan-done")).toContainText("计划已拒绝", { timeout: 15_000 });
});
