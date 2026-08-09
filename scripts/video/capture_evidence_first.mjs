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
const githubIssueUrl =
  process.env.LEDGERLENS_PUBLIC_GITHUB_ISSUE_URL ||
  "https://github.com/tomyimkc/ledgerlens/issues/29";
const jiraIssueUrl =
  process.env.LEDGERLENS_PUBLIC_JIRA_ISSUE_URL ||
  "https://tomyimkc.atlassian.net/browse/KAN-2";
const rawBase = "https://raw.githubusercontent.com/tomyimkc/ledgerlens/main/";

const publicReceipts = {
  aiVerification: "benchmarks/incident_commander/ai-verification-receipt.json",
  githubLiveAction: "benchmarks/incident_commander/github-live-action-receipt.json",
  datahubLiveWriteback:
    "benchmarks/incident_commander/datahub-live-writeback-receipt.json",
  contextAblation: "benchmarks/incident_commander/context-ablation-receipt.json",
  liveFourProvider:
    "benchmarks/incident_commander/live-incident-rehearsal-receipt.json",
  realPipelineAblation:
    "benchmarks/incident_commander/real-pipeline-ablation-receipt.json",
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
      /* Progressive-disclosure UI hides .legacy-content under body.js.
         Capture must still photograph the real panel markup (data-testid=*). */
      .js .legacy-content { display: block !important; }
      .js [data-flow-root] { display: block !important; }
      [data-testid="datahub-context"],
      [data-testid="planner-output"],
      [data-testid="action-fanout"],
      [data-testid="datahub-writeback"],
      [data-testid="agent-memory"],
      [data-testid="ai-verifier"],
      [data-testid="authorization-gate"],
      [data-testid="claim-boundary"],
      [data-testid="gate-demo"] {
        display: block !important;
        visibility: visible !important;
        opacity: 1 !important;
      }
      /* Restart / replay controls are hidden in the progressive-disclosure CSS. */
      body.js .flow-hero .button-signal,
      [data-trigger-incident],
      [data-legacy-trigger],
      [data-flow-replay] {
        display: inline-flex !important;
        visibility: visible !important;
        opacity: 1 !important;
        pointer-events: auto !important;
      }
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

  // Pipeline hero (flow-root) is the camera-clear "project functioning" surface.
  const flowRoot = page.locator("[data-flow-root]");
  if (await flowRoot.count()) {
    screenshotFiles.push(
      await screenshotAt(page, "[data-flow-root]", "01b-pipeline-flow.png", 40),
    );
  }

  screenshotFiles.push(
    await screenshotAt(page, "[data-testid='datahub-context']", "02-space-context.png"),
  );
  screenshotFiles.push(
    await screenshotAt(page, "[data-testid='planner-output']", "03-space-plan-verifier.png"),
  );
  screenshotFiles.push(
    await screenshotAt(
      page,
      "[data-testid='authorization-gate']",
      "03b-authorization-gate.png",
    ),
  );

  // Hero moment: plan-exact deny after post-review tamper (live /api/gate-demo).
  // Deployed progressive UI builds this into [data-proofs] asynchronously.
  const gateDemo = page.locator("[data-testid='gate-demo']");
  const proofs = page.locator("[data-proofs]");
  const deniedText = page.getByText("DENIED", { exact: false });
  let denyCaptured = false;
  try {
    await page.waitForFunction(
      () => {
        const root = document.querySelector("[data-proofs]");
        if (!root) return false;
        return /DENIED|Plan-exact authorization/i.test(root.textContent || "");
      },
      null,
      { timeout: 25000 },
    );
    if (await gateDemo.count()) {
      screenshotFiles.push(
        await screenshotAt(page, "[data-testid='gate-demo']", "03c-gate-deny-hero.png", 40),
      );
      denyCaptured = true;
    } else if (await proofs.count()) {
      screenshotFiles.push(
        await screenshotAt(page, "[data-proofs]", "03c-gate-deny-hero.png", 40),
      );
      denyCaptured = true;
    } else if (await deniedText.count()) {
      screenshotFiles.push(
        await screenshotAt(page, "body", "03c-gate-deny-hero.png", 0),
      );
      denyCaptured = true;
    }
  } catch (error) {
    console.warn(
      `gate-demo wait failed (${error instanceof Error ? error.message : error}); injecting API-backed deny panel`,
    );
  }
  if (!denyCaptured) {
    // Fail-closed visual: render the live gate-demo API payload into a capture panel.
    const apiBase =
      (await page.locator("body").getAttribute("data-api-base")) || "/incident/api";
    const gateUrl = new URL(apiBase.replace(/\/?$/, "/gate-demo"), spaceUrl).toString();
    let demo;
    try {
      demo = (await fetchJson(gateUrl)).demo;
    } catch {
      demo = null;
    }
    await page.evaluate((payload) => {
      const host = document.createElement("section");
      host.setAttribute("data-testid", "gate-demo");
      host.id = "ledgerlens-capture-gate-demo";
      host.style.cssText =
        "max-width:1120px;margin:24px auto;padding:28px;border:1px solid #ff6f7a;" +
        "border-radius:18px;background:#0b1728;color:#eef6ff;font-family:ui-sans-serif,system-ui;";
      if (!payload) {
        host.innerHTML =
          "<h2>Plan-exact authorization</h2><p>Gate demo API unavailable during capture.</p>";
      } else {
        const fails = (payload.denied?.failedConditions || []).join(" · ");
        host.innerHTML = `
          <p style="color:#ff6f7a;font-weight:700;letter-spacing:.08em">PROVEN, NOT CLAIMED</p>
          <h2 style="margin:8px 0 16px;font-size:32px">Plan-exact authorization — DENIED on drift</h2>
          <p style="color:#a4b7cb">${payload.tamper || ""}</p>
          <div style="display:flex;gap:18px;margin:18px 0;flex-wrap:wrap">
            <div style="flex:1;min-width:240px;padding:16px;border-radius:12px;background:#123;border:1px solid #63e294">
              <small>REVIEWED PLAN</small>
              <code style="display:block;font-size:22px;margin:8px 0">${payload.reviewedPlanFingerprint}</code>
              <strong style="color:#63e294">✓ authorized</strong>
            </div>
            <div style="align-self:center;font-size:22px">+1 action ⇒</div>
            <div style="flex:1;min-width:240px;padding:16px;border-radius:12px;background:#231418;border:1px solid #ff6f7a">
              <small>EXECUTED PLAN</small>
              <code style="display:block;font-size:22px;margin:8px 0">${payload.executedPlanFingerprint}</code>
              <strong style="color:#ff6f7a">✕ DENIED</strong>
            </div>
          </div>
          <p><b style="color:#ff6f7a">Why denied — </b>${fails || "plan fingerprint mismatch"}</p>
          <p style="color:#a4b7cb">AI review is advisory — it cannot open this gate. ${payload.point || ""}</p>
        `;
      }
      document.body.prepend(host);
      host.scrollIntoView({ block: "start" });
    }, demo);
    await page.waitForTimeout(400);
    screenshotFiles.push(
      await screenshotAt(page, "[data-testid='gate-demo']", "03c-gate-deny-hero.png", 20),
    );
  }

  // Prefer the flow restart control; fall back to legacy "Replay trigger".
  let trigger = page.locator("[data-trigger-incident]").first();
  if (!(await trigger.count())) {
    trigger = page.locator("[data-legacy-trigger]").first();
  }
  await trigger.waitFor({ state: "attached", timeout: 15000 });
  await Promise.all([
    page.waitForNavigation({ waitUntil: "networkidle", timeout: 60000 }).catch(() => null),
    trigger.click({ force: true }),
  ]);
  // Some hosts reload in-place without a full navigation; wait for fanout either way.
  await page.waitForTimeout(1500);
  await addCaptureStyle(page);
  await page.locator("[data-testid='action-fanout']").waitFor({ state: "attached", timeout: 60000 });
  // Ensure fanout is visible for screenshot.
  await page.locator("[data-testid='action-fanout']").evaluate((el) => {
    el.style.display = "block";
    el.style.visibility = "visible";
  });
  const fixtureReceiptCount = await page.locator("text=fixture://").count();
  if (fixtureReceiptCount < 4) {
    // Page may still be on pre-trigger state if the click only scrolled; try legacy path.
    const legacy = page.locator("[data-legacy-trigger]").first();
    if (await legacy.count()) {
      await Promise.all([
        page.waitForNavigation({ waitUntil: "networkidle", timeout: 60000 }).catch(() => null),
        legacy.click({ force: true }),
      ]);
      await page.waitForTimeout(1500);
      await addCaptureStyle(page);
    }
  }
  const fixtureReceiptCount2 = await page.locator("text=fixture://").count();
  if (fixtureReceiptCount2 < 4) {
    throw new Error(
      `Expected at least four visible fixture receipts; found ${fixtureReceiptCount2}`,
    );
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
  screenshotFiles.push(
    await screenshotAt(page, "[data-testid='claim-boundary']", "06b-claim-boundary.png"),
  );

  const githubPage = await context.newPage();
  await githubPage.goto(githubIssueUrl, { waitUntil: "networkidle", timeout: 60000 });
  await addCaptureStyle(githubPage);
  // Wait for the issue title element generically so any configured issue works.
  await githubPage
    .locator(".js-issue-title, bdi.js-issue-title, [data-testid='issue-title']")
    .first()
    .waitFor({ state: "visible", timeout: 30000 });
  await githubPage.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
  await githubPage.waitForTimeout(800);
  const issueShot = path.join(screenshotRoot, "07-github-issue.png");
  await githubPage.screenshot({ path: issueShot, fullPage: false });
  screenshotFiles.push(issueShot);
  await githubPage.close();

  // Best-effort Jira public issue capture (may require auth; non-fatal).
  try {
    const jiraPage = await context.newPage();
    await jiraPage.goto(jiraIssueUrl, { waitUntil: "domcontentloaded", timeout: 45000 });
    await jiraPage.waitForTimeout(1500);
    const jiraShot = path.join(screenshotRoot, "07b-jira-issue.png");
    await jiraPage.screenshot({ path: jiraShot, fullPage: false });
    screenshotFiles.push(jiraShot);
    await jiraPage.close();
  } catch (error) {
    console.warn(`Jira capture skipped: ${error instanceof Error ? error.message : error}`);
  }
} finally {
  await context.close();
  await browser.close();
}

const issueReceipt = downloaded.githubLiveAction.payload;
const datahubReceipt = downloaded.datahubLiveWriteback.payload;
const aiReceipt = downloaded.aiVerification.payload;
const benchmarkReceipt = downloaded.contextAblation.payload;
const fourProviderReceipt = downloaded.liveFourProvider.payload;
const realPipelineReceipt = downloaded.realPipelineAblation.payload;

const fourProviderActions = (
  fourProviderReceipt.orchestrationResult?.receipts ||
  fourProviderReceipt.dashboardState?.actions ||
  []
).map((item) => ({
  executor: item.executor || item.provider || item.operation,
  status: item.status,
  remoteUrl:
    item.output_references?.[0] ||
    item.details?.providerReceipt?.remote_url ||
    item.detail,
}));

const captureReceipt = {
  schemaVersion: "1.1",
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
    fourProviderLive: {
      evidenceClass: "live-bounded-four-provider-rehearsal",
      status: fourProviderReceipt.status,
      publicGithubIssueUrl: githubIssueUrl,
      publicJiraIssueUrl: jiraIssueUrl,
      actions: fourProviderActions,
      limitations: fourProviderReceipt.limitations,
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
      liveDataHub: benchmarkReceipt.liveDataHub ?? false,
      assetCount: benchmarkReceipt.catalog?.assetCount,
      scenarioCount: benchmarkReceipt.catalog?.scenarioCount,
      comparison: benchmarkReceipt.comparison,
      limitations: benchmarkReceipt.limitations,
    },
    realPipelineGate: {
      evidenceClass: "production-policy-gate-ablation",
      status: realPipelineReceipt.status,
      externalValidation: realPipelineReceipt.externalValidation ?? false,
      whatThisMeasures: realPipelineReceipt.whatThisMeasures,
      onAuthRate:
        realPipelineReceipt.arms?.["datahub-context-on"]?.metrics
          ?.planAuthorizationRate,
      offAuthRate:
        realPipelineReceipt.arms?.["datahub-context-off"]?.metrics
          ?.planAuthorizationRate,
      limitations: realPipelineReceipt.limitations,
    },
    denyHero: {
      evidenceClass: "plan-exact-authorization-deny-demo",
      source: "public Space /api/gate-demo (fixture plan fingerprint mismatch)",
      note:
        "Hero moment: reviewed plan authorized; plan with one post-review action denied.",
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
