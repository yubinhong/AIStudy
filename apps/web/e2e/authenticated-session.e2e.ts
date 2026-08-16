import { randomBytes } from "node:crypto";

import {
  expect,
  request,
  test,
  type Locator,
  type Page,
} from "@playwright/test";

const apiUrl = `http://127.0.0.1:${Number(
  process.env.STUDY_E2E_API_PORT ?? "18080",
)}`;

function runtimeSecret(prefix: string) {
  return `${prefix}-${randomBytes(12).toString("hex")}!9a`;
}

async function fillSecret(locator: Locator, value: string) {
  await locator.evaluate((element, nextValue) => {
    const input = element as HTMLInputElement;
    const setter = Object.getOwnPropertyDescriptor(
      HTMLInputElement.prototype,
      "value",
    )?.set;
    if (!setter) throw new Error("input value setter is unavailable");
    setter.call(input, nextValue);
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
  }, value);
}

async function login(page: Page, username: string, password: string) {
  await page.goto("/login");
  await page.getByLabel("用户名").fill(username);
  await fillSecret(page.getByLabel("密码"), password);
  await page.getByRole("button", { name: "登录" }).click();
}

async function changePassword(
  page: Page,
  currentPassword: string,
  nextPassword: string,
) {
  await expect(page).toHaveURL(/\/first-password$/);
  await fillSecret(page.getByLabel("当前密码"), currentPassword);
  await fillSecret(
    page.getByLabel("新密码（至少 12 位）", { exact: true }),
    nextPassword,
  );
  await page.getByRole("button", { name: "保存新密码" }).click();
  await expect(page).toHaveURL(/\/$/);
}

async function logout(page: Page) {
  await page.getByLabel(/当前账号：/).click();
  await page.getByRole("button", { name: "退出登录" }).click();
  await expect(page).toHaveURL(/\/login$/);
}

