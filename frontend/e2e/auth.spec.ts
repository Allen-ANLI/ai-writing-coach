import { expect, test, type Page } from "@playwright/test";

/**
 * Frontend authentication E2E against the isolated stack defined in
 * playwright.config.ts (backend :8001 + test DB + 2s access-token TTL,
 * frontend :3600). Every test uses a unique user.
 */

const PASSWORD = "SecurePassword123";
const BACKEND = "http://localhost:8001/api/v1";

function uniqueEmail(): string {
  return `e2e-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
}

async function registerViaApi(
  request: import("@playwright/test").APIRequestContext,
  email: string,
): Promise<void> {
  const response = await request.post(`${BACKEND}/auth/register`, {
    data: { email, password: PASSWORD },
  });
  expect(response.status()).toBe(201);
}

async function registerViaUi(page: Page, email: string): Promise<void> {
  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel(/Display name/).fill("E2E User");
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/profile/);
}

test("register signs the user in and shows the profile", async ({ page }) => {
  const email = uniqueEmail();
  await registerViaUi(page, email);

  await expect(page.getByTestId("profile-email")).toHaveText(email);
  await expect(page.getByTestId("display-name")).toHaveText("E2E User");
  await expect(page.getByTestId("session-list")).toBeVisible();
});

test("login with valid credentials reaches the protected profile", async ({ page, request }) => {
  const email = uniqueEmail();
  await registerViaApi(request, email);

  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect(page).toHaveURL(/\/profile/);
  await expect(page.getByTestId("profile-email")).toHaveText(email);
});

test("login with a wrong password shows an error and stays signed out", async ({ page, request }) => {
  const email = uniqueEmail();
  await registerViaApi(request, email);

  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("WrongPassword123");
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect(page.getByTestId("auth-error")).toHaveText("Invalid email or password.");
  await expect(page).toHaveURL(/\/login/);
});

test("session survives a full page reload (silent refresh restore)", async ({ page }) => {
  const email = uniqueEmail();
  await registerViaUi(page, email);

  await page.reload();

  await expect(page.getByTestId("profile-email")).toHaveText(email);
});

test("expired access token is refreshed automatically without user action", async ({ page }) => {
  const email = uniqueEmail();
  await registerViaUi(page, email);

  // E2E backend issues 2-second access tokens.
  await page.waitForTimeout(3_000);
  await page.getByTestId("refresh-data").click();

  // The 401 -> single-flight refresh -> retry path recovers transparently.
  await expect(page.getByTestId("profile-email")).toHaveText(email);
  await expect(page.getByTestId("session-list")).toBeVisible();
  await expect(page).toHaveURL(/\/profile/);
});

test("concurrent 401s trigger exactly one refresh request", async ({ page }) => {
  const email = uniqueEmail();
  await registerViaUi(page, email);
  await page.waitForTimeout(3_000);

  let refreshCount = 0;
  page.on("request", (request) => {
    if (request.method() === "POST" && request.url().endsWith("/auth/refresh")) {
      refreshCount += 1;
    }
  });

  // Refetches me + sessions in parallel: two 401s, one shared refresh.
  await page.getByTestId("refresh-data").click();
  await expect(page.getByTestId("profile-email")).toHaveText(email);
  await expect(page.getByTestId("session-list")).toBeVisible();
  await page.waitForTimeout(500);

  expect(refreshCount).toBe(1);
});

test("failed refresh clears the session and redirects to login", async ({ page, context }) => {
  const email = uniqueEmail();
  await registerViaUi(page, email);
  await page.waitForTimeout(3_000);

  // Remove the HttpOnly refresh cookie: the next refresh must fail.
  await context.clearCookies();
  await page.getByTestId("refresh-data").click();

  await expect(page).toHaveURL(/\/login/);
});

test("logout revokes the session so it cannot be restored", async ({ page }) => {
  const email = uniqueEmail();
  await registerViaUi(page, email);

  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login/);

  // Neither a reload nor a direct visit may resurrect the session.
  await page.reload();
  await expect(page).toHaveURL(/\/login/);
  await page.goto("/profile");
  await expect(page).toHaveURL(/\/login/);
});

test("anonymous visitors are redirected from protected pages to login", async ({ page }) => {
  await page.goto("/profile");
  await expect(page).toHaveURL(/\/login/);
});

test("authenticated users can navigate directly to the protected profile", async ({ page, request }) => {
  const email = uniqueEmail();
  await registerViaApi(request, email);

  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/profile/);

  await page.goto("/profile");
  await expect(page.getByTestId("profile-email")).toHaveText(email);
});

test("refresh cookie is HttpOnly/Secure/SameSite=Strict and invisible to JavaScript", async ({
  page,
  context,
}) => {
  const email = uniqueEmail();
  await registerViaUi(page, email);

  const jsVisibleCookies = await page.evaluate(() => document.cookie);
  expect(jsVisibleCookies).not.toContain("awc_refresh_token");

  const cookies = await context.cookies();
  const refreshCookie = cookies.find((cookie) => cookie.name === "awc_refresh_token");
  expect(refreshCookie).toBeDefined();
  expect(refreshCookie?.httpOnly).toBe(true);
  expect(refreshCookie?.secure).toBe(true);
  expect(refreshCookie?.sameSite).toBe("Strict");
  expect(refreshCookie?.path).toBe("/api/v1/auth");
});
