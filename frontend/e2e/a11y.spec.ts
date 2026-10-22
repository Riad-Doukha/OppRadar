import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

// Automated accessibility checks (axe-core, WCAG 2.2 A/AA rules) on every
// screen, in light and dark. Public pages run in CI with the API mocked;
// signed-in pages use the demo account and need the API on :8000.

const PUBLIC = ["/", "/explore", "/login", "/signup", "/forgot-password"];
const SIGNED_IN = [
  "/dashboard",
  "/agent",
  "/notifications",
  "/profile",
  "/applications",
  "/settings",
  "/settings?tab=notifications",
  "/settings?tab=privacy",
  "/settings?tab=agent",
  "/premium",
  "/premium/checkout",
  "/submit",
  "/onboarding?step=1",
  "/onboarding?step=3",
  "/onboarding?step=5",
  "/onboarding?step=review",
];

async function audit(page: Page, label: string) {
  // Let skeletons resolve so we check the real content.
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.waitForTimeout(600);
  const { violations } = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .exclude("nextjs-portal") // the dev-only Next.js overlay
    .analyze();
  const report = violations.map((v) => `${v.id} (${v.impact}): ${v.help}\n    ${v.nodes.slice(0, 4).map((n) => n.target.join(" ")).join("\n    ")}`);
  expect(report, `${label}\n${report.join("\n")}`).toEqual([]);
}

for (const scheme of ["light", "dark"] as const) {
  test.describe(`public pages, ${scheme}`, () => {
    test.use({ colorScheme: scheme });
    test.beforeEach(async ({ page, context }) => {
      await context.addCookies([{ name: "NEXT_LOCALE", value: "en", url: "http://localhost:3000" }]);
      await page.route("http://localhost:8000/opportunities?**", (route) =>
        route.fulfill({
          json: {
            items: [
              {
                id: "00000000-0000-4000-8000-000000000001", external_id: null, title: "Algiers AI Summit Hackathon",
                organizer: "Sahara Tech Events", type: "hackathon", mode: "onsite", location: "Algiers", country: "Algeria",
                language: "en", deadline: "2099-11-04", funding: "5,000 DZD prize", eligibility: [], benefits: [],
                summary: "48-hour student hackathon.", url: "https://example.org", source: "fixture", trust_level: "suspicious",
                scam_flags: [], added_via: "pipeline", created_at: "2026-10-01T00:00:00Z",
              },
            ],
            total: 1, limit: 12, offset: 0,
          },
        }),
      );
    });
    for (const path of PUBLIC) test(`${path} @public`, async ({ page }) => {
      await page.goto(path);
      await audit(page, `${path} (${scheme})`);
    });
    test(`/ in Arabic (RTL) @public`, async ({ page, context }) => {
      await context.addCookies([{ name: "NEXT_LOCALE", value: "ar", url: "http://localhost:3000" }]);
      await page.goto("/");
      await audit(page, `/ ar (${scheme})`);
    });
  });

  test.describe(`signed-in pages (demo), ${scheme}`, () => {
    test.use({ colorScheme: scheme });
    test.beforeEach(async ({ page, request, context }) => {
      const demo = await request.post("http://localhost:8000/auth/demo").catch(() => null);
      test.skip(!demo?.ok(), "needs the API on :8000 with the demo account");
      await context.addCookies([{ name: "NEXT_LOCALE", value: "en", url: "http://localhost:3000" }]);
      await page.goto("/login");
      await page.getByRole("button", { name: /Try the demo instead/ }).click();
      await expect(page).toHaveURL(/\/dashboard/);
    });
    for (const path of SIGNED_IN) test(`${path} @signed-in`, async ({ page }) => {
      await page.goto(path);
      await audit(page, `${path} (${scheme})`);
    });
  });
}
