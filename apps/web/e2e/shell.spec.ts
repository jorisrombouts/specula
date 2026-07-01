import { test, expect } from "@playwright/test";

test("the app renders on warm paper", async ({ page }) => {
  await page.goto("/");
  const bg = await page.evaluate(
    () => getComputedStyle(document.body).backgroundColor,
  );
  // --paper #FBFAF6 == rgb(251, 250, 246)
  expect(bg).toBe("rgb(251, 250, 246)");
});

const ROUTES = [
  { href: "/jobs", label: "jobs" },
  { href: "/approvals", label: "approvals" },
  { href: "/companies", label: "companies" },
  { href: "/insights", label: "insights" },
  { href: "/profiles", label: "profiles" },
  { href: "/targeting", label: "targeting" },
  { href: "/candidate", label: "candidate" },
];

test("/ redirects to /jobs", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/jobs$/);
  await expect(page.locator('[data-screen-label="jobs"]')).toBeVisible();
});

for (const route of ROUTES) {
  test(`renders the ${route.label} view at ${route.href}`, async ({ page }) => {
    await page.goto(route.href);
    await expect(
      page.locator(`[data-screen-label="${route.label}"]`),
    ).toBeVisible();
  });
}

test("the sidebar shows the brand and grouped sections", async ({ page }) => {
  await page.goto("/jobs");
  await expect(page.getByText("Specula")).toBeVisible();
  for (const section of ["Pipeline", "Intelligence", "Configure"]) {
    await expect(page.getByText(section, { exact: true })).toBeVisible();
  }
});

test("the active nav item reflects the current route", async ({ page }) => {
  await page.goto("/companies");
  await expect(page.getByRole("link", { name: /Companies/i })).toHaveAttribute(
    "aria-current",
    "page",
  );
  await expect(page.getByRole("link", { name: /^Jobs$/i })).not.toHaveAttribute(
    "aria-current",
    "page",
  );
});
