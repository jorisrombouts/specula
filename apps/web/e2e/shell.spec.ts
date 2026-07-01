import { test, expect } from "@playwright/test";

test("an unauthenticated visit to an app route redirects to sign-in", async ({
  page,
}) => {
  await page.goto("/jobs");
  await expect(page).toHaveURL(/\/signin$/);
});

test("the root redirects an unauthenticated user to sign-in", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/signin$/);
});

test("the sign-in page renders on warm paper with a Google button", async ({
  page,
}) => {
  await page.goto("/signin");
  const bg = await page.evaluate(
    () => getComputedStyle(document.body).backgroundColor,
  );
  // --paper #FBFAF6 == rgb(251, 250, 246)
  expect(bg).toBe("rgb(251, 250, 246)");
  await expect(
    page.getByRole("button", { name: /sign in with google/i }),
  ).toBeVisible();
});
