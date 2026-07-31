#!/usr/bin/env node

import crypto from "node:crypto";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import process from "node:process";
import { pathToFileURL } from "node:url";

const root = path.resolve(process.env.LEDGERLENS_ROOT || process.cwd());
const outputRoot = path.resolve(
  process.env.LEDGERLENS_EVIDENCE_VIDEO_OUTPUT ||
    path.join(root, "artifacts/video/evidence-first"),
);
const screenshotRoot = path.join(outputRoot, "screenshots");
const receiptRoot = path.join(outputRoot, "public-receipts");
const spaceUrl =
  process.env.LEDGERLENS_PUBLIC_SPACE_URL ||
  "https://tomyimkc-ledgerlens-incident-commander.hf.space/";
const healthUrl = new URL("/healthz", spaceUrl).toString();
const githubIssueUrl = "https://github.com/tomyimkc/ledgerlens/issues/3";
const rawBase = "https://raw.githubusercontent.com/tomyimkc/ledgerlens/main/";

const publicReceipts = {
  aiVerification: "benchmarks/incident_commander/ai-verification-receipt.json",
  githubLiveAction: "benchmarks/incident_commander/github-live-action-receipt.json",
  datahubLiveWriteback:
    "benchmarks/incident_commander/datahub-live-writeback-receipt.json",
  contextAblation: "benchmarks/incident_commander/context-ablation-receipt.json",
};

async function exists(candidate) {
  try {
    await fs.access(candidate);
    return true;
  } catch {
    return false;
  }
}

async function findPlaywrightPackage() {
  const configured = process.env.PLAYWRIGHT_PACKAGE;
  const candidates = [
    configured,
    path.join(root, "artifacts/video-tools/node_modules/playwright"),
  ].filter(Boolean);

  const pnpmRoot = path.join(
    os.homedir(),
    ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/.pnpm",
  );
  if (await exists(pnpmRoot)) {
    for (const entry of await fs.readdir(pnpmRoot)) {
      if (entry.startsWith("playwright@")) {
        candidates.push(path.join(pnpmRoot, entry, "node_modules/playwright"));
      }
    }
  }

  const npxRoot = path.join(os.homedir(), ".npm/_npx");
  if (await exists(npxRoot)) {
    for (const entry of await fs.readdir(npxRoot)) {
      candidates.push(path.join(npxRoot, entry, "node_modules/playwright"));
    }
  }

  for (const candidate of candidates) {
    if (candidate && (await exists(path.join(candidate, "index.mjs")))) {
      return candidate;
    }
  }
  return null;
}

async function loadPlaywright() {
  try {
    return await import("playwright");
  } catch {
    const packageRoot = await findPlaywrightPackage();
    if (!packageRoot) {
      throw new Error(
        "Playwright was not found. Set PLAYWRIGHT_PACKAGE to a playwright package directory " +
          "or install the isolated capture tools.",
      );
    }
    return import(pathToFileURL(path.join(packageRoot, "index.mjs")).href);
  }
}

function sha256(bytes) {
  return crypto.createHash("sha256").update(bytes).digest("hex");
}

async function fetchBytes(url) {
  const response = await fetch(url, {
    headers: {
      "User-Agent": "LedgerLens evidence-first video capture",
      Accept: "application/json,text/plain;q=0.9,*/*;q=0.8",
    },
  });
  if (!response.ok) {
    throw new Error(`GET ${url} failed with HTTP ${response.status}`);
  }
  return Buffer.from(await response.arrayBuffer());
}

async function fetchJson(url) {
  return JSON.parse((await fetchBytes(url)).toString("utf8"));
}

async function screenshotAt(page, selector, name, offset = 92) {
  const locator = page.locator(selector).first();
  await locator.waitFor({ state: "visible", timeout: 30000 });
  await locator.evaluate(
    (element, topOffset) => {
      const top = element.getBoundingClientRect().top + window.scrollY - topOffset;
      window.scrollTo({ top: Math.max(0, top), behavior: "instant" });
    },
    offset,
  );
  await page.waitForTimeout(600);
  const destination = path.join(screenshotRoot, name);
  await page.screenshot({ path: destination, fullPage: false });
  return destination;
}

async function addCaptureStyle(page) {
  await page.addStyleTag({
    content: `
      * { animation: none !important; transition: none !important; }
      html { scroll-behavior: auto !important; }
      ::-webkit-scrollbar { width: 0 !important; height: 0 !important; }
    `,
  });
}

await fs.mkdir(screenshotRoot, { recursive: true });
await fs.mkdir(receiptRoot, { recursive: true });

const health = await fetchJson(healthUrl);
if (
  health.mode !== "fixture" ||
  health.externalMutations !== false ||
  health.candidateOnly !== true ||
  health.canClaimAGI !== false
) {
  throw new Error(`Unexpected public Space health boundary: ${JSON.stringify(health)}`);
}

const downloaded = {};
for (const [key, relativePath] of Object.entries(publicReceipts)) {
  const url = `${rawBase}${relativePath}`;
  const bytes = await fetchBytes(url);
  const localPath = path.join(receiptRoot, path.basename(relativePath));
  await fs.writeFile(localPath, bytes);
  const payload = JSON.parse(bytes.toString("utf8"));
  if (payload.candidateOnly !== true || payload.canClaimAGI !== false) {
    throw new Error(`${relativePath} violates the claim boundary`);
  }
  downloaded[key] = {
    url,
    repositoryPath: relativePath,
    localPath: path.relative(root, localPath),
    sha256: sha256(bytes),
    bytes: bytes.length,
    payload,
  };
}

