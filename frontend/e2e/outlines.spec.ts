import { expect, test, type Page } from "@playwright/test";

/**
 * Outlines & workflows E2E (Slice 8): plan generation → confirmation → left
 * panel + ghost-text insertion (user-initiated only), and the personalized
 * study planner workflow with human confirmation. Mock LLM on the E2E stack.
 */

const PASSWORD = "SecurePassword123";

function uniqueEmail(): string {
  return `e2e-outline-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
}

async function register(page: Page): Promise<void> {
  await page.goto("/register");
  await page.getByLabel("Email").fill(uniqueEmail());
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/profile/);
}

async function openNewEssay(page: Page, title: string): Promise<void> {
  await register(page);
  await page.getByRole("link", { name: "Dashboard" }).click();
  await page.getByTestId("new-essay").click();
  await page.getByTestId("essay-title-input").fill(title);
  await page.getByTestId("submit-create").click();
  await expect(page.getByTestId("create-dialog")).toBeHidden();
  await page.getByTestId("essay-title").click();
  await expect(page).toHaveURL(/\/essays\/[0-9a-f-]{36}/);
  await expect(page.getByTestId("editor-content")).toBeVisible();
}

test("plan generation, confirmation, panel and ghost-text insertion", async ({ page }) => {
  await openNewEssay(page, "Planned essay");

  await page.getByTestId("open-planner").click();
  await expect(page.getByTestId("outline-planner-dialog")).toBeVisible();
  await page.getByTestId("outline-viewpoint").fill("Public transport should be free.");
  await page.getByTestId("generate-outline").click();

  const draft = page.getByTestId("outline-draft");
  await expect(draft).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId("outline-tree-plan")).toContainText("·");
  await page.getByTestId("confirm-outline").click();
  await expect(page.getByTestId("outline-planner-dialog")).toBeHidden({ timeout: 15_000 });

  // Confirmed plan appears in the left panel.
  await expect(page.getByTestId("confirmed-plan")).toBeVisible({ timeout: 15_000 });

  // Ghost text is a hint only; insertion happens on explicit click.
  const hint = page.getByTestId("ghost-text-hint");
  await expect(hint).toBeVisible();
  const ideaText = (await hint.innerText()).replace("Next idea from your plan: ", "").trim();
  await page.getByTestId("insert-ghost-text").click();
  await expect(page.getByTestId("editor-content")).toContainText(ideaText.slice(0, 30));
});

test("study planner workflow confirms suggestions", async ({ page }) => {
  await register(page);
  await page.goto("/learning");
  await expect(page.getByTestId("study-planner")).toBeVisible();

  await page.getByTestId("planner-goal").fill("Reach band 7");
  await page.getByTestId("generate-plan").click();
  await expect(page.getByTestId("plan-suggestions")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId("plan-status")).toContainText("awaiting_confirmation");

  await page.getByTestId("confirm-plan").click();
  await expect(page.getByTestId("plan-done")).toContainText("Plan confirmed", { timeout: 15_000 });
});

test("study planner can be rejected", async ({ page }) => {
  await register(page);
  await page.goto("/learning");
  await page.getByTestId("generate-plan").click();
  await expect(page.getByTestId("plan-suggestions")).toBeVisible({ timeout: 20_000 });
  await page.getByTestId("reject-plan").click();
  await expect(page.getByTestId("plan-done")).toContainText("Plan rejected", { timeout: 15_000 });
});
