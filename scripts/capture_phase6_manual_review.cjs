const { chromium } = require("../apps/web/node_modules/@playwright/test");
const { pathToFileURL } = require("node:url");
const path = require("node:path");
const fs = require("node:fs");

const root = path.resolve(__dirname, "..");
const review = path.join(root, "evaluation", "reports", "manual-review", "index.html");
const screenshots = path.join(root, "evaluation", "reports", "manual-review", "screenshots");
const documents = ["multi-column-01", "multi-column-02", "tables-01", "tables-02", "invoice-receipt-01", "invoice-receipt-02", "multi-page-01", "multi-page-02"];

(async () => {
  fs.mkdirSync(screenshots, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1100 }, deviceScaleFactor: 1 });
  await page.goto(pathToFileURL(review).href, { waitUntil: "load" });
  for (const documentId of documents) {
    await page.locator(`#document-${documentId}`).screenshot({ path: path.join(screenshots, `${documentId}.png`) });
  }
  await browser.close();
})().catch((error) => { console.error(error); process.exitCode = 1; });