const { chromium } = await loadPlaywright();
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 1920, height: 1080 },
  deviceScaleFactor: 1,
  colorScheme: "dark",
  locale: "en-US",
  bypassCSP: true,
});
const page = await context.newPage();
const screenshotFiles = [];

try {
  await page.goto(spaceUrl, { waitUntil: "networkidle", timeout: 60000 });
  await addCaptureStyle(page);
  await page.locator("[data-testid='fixture-label']").waitFor();
  screenshotFiles.push(
    await screenshotAt(page, "body", "01-space-hero.png", 0),
  );
  screenshotFiles.push(
    await screenshotAt(page, "[data-testid='datahub-context']", "02-space-context.png"),
  );
  screenshotFiles.push(
    await screenshotAt(page, "[data-testid='planner-output']", "03-space-plan-verifier.png"),
  );

  const trigger = page.locator("[data-trigger-incident]");
  await Promise.all([
    page.waitForNavigation({ waitUntil: "networkidle", timeout: 60000 }),
    trigger.click(),
  ]);
  await addCaptureStyle(page);
  await page.locator("[data-testid='action-fanout']").waitFor();
  const fixtureReceiptCount = await page.locator("text=fixture://").count();
  if (fixtureReceiptCount < 4) {
    throw new Error(`Expected at least four visible fixture receipts; found ${fixtureReceiptCount}`);
  }
  screenshotFiles.push(
    await screenshotAt(page, "[data-testid='action-fanout']", "04-space-fixture-actions.png"),
  );
  screenshotFiles.push(
    await screenshotAt(page, "[data-testid='datahub-writeback']", "05-space-writeback.png"),
  );
  screenshotFiles.push(
    await screenshotAt(page, "[data-testid='agent-memory']", "06-space-memory.png"),
  );

  const githubPage = await context.newPage();
  await githubPage.goto(githubIssueUrl, { waitUntil: "networkidle", timeout: 60000 });
  await addCaptureStyle(githubPage);
  await githubPage.getByText(
    "[LedgerLens rehearsal] Autonomous incident receipt 2026-07-31T08:13:22+00:00",
    { exact: true },
  ).first().waitFor({ state: "visible", timeout: 30000 });
  await githubPage.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
  await githubPage.waitForTimeout(800);
  const issueShot = path.join(screenshotRoot, "07-github-issue.png");
  await githubPage.screenshot({ path: issueShot, fullPage: false });
  screenshotFiles.push(issueShot);
  await githubPage.close();
} finally {
  await context.close();
  await browser.close();
}

const issueReceipt = downloaded.githubLiveAction.payload;
const datahubReceipt = downloaded.datahubLiveWriteback.payload;
const aiReceipt = downloaded.aiVerification.payload;
const benchmarkReceipt = downloaded.contextAblation.payload;

const captureReceipt = {
  schemaVersion: "1.0",
  capturedAtUtc: new Date().toISOString(),
  candidateOnly: true,
  canClaimAGI: false,
  publicSpace: {
    url: spaceUrl,
    healthUrl,
    health,
    evidenceClass: "live-host-fixture-replay",
  },
  evidence: {
    github: {
      evidenceClass: "live-external-mutation",
      publicIssueUrl: githubIssueUrl,
      remoteUrl: issueReceipt.providerReceipt.remote_url,
      status: issueReceipt.providerReceipt.status,
      closure: issueReceipt.closure,
      limitations: issueReceipt.limitations,
    },
    datahub: {
      evidenceClass: "live-datahub-oss-writeback",
      status: datahubReceipt.status,
      tool: datahubReceipt.tool,
      urn: datahubReceipt.result.urn,
      retrieved: datahubReceipt.nextAgentRetrieval.retrieved,
      retrievalVia: datahubReceipt.nextAgentRetrieval.via,
      limitations: datahubReceipt.limitations,
    },
    aiVerification: {
      evidenceClass: "live-ai-advisory-rehearsal",
      status: aiReceipt.status,
      authorized: aiReceipt.authorization.authorized,
      planner: aiReceipt.models.planner,
      verifiers: aiReceipt.models.verifiers,
      providerFamilyIndependenceClaimed:
        aiReceipt.models.providerFamilyIndependenceClaimed,
      limitations: aiReceipt.limitations,
    },
    benchmark: {
      evidenceClass: "deterministic-fixture-benchmark",
      contextSource: benchmarkReceipt.contextSource,
      liveDataHub: benchmarkReceipt.liveDataHub,
      assetCount: benchmarkReceipt.catalog.assetCount,
      scenarioCount: benchmarkReceipt.catalog.scenarioCount,
      comparison: benchmarkReceipt.comparison,
      limitations: benchmarkReceipt.limitations,
    },
  },
  publicReceipts: Object.fromEntries(
    Object.entries(downloaded).map(([key, item]) => [
      key,
      {
        url: item.url,
        repositoryPath: item.repositoryPath,
        localPath: item.localPath,
        sha256: item.sha256,
        bytes: item.bytes,
      },
    ]),
  ),
  screenshots: await Promise.all(
    screenshotFiles.map(async (file) => {
      const bytes = await fs.readFile(file);
      return {
        path: path.relative(root, file),
        sha256: sha256(bytes),
        bytes: bytes.length,
      };
    }),
  ),
  limitations: [
    "The public Space capture proves hosted reachability while showing fixture replay state.",
    "Receipt cards are rendered from bytes downloaded from the public GitHub main branch.",
    "The capture does not independently validate incident causality, user impact, or recovery.",
  ],
};

await fs.writeFile(
  path.join(outputRoot, "public-evidence.json"),
  `${JSON.stringify(captureReceipt, null, 2)}\n`,
);
console.log(`Evidence capture complete: ${outputRoot}`);
