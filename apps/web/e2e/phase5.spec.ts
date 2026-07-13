import { expect, test } from "@playwright/test";
import path from "node:path";
import { stat } from "node:fs/promises";

const imageFixture = path.join(__dirname, "fixtures", "sample-image.png");
const pdfFixture = path.join(__dirname, "fixtures", "sample-three-page.pdf");

async function openLatestJob(page: any) {
  await page.goto("/jobs");
  const links = page.locator('a[href^="/jobs/"]');
  await expect(links.first()).toBeVisible({ timeout: 15_000 });
  await links.first().click();
  await expect(page.getByText(/Result|Pages/).first()).toBeVisible({ timeout: 15_000 });
}

test.describe.serial("Phase 5 production browser verification", () => {
  test("renders all operational routes", async ({ page }) => {
    const errors: string[] = [];
    const requests: string[] = [];
    page.on("pageerror", error => errors.push(error.message));
    page.on("request", request => requests.push(request.url()));
    for (const route of ["/", "/jobs", "/system", "/maintenance"]) {
      await page.goto(route);
      await expect(page.locator("h1")).toBeVisible();
    }
    await page.goto("/");
    await expect(page.getByText(/Local processing/i)).toBeVisible();
    await expect(page.getByRole("button", { name: "Preview" })).toBeVisible();
    await page.goto("/jobs");
    await expect(page.getByText(/Jobs|No jobs found/i).first()).toBeVisible();
    await page.goto("/system");
    await expect(page.getByText(/cuda_available|CUDA/i)).toBeVisible();
    await expect(page.getByText(/offline_mode|offline/i)).toBeVisible();
    expect(errors).toEqual([]);
    expect(requests.filter(url => !url.startsWith("http://127.0.0.1:3000") && !url.startsWith("http://127.0.0.1:8000"))).toEqual([]);
  });

  test("completes an image job and verifies result actions", async ({ page }) => {
    await page.goto("/");
    await page.locator('input[type="file"]').setInputFiles(imageFixture);
    await expect(page.locator('input[type="file"]')).toHaveValue(/sample-image\.png/);
    await page.getByRole("button", { name: "Start OCR" }).click();
    await expect(page.getByText(/Completed/)).toBeVisible({ timeout: 180_000 });
    await openLatestJob(page);
    await expect(page.getByText(/Rendered Markdown/)).toBeVisible();
    await expect(page.getByText(/Plain text/)).toBeVisible();
    await expect(page.getByText(/JSON metadata/)).toBeVisible();
    await page.getByRole("button", { name: "Integrity" }).click();
    await expect(page.getByText("Integrity valid")).toBeVisible({ timeout: 15_000 });
    for (const [name, suffix] of [["Download Markdown", ".md"], ["Download TXT", ".txt"], ["Download JSON", ".json"]] as const) {
      const downloadPromise = page.waitForEvent("download");
      await page.getByRole("link", { name }).click();
      const download = await downloadPromise;
      expect(download.suggestedFilename()).toContain(suffix);
      const downloadedPath = await download.path();
      expect(downloadedPath).toBeTruthy();
      expect((await stat(downloadedPath!)).size).toBeGreaterThan(0);
    }
  });

  test("completes a three-page PDF with conditional DPI and page results", async ({ page }) => {
    await page.goto("/");
    await page.locator('input[type="file"]').setInputFiles(pdfFixture);
    await expect(page.locator('input[type="file"]')).toHaveValue(/sample-three-page\.pdf/);
    const dpi = page.getByLabel(/PDF DPI/i);
    await expect(dpi).toBeVisible();
    await dpi.selectOption("200");
    await page.getByRole("button", { name: "Start OCR" }).click();
    await expect(page.getByText(/3\/3/)).toBeVisible({ timeout: 180_000 });
    await expect(page.getByText(/successful 3/)).toBeVisible();
    await openLatestJob(page);
    await expect(page.locator("summary").filter({ hasText: "Page 1:" })).toBeVisible();
    await expect(page.locator("summary").filter({ hasText: "Page 2:" })).toBeVisible();
    await expect(page.locator("summary").filter({ hasText: "Page 3:" })).toBeVisible();
    await page.locator("summary").filter({ hasText: "Page 1:" }).click();
    await page.getByRole("button", { name: "Load page result" }).first().click();
    await expect(page.getByText(/Rendered Markdown/)).toBeVisible();
    await page.getByRole("button", { name: "Integrity" }).click();
    await expect(page.getByText("Integrity valid")).toBeVisible({ timeout: 15_000 });
  });

  test("previews maintenance without executing cleanup", async ({ page }) => {
    await page.goto("/maintenance");
    await page.getByRole("button", { name: "Preview" }).click();
    await expect(page.locator("pre")).toContainText(/rendered|files|jobs/i);
    await expect(page.getByRole("checkbox", { name: /Source files/i })).not.toBeChecked();
    await expect(page.getByRole("checkbox", { name: /Outputs/i })).not.toBeChecked();
  });
});
