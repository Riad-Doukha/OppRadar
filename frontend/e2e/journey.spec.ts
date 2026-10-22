import { expect, test } from "@playwright/test";

import { createUser, deleteUser, hasSupabase } from "./support/supabase";

// The whole signed-in journey against the real Supabase project and API
// (run locally: `npm run e2e:full`). A throwaway account is created here and
// deleted at the end — through the app's own "Delete my account".

test.skip(!hasSupabase, "needs SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY in the root .env");
test.describe.configure({ mode: "serial" });

let user: Awaited<ReturnType<typeof createUser>>;

test.beforeAll(async () => {
  user = await createUser("Journey Tester");
});

test.afterAll(async () => {
  if (user) await deleteUser(user.id);
});

test.beforeEach(async ({ context }) => {
  await context.addCookies([{ name: "NEXT_LOCALE", value: "en", url: "http://localhost:3000" }]);
});

test("log in, set up the profile, use the app, delete the account", async ({ page }) => {
  test.setTimeout(240_000);

  await test.step("log in → setup wizard", async () => {
    await page.goto("/login");
    await page.getByLabel("Email").fill(user.email);
    await page.getByLabel("Password", { exact: true }).fill(user.password);
    await page.getByRole("button", { name: "Log in" }).click();
    await expect(page).toHaveURL(/\/onboarding/);
    await expect(page.getByText("STEP 1 OF 5")).toBeVisible();
  });

  await test.step("step 1: about you", async () => {
    await expect(page.getByLabel("Full name *")).toHaveValue("Journey Tester");
    await page.getByLabel("Birth year *").fill("2004");
    await page.getByLabel("Nationality *").fill("Algerian");
    await page.getByLabel("Country *").fill("Algeria");
    await page.getByLabel("Wilaya *").selectOption("Oran");
    await page.getByRole("button", { name: "Continue" }).click();
    await expect(page.getByText("STEP 2 OF 5")).toBeVisible();
  });

  await test.step("step 2: education", async () => {
    await page.getByLabel("Education level *").selectOption("licence");
    await page.getByLabel("Field of study *").fill("Computer Science");
    await page.getByLabel("Current year", { exact: true }).selectOption("2");
    await page.getByRole("button", { name: "Continue" }).click();
    await expect(page.getByText("STEP 3 OF 5")).toBeVisible();
  });

  await test.step("step 3: skills & interests", async () => {
    const skill = page.getByPlaceholder("Type a skill");
    for (const s of ["Python", "SQL", "Statistics"]) {
      await skill.fill(s);
      await skill.press("Enter");
    }
    const interest = page.getByPlaceholder("Add an interest…");
    await interest.fill("Data");
    await interest.press("Enter");
    await page.getByText("Hackathon", { exact: true }).click();
    await page.getByText("Internship", { exact: true }).click();
    await page.getByLabel("Preferred location *").selectOption("algeria");
    await page.getByRole("button", { name: "Continue" }).click();
    await expect(page.getByText("STEP 4 OF 5")).toBeVisible();
  });

  await test.step("step 4: goal", async () => {
    await page.getByLabel(/Goal \*/).fill("I want to join hackathons and find a data internship in Oran.");
    await page.getByRole("button", { name: "Continue" }).click();
    await expect(page.getByText("STEP 5 OF 5")).toBeVisible();
  });

  await test.step("step 5: alerts & consent → review", async () => {
    const terms = page.getByRole("checkbox", { name: /I agree to the Terms/ });
    if (!(await terms.isChecked())) await terms.check();
    await page.getByRole("checkbox", { name: "The agent uses my profile to find matches" }).check();
    await page.getByRole("button", { name: "Finish setup" }).click();
    await expect(page.getByText("SETUP COMPLETE")).toBeVisible();
  });

  await test.step("start the agent → first scan → dashboard", async () => {
    await page.getByRole("button", { name: "Start my agent" }).click();
    await expect(page.getByText("Your agent is starting its first scan")).toBeVisible();
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 30_000 });
    await expect(page.getByRole("heading", { level: 1 })).toContainText("Journey");
  });

  let title = "";
  await test.step("save an opportunity → Saved tab", async () => {
    const card = page.locator("article").first();
    title = (await card.getByRole("heading").textContent()) ?? "";
    await card.getByRole("button", { name: "Save" }).click();
    await expect(card.getByRole("button", { name: "Saved" })).toBeVisible();
    await page.getByRole("tab", { name: /Saved/ }).click();
    await expect(page.getByRole("heading", { name: title })).toBeVisible();
  });

  await test.step("apply assistant → recorded → Applications", async () => {
    await page.locator("article").first().getByRole("link", { name: "View details" }).click();
    await expect(page.getByRole("heading", { level: 1, name: title })).toBeVisible();
    await page.getByRole("link", { name: "Apply assistant" }).click();
    await expect(page.getByText("Your answers, ready to copy")).toBeVisible();
    await page.getByLabel("Reference number").fill("E2E-42");
    await page.getByRole("button", { name: "I've submitted it" }).click();
    await expect(page.getByRole("heading", { name: "Application recorded" })).toBeVisible();
    await page.getByRole("link", { name: /Go to my applications/ }).click();
    await expect(page.getByRole("link", { name: title })).toBeVisible();
    await expect(page.getByLabel("Reference").first()).toHaveValue("E2E-42");
  });

  await test.step("Premium: reserve early access, then cancel", async () => {
    await page.goto("/premium");
    await expect(page.getByText("PREVIEW — Premium is coming soon")).toBeVisible();
    await page.getByRole("link", { name: /Reserve early access/ }).click();
    await expect(page).toHaveURL(/\/premium\/checkout/);
    await expect(page.getByText("Total today")).toBeVisible();
    await expect(page.getByText("0 DZD", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Reserve early access — free" }).click();
    await expect(page.getByRole("heading", { name: "You're on the list" })).toBeVisible();
    await page.getByRole("button", { name: "Cancel reservation" }).click();
    await page.getByRole("button", { name: "Yes, cancel" }).click();
    await expect(page.getByRole("heading", { name: "Reservation cancelled" })).toBeVisible();
  });

  await test.step("delete the account from Settings", async () => {
    await page.goto("/settings");
    await page.getByRole("button", { name: "Delete account" }).click();
    await page.getByLabel("Type DELETE to confirm").fill("DELETE");
    await page.getByRole("button", { name: "Delete permanently" }).click();
    await expect(page).toHaveURL(/\/\?deleted=1/);
    await expect(page.getByText("Your account and all its data have been deleted.")).toBeVisible();
  });
});
