import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("public core screens pass automated accessibility checks", async ({
  page,
}) => {
  for (const route of ["/", "/sign-in", "/analyze?mode=text"]) {
    await page.goto(route);
    await expect(page.getByRole("main")).toBeVisible();
    const result = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
      .analyze();
    expect(
      result.violations.map((v) => ({
        id: v.id,
        impact: v.impact,
        nodes: v.nodes.map((n) => n.target),
      })),
      route,
    ).toEqual([]);
  }
});
