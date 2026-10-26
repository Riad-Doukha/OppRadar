import { expect, test, type Page } from "@playwright/test";

// Public pages only — the API is mocked, so this runs in CI without
// Supabase or the backend. (The signed-in journey is journey.spec.ts.)

const API = "http://localhost:8000";

const opportunity = (over: Record<string, unknown>) => ({
  id: crypto.randomUUID(),
  external_id: null,
  title: "Algiers AI Summit Hackathon",
  organizer: "Sahara Tech Events",
  type: "hackathon",
  mode: "onsite",
  location: "Algiers",
  country: "Algeria",
  language: "en",
  deadline: "2099-11-04",
  funding: "5,000 DZD prize",
  eligibility: [],
  benefits: [],
  summary: "48-hour student hackathon.",
  url: "https://example.org/hack",
  source: "fixture",
  trust_level: "likely_safe",
  scam_flags: [],
  added_via: "pipeline",
  created_at: "2026-10-01T00:00:00Z",
  ...over,
});

/** Mock GET /opportunities; returns the list of query strings the page asked for. */
async function mockOpportunities(page: Page) {
  const asked: URLSearchParams[] = [];
  await page.route(`${API}/opportunities?**`, async (route) => {
    const sp = new URL(route.request().url()).searchParams;
    asked.push(sp);
    const all = [
      opportunity({}),
      opportunity({ title: "Data Science Internship", type: "internship", mode: "remote", organizer: "Yassir" }),
    ];
    const items = all.filter((o) => (!sp.get("type") || o.type === sp.get("type")) && (!sp.get("q") || o.title.toLowerCase().includes(sp.get("q")!.toLowerCase().split(" ")[0])));
    await route.fulfill({ json: { items, total: items.length, limit: 12, offset: 0 } });
  });
  return asked;
}

async function noHorizontalScroll(page: Page) {
  const { sw, w } = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, w: document.documentElement.clientWidth }));
  expect(sw).toBeLessThanOrEqual(w);
}

test.beforeEach(async ({ context }) => {
  // Start every test in English with the system theme.
  await context.addCookies([{ name: "NEXT_LOCALE", value: "en", url: "http://localhost:3000" }]);
});

test("landing page and its search lead to Explore", async ({ page }) => {
  await mockOpportunities(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Find opportunities");
  await page.getByRole("searchbox", { name: "Search opportunities" }).or(page.getByLabel("Search opportunities")).first().fill("hackathon");
  await page.getByRole("button", { name: "Search" }).click();
  await expect(page).toHaveURL(/\/explore\?q=hackathon/);
  await expect(page.getByRole("heading", { name: "Algiers AI Summit Hackathon" })).toBeVisible();
  await expect(page.getByText("1 open opportunity")).toBeVisible();
});

test("Explore filters by type through the URL and the API", async ({ page }) => {
  const asked = await mockOpportunities(page);
  await page.goto("/explore");
  await expect(page.getByText("2 open opportunities")).toBeVisible();
  await page.getByRole("button", { name: "Internship", exact: true }).click();
  await expect(page).toHaveURL(/type=internship/);
  await expect(page.getByRole("heading", { name: "Data Science Internship" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Algiers AI Summit Hackathon" })).toHaveCount(0);
  expect(asked.some((sp) => sp.get("type") === "internship")).toBe(true);
  // Details need an account: the login page keeps where to come back to.
  await page.getByRole("link", { name: "View details" }).first().click();
  await expect(page).toHaveURL(/\/login\?next=%2Fopportunities%2F/);
});

test("switching to French, then Arabic (right-to-left), is remembered", async ({ page }) => {
  await mockOpportunities(page);
  await page.goto("/");
  await page.getByRole("button", { name: /Change language/ }).click();
  await page.getByRole("menuitemradio", { name: "Français" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Trouvez des opportunités");
  await expect(page.locator("html")).toHaveAttribute("lang", "fr");

  await page.reload();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Trouvez des opportunités");

  await page.getByRole("button", { name: /Changer de langue/ }).click();
  await page.getByRole("menuitemradio", { name: "العربية" }).click();
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("اعثر على فرص");
});

test("dark mode toggle applies and survives a reload", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "light" });
  await page.goto("/");
  const html = page.locator("html");
  await expect(html).not.toHaveClass(/dark/);
  await page.getByRole("button", { name: "Switch to dark mode" }).click();
  await expect(html).toHaveClass(/dark/);
  await page.reload();
  await expect(html).toHaveClass(/dark/);
  await page.getByRole("button", { name: "Switch to light mode" }).click();
  await expect(html).not.toHaveClass(/dark/);
});

test("signed-in pages send visitors to log in", async ({ page }) => {
  for (const path of ["/dashboard", "/settings", "/admin", "/submit", "/premium"]) {
    await page.goto(path);
    await expect(page).toHaveURL(new RegExp(`/login\\?next=${encodeURIComponent(path).replace(/\//g, "%2F")}`));
  }
  await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();
});

test("sign-up checks the form before calling the server", async ({ page }) => {
  let authCalls = 0;
  await page.route("**/auth/v1/**", (route) => {
    authCalls++;
    return route.abort();
  });
  await page.goto("/signup");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByText("Enter your full name.")).toBeVisible();
  await expect(page.getByText("Enter a valid email.")).toBeVisible();
  await expect(page.getByText("Please accept the Terms and Privacy Policy.")).toBeVisible();
  await page.getByLabel("Password", { exact: true }).fill("short");
  await expect(page.getByText("Use at least 8 characters.")).toBeVisible();
  expect(authCalls).toBe(0);
});

test("phone: the navbar is in a drawer @phone", async ({ page }) => {
  await mockOpportunities(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Open menu" }).click();
  const drawer = page.getByRole("dialog", { name: "Menu" });
  await expect(drawer.getByRole("link", { name: "Explore" })).toBeVisible();
  await expect(drawer.getByRole("link", { name: "Log in" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(drawer).toBeHidden();
});

test("phone: landing and Explore fit the screen @phone", async ({ page }) => {
  await mockOpportunities(page);
  for (const path of ["/", "/explore", "/login", "/signup"]) {
    await page.goto(path);
    await expect(page.locator("main").first()).toBeVisible();
    await noHorizontalScroll(page);
  }
});
