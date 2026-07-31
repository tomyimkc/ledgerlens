#!/usr/bin/env node

import crypto from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { chromium } from "playwright";

const root = process.env.LEDGERLENS_ROOT || process.cwd();
const outputRoot = path.resolve(
  process.env.LEDGERLENS_VIDEO_OUTPUT || path.join(root, "artifacts/video"),
);
const planPath = path.resolve(
  process.env.LEDGERLENS_CAPTURE_PLAN ||
    path.join(outputRoot, "capture-plan.json"),
);
const screenshotRoot = path.join(outputRoot, "screenshots");
const rawVideoRoot = path.join(outputRoot, "raw-browser-video");
const finalVideo = path.join(outputRoot, "real-ui-capture.webm");

function expand(value) {
  if (typeof value === "string") {
    return value.replace(/\$\{([A-Z0-9_]+)\}/g, (_, name) => {
      const resolved = process.env[name];
      if (!resolved) {
        throw new Error(`Capture plan requires environment variable ${name}`);
      }
      return resolved;
    });
  }
  if (Array.isArray(value)) {
    return value.map(expand);
  }
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, expand(item)]));
  }
  return value;
}

function publicUrl(value) {
  const parsed = new URL(value);
  return `${parsed.protocol}//${parsed.host}${parsed.pathname}`;
}

async function sha256(file) {
  const bytes = await fs.readFile(file);
  return crypto.createHash("sha256").update(bytes).digest("hex");
}

async function perform(page, action) {
  const timeout = action.timeoutMilliseconds || 15000;
  switch (action.type) {
    case "goto":
      await page.goto(action.url, { waitUntil: "networkidle", timeout });
      return;
    case "click":
      await page.locator(action.selector).click({ timeout });
      return;
    case "tryClick": {
      const locator = page.locator(action.selector);
      if ((await locator.count()) > 0) {
        await locator.first().click({ timeout: Math.min(timeout, 3000) });
      }
      return;
    }
    case "fill":
      await page.locator(action.selector).fill(action.value, { timeout });
      return;
    case "press":
      await page.locator(action.selector).press(action.key, { timeout });
      return;
    case "waitFor":
      await page.locator(action.selector).waitFor({ state: action.state || "visible", timeout });
      return;
    case "scrollIntoView":
      await page.locator(action.selector).scrollIntoViewIfNeeded({ timeout });
      return;
    case "scrollCenter":
      await page.locator(action.selector).evaluate((element) => {
        element.scrollIntoView({ block: "center", behavior: "instant" });
      });
      return;
    case "wait":
      await page.waitForTimeout(action.milliseconds || 1000);
      return;
    case "screenshot": {
      const destination = path.join(screenshotRoot, action.name);
      await page.screenshot({ path: destination, fullPage: Boolean(action.fullPage) });
      return;
    }
    default:
      throw new Error(`Unsupported capture action: ${action.type}`);
  }
}

await fs.mkdir(screenshotRoot, { recursive: true });
await fs.rm(rawVideoRoot, { recursive: true, force: true });
await fs.mkdir(rawVideoRoot, { recursive: true });

const plan = expand(JSON.parse(await fs.readFile(planPath, "utf8")));
const viewport = plan.viewport || { width: 1920, height: 1080 };
const browser = await chromium.launch({
  headless: process.env.LEDGERLENS_CAPTURE_HEADLESS !== "false",
});
const context = await browser.newContext({
  viewport,
  recordVideo: {
    dir: rawVideoRoot,
    size: viewport,
  },
});
const page = await context.newPage();
const video = page.video();
const shots = [];

try {
  for (const shot of plan.shots || []) {
    const started = new Date().toISOString();
    await page.goto(shot.url, {
      waitUntil: "networkidle",
      timeout: shot.timeoutMilliseconds || 30000,
    });
    for (const action of shot.actions || []) {
      await perform(page, action);
    }
    shots.push({
      id: shot.id,
      url: publicUrl(shot.url),
      startedAtUtc: started,
      finishedAtUtc: new Date().toISOString(),
      actionCount: (shot.actions || []).length,
    });
  }
} finally {
  await context.close();
  await browser.close();
}

if (!video) {
  throw new Error("Playwright did not create a browser video.");
}
const recordedPath = await video.path();
await fs.copyFile(recordedPath, finalVideo);

const screenshotFiles = (await fs.readdir(screenshotRoot))
  .filter((name) => name.endsWith(".png"))
  .sort();
const receipt = {
  schemaVersion: "1.0",
  captureKind: "real-ui",
  syntheticProductImitation: false,
  candidateOnly: true,
  canClaimAGI: false,
  capturedAtUtc: new Date().toISOString(),
  viewport,
  shots,
  video: {
    path: path.relative(root, finalVideo),
    sha256: await sha256(finalVideo),
  },
  screenshots: await Promise.all(
    screenshotFiles.map(async (name) => ({
      path: path.relative(root, path.join(screenshotRoot, name)),
      sha256: await sha256(path.join(screenshotRoot, name)),
    })),
  ),
  limitations: [
    "This receipt records browser capture, not independent validation.",
    "Operators must verify that live DataHub shots are not deterministic fixture output.",
  ],
};
await fs.writeFile(
  path.join(outputRoot, "capture-receipt.json"),
  `${JSON.stringify(receipt, null, 2)}\n`,
);
console.log(`Real UI capture written to ${finalVideo}`);
