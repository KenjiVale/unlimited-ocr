import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
const root = new URL("../", import.meta.url);
const read = (path) => readFile(new URL(path, root), "utf8");
const checks = [];
async function check(name, fn) {
  await fn();
  checks.push(name);
}

await check("API client exposes safe result download URLs", async () => {
  const source = await read("lib/api.ts");
  assert.match(source, /jobs\/\$\{id\}\/download\/\$\{kind\}/);
  assert.match(source, /statusLabel/);
});

await check("upload UI exposes conditional PDF DPI choices", async () => {
  const source = await read("app/page.tsx");
  assert.match(source, /pdf_dpi/);
  assert.match(source, /150/);
  assert.match(source, /200/);
  assert.match(source, /300/);
});

await check("job detail includes terminal polling and recovery actions", async () => {
  const source = await read("app/jobs/[jobId]/page.tsx");
  assert.match(source, /activeStatuses/);
  assert.match(source, /clearInterval/);
  assert.match(source, /Retry page/);
  assert.match(source, /Integrity/);
});

console.log(`${checks.length} frontend smoke checks passed`);