test("真实 Cookie 会话完成首次改密、跨家庭角色和双孩子作用域", async ({
  context,
  page,
}) => {
  const bootstrapPassword = ["admin", "123456"].join("");
  const adminPassword = runtimeSecret("admin-e2e");
  const parentInitialPassword = runtimeSecret("parent-initial");
  const parentPassword = runtimeSecret("parent-e2e");
  const childPassword = runtimeSecret("child-e2e");
  const suffix = randomBytes(5).toString("hex");
  const parentUsername = `parent-${suffix}`;
  const firstChildName = `语文孩子-${suffix}`;
  const secondChildName = `数学孩子-${suffix}`;

  await test.step("未登录访问受保护页面时跳转登录", async () => {
    await page.goto("/accounts");
    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByRole("heading", { name: "欢迎回来" })).toBeVisible();
  });

  let bootstrapSession = "";
  let adminHouseholdId = "";
  await test.step("一次性管理员登录后数据仍受阻并建立安全 Cookie", async () => {
    await login(page, "admin", bootstrapPassword);
    await expect(page).toHaveURL(/\/first-password$/);

    const cookies = await context.cookies();
    const session = cookies.find((cookie) => cookie.name === "study_session");
    const csrf = cookies.find((cookie) => cookie.name === "study_csrf");
    expect(session).toMatchObject({ httpOnly: true, sameSite: "Lax" });
    expect(csrf).toMatchObject({ httpOnly: false, sameSite: "Lax" });
    bootstrapSession = session?.value ?? "";
    expect(bootstrapSession).not.toBe("");

    const blocked = await page.request.get("/api/children");
    expect(blocked.status()).toBe(403);

    const csrfRejected = await page.request.post("/api/children/management", {
      data: {
        display_name: "不会创建",
        grade: 3,
        curriculum_version: "e2e",
        subjects: ["math"],
        username: `blocked-${suffix}`,
        password: childPassword,
      },
      headers: { "Idempotency-Key": `e2e-blocked-${suffix}` },
    });
    expect(csrfRejected.status()).toBe(403);
  });

  await test.step("首次改密轮换 Session 并撤销引导会话", async () => {
    await changePassword(page, bootstrapPassword, adminPassword);
    await expect(
      page.getByRole("heading", { name: "今天，先关注这几件事" }),
    ).toBeVisible();

    const sessionResponse = await page.request.get("/api/auth/session");
    expect(sessionResponse.ok()).toBe(true);
    const account = (await sessionResponse.json()) as {
      household_id: string;
      role: string;
    };
    expect(account.role).toBe("super_admin");
    adminHouseholdId = account.household_id;

    const currentSession = (await context.cookies()).find(
      (cookie) => cookie.name === "study_session",
    )?.value;
    expect(currentSession).toBeTruthy();
    expect(currentSession).not.toBe(bootstrapSession);

    const staleRequest = await request.newContext({
      baseURL: apiUrl,
      extraHTTPHeaders: { cookie: `study_session=${bootstrapSession}` },
    });
    expect((await staleRequest.get("/auth/me")).status()).toBe(401);
    await staleRequest.dispose();
  });

  await test.step("超级管理员开通独立家庭及首个普通家长", async () => {
    await page.goto("/family");
    await expect(
      page.getByRole("heading", { name: "家庭与家长账号" }),
    ).toBeVisible();
    await page.getByLabel("新家庭家长用户名").fill(parentUsername);
    await fillSecret(
      page.getByLabel("初始密码（至少 12 位）", { exact: true }),
      parentInitialPassword,
    );
    await page.getByRole("button", { name: "开通家庭并创建家长" }).click();
    await expect(page.getByRole("status")).toHaveText(
      "家庭已开通，新家长首次登录时需要修改密码",
    );
    await expect(page.getByText(parentUsername, { exact: true })).toBeVisible();
  });

  await test.step("退出会撤销服务端 Session", async () => {
    const activeSession = (await context.cookies()).find(
      (cookie) => cookie.name === "study_session",
    )?.value;
    expect(activeSession).toBeTruthy();
    await logout(page);

    const revokedRequest = await request.newContext({
      baseURL: apiUrl,
      extraHTTPHeaders: { cookie: `study_session=${activeSession}` },
    });
    expect((await revokedRequest.get("/auth/me")).status()).toBe(401);
    await revokedRequest.dispose();
  });

  await test.step("普通家长首次改密后没有超级管理员导航", async () => {
    await login(page, parentUsername, parentInitialPassword);
    await changePassword(page, parentInitialPassword, parentPassword);
    await expect(page.getByRole("link", { name: "家庭权限" })).toHaveCount(0);

    const forbidden = await page.request.get("/api/auth/family-parents");
    expect(forbidden.status()).toBe(403);

    const account = (await (
      await page.request.get("/api/auth/session")
    ).json()) as {
      household_id: string;
      role: string;
    };
    expect(account.role).toBe("parent");
    expect(account.household_id).not.toBe(adminHouseholdId);

    const crossHousehold = await page.request.get(
      `${apiUrl}/households/${adminHouseholdId}/children`,
    );
    expect(crossHousehold.status()).toBe(404);
  });

  await test.step("普通家长创建两个学科配置不同的孩子", async () => {
    await page.goto("/accounts");
    await page.getByLabel("孩子姓名").fill(firstChildName);
    await page.getByLabel("年级").selectOption("4");
    await page.getByLabel("孩子登录用户名").fill(`chinese-${suffix}`);
    await fillSecret(
      page.getByLabel("初始密码（至少 8 位）", { exact: true }),
      childPassword,
    );
    await page.getByLabel("同时启用语文学科").check();
    await page.getByRole("button", { name: "创建孩子档案与账号" }).click();
    await expect(page.getByRole("status")).toHaveText("孩子档案和账号已创建");

    await page.getByLabel("孩子姓名").fill(secondChildName);
    await page.getByLabel("年级").selectOption("2");
    await page.getByLabel("孩子登录用户名").fill(`math-${suffix}`);
    await fillSecret(
      page.getByLabel("初始密码（至少 8 位）", { exact: true }),
      childPassword,
    );
    await page.getByRole("button", { name: "创建孩子档案与账号" }).click();
    await expect(page.getByRole("status")).toHaveText("孩子档案和账号已创建");

    const chineseCard = page.locator("article.profile-card").filter({
      hasText: firstChildName,
    });
    const mathCard = page.locator("article.profile-card").filter({
      hasText: secondChildName,
    });
    await expect(chineseCard).toContainText("小学4年级");
    await expect(chineseCard.getByLabel("启用语文")).toBeChecked();
    await expect(mathCard).toContainText("小学2年级");
    await expect(mathCard.getByLabel("启用语文")).not.toBeChecked();
  });

  await test.step("当前孩子切换保持显式 child 作用域", async () => {
    const childrenResponse = await page.request.get("/api/children");
    expect(childrenResponse.ok()).toBe(true);
    const children = (await childrenResponse.json()) as Array<{
      display_name: string;
      id: string;
    }>;
    expect(children).toHaveLength(2);
    const secondChild = children.find(
      (child) => child.display_name === secondChildName,
    );
    expect(secondChild).toBeTruthy();

    await page.getByLabel(/当前孩子：/).click();
    await page.getByRole("link", { name: new RegExp(secondChildName) }).click();
    await expect(page).toHaveURL(
      new RegExp(`\/accounts\\?child=${secondChild?.id}$`),
    );
    await expect(
      page.getByLabel(new RegExp(`当前孩子：${secondChildName}`)),
    ).toBeVisible();
  });

  await test.step("普通家长退出后受保护页面再次跳转登录", async () => {
    await logout(page);
    expect((await page.request.get("/api/auth/session")).status()).toBe(401);
    await page.goto("/accounts");
    await expect(page).toHaveURL(/\/login$/);
  });
});
