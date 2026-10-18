import { expect, test } from "@playwright/test";

const FOOTER =
  "Built for Graph Hacks with FalkorDB · Decision support for genetic counsellors. Not medical advice. · ClinVar data: NCBI monthly archives, public · People, families, clinicians and organisations shown are fictional.";

for (const width of [375, 1280]) {
  test(`layout at ${width}px shows the footer disclaimer`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/");
    await expect(page.getByText("Recontact").first()).toBeVisible();
    await expect(page.getByRole("link", { name: "What changed" })).toBeVisible();
    await expect(page.getByRole("link", { name: "How it works" })).toBeVisible();
    await expect(page.getByText("Demo lab (fictional)")).toBeVisible();
    await expect(page.getByText(FOOTER)).toBeVisible();
    await page.screenshot({
      path: `../../docs/evidence/g008-${width}.png`,
      fullPage: true,
    });
  });
}
