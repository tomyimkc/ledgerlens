(() => {
  "use strict";

  // Scroll-driven incident pipeline. The flowchart pins ("freezes") at the top;
  // as the reader scrolls, each phase reveals below and the pinned flowchart
  // animates a data packet to the next node. No auto-play, no auto-scroll — the
  // scroll position is the only driver. A timeline of DataHub-observed incidents
  // feeds one pipeline, each node mapped to the repo module that handles it. The
  // server still renders the full panels as a no-JS fallback (`.legacy-content`),
  // hidden only once the diagram is ready.
  //
  // Authorization is deterministic: "Evaluating deterministic gate" is shown while
  // the executed fixture state loads — AI cannot open the gate.

  const body = document.body;
  const apiBase = body.dataset.apiBase;
  const root = document.querySelector("[data-flow-root]");
  const timelineEl = document.querySelector("[data-timeline]");
  const pipeEl = document.querySelector("[data-pipe]");
  const logEl = document.querySelector("[data-detail]");
  const replayBtn = document.querySelector("[data-flow-replay]");
  const hintEl = document.querySelector("[data-scrollhint]");
  const GATE = "Evaluating deterministic gate…";

  if (!root || !timelineEl || !pipeEl || !logEl) return; // keep server fallback

  const h = (tag, attrs, ...kids) => {
    const node = document.createElement(tag);
    if (attrs) for (const [k, v] of Object.entries(attrs)) {
      if (v == null) continue;
      if (k === "class") node.className = v;
      else if (k === "text") node.textContent = v;
      else node.setAttribute(k, v);
    }
    for (const kid of kids) if (kid != null) node.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
    return node;
  };
  const arr = (v) => (Array.isArray(v) ? v : []);

  const NODES = [
    { icon: "◎", label: "Trigger", mod: "incident_dashboard", line: (s) => s.trigger },
    { icon: "◇", label: "DataHub context", mod: "mcp_client", line: (s) => (s.ctx ? s.ctx.change + " — read via MCP get_entities" : "Owner · schema · lineage read over MCP") },
    { icon: "▤", label: "Plan", mod: "agent", line: () => "Bounded, reversible actions proposed" },
    { icon: "◈", label: "Verify", mod: "VerifierPanel", line: () => "AI advisory review — cannot authorize" },
    { icon: "⛨", label: "Policy gate", mod: "PolicyGate", line: () => "Deterministic authorization of the exact plan" },
    { icon: "⇶", label: "Act", mod: "action_adapters", line: () => "GitHub · Slack · PagerDuty · Jira" },
    { icon: "⤴", label: "Write-back", mod: "mcp_mutations", line: () => "Incident receipt saved to DataHub" },
    { icon: "⇉", label: "Handoff", mod: "memory", line: () => "Next agent inherits facts + unknowns" },
  ];

  const SCENARIOS = [
    { id: "freshness", day: "Issue 1", sev: 1, type: "Freshness SLO breach", entity: "analytics.payments_daily", trigger: "Freshness 23m over a 15m SLO", featured: true,
      plain: "A payments table that is supposed to refresh every 15 minutes hasn't updated in 23. Every dashboard and risk model built on it is now quietly showing stale numbers.",
      signal: [
        "ASSERTION  freshness.payments_daily        FAILED",
        "  last_loaded_at   2026-07-31T02:51:07Z   (23m ago)",
        "  sla_max_lag      15m",
        "  observed_lag     23m     ✗  +8m over SLO",
        "  downstream       finance.revenue_executive (T1) +2",
      ],
      fix: "Open a tracked incident, page the recorded on-call owner, and post the blast radius to Slack — every action grounded in the DataHub owner + lineage, bounded and reversible.",
      ctx: { owner: "Data Platform", tier: "Tier 1", change: "Freshness assertion breached (observed 23m > 15m SLO)",
        assets: [
          { name: "finance.revenue_executive", criticality: "Tier 1", relationship: "1 hop downstream" },
          { name: "risk.payment_anomaly_features", criticality: "Tier 1", relationship: "2 hops downstream" },
          { name: "growth.checkout_health", criticality: "Tier 1", relationship: "2 hops downstream" }] } },
    { id: "schema", day: "Issue 2", sev: 2, type: "Schema drift", entity: "core.orders_v2", trigger: "Breaking column type change detected",
      plain: "Someone changed the order-total column from a whole number to a decimal. Any table or model that still reads it as a whole number can now break or silently round money.",
      signal: [
        "schemaMetadata  core.orders_v2       BREAKING CHANGE",
        "  - order_total   INT",
        "  + order_total   DECIMAL(12,2)",
        "  affected  analytics.orders_daily (T1)",
        "            ml.churn_features (T1)",
      ],
      fix: "File a schema-change record on the owning team, flag the two downstream models that read the column, and hold any risky action behind the deterministic policy gate.",
      receipts: { act: ["fixture://github/issues/512", "fixture://slack/messages/1712.5521", "fixture://jira/issues/DATA-874"], writeback: "fixture://datahub/writeback/inc-schema-orders/receipt-8c21", memory: "mem-inc-schema-orders-v1" },
      ctx: { owner: "Commerce", tier: "Tier 1", change: "order_total INT → DECIMAL (breaking) in schemaMetadata",
        assets: [
          { name: "analytics.orders_daily", criticality: "Tier 1", relationship: "1 hop downstream" },
          { name: "ml.churn_features", criticality: "Tier 1", relationship: "2 hops downstream" },
          { name: "finance.rev_recognition", criticality: "Tier 2", relationship: "2 hops downstream" }] } },
    { id: "volume", day: "Issue 3", sev: 2, type: "Volume anomaly", entity: "events.clickstream", trigger: "Row count −62% vs baseline",
      plain: "The stream of website click events suddenly dropped to a third of its normal size. Something upstream is dropping data, and every metric built on it will read low.",
      signal: [
        "ASSERTION  volume.clickstream             FAILED",
        "  rows_last_1h     48,210",
        "  baseline_7d_avg  126,900",
        "  delta            −62%    ✗  below −40% floor",
      ],
      fix: "Record the drop, notify the Growth owner, and warn the downstream metrics + ML-training tables. Nothing is 'fixed' automatically — humans decide; receipts are kept.",
      receipts: { act: ["fixture://github/issues/513", "fixture://slack/messages/1712.6033", "fixture://pagerduty/incidents/781"], writeback: "fixture://datahub/writeback/inc-volume-clickstream/receipt-4f90", memory: "mem-inc-volume-clickstream-v1" },
      ctx: { owner: "Growth", tier: "Tier 2", change: "Row-count assertion: −62% vs 7-day baseline",
        assets: [
          { name: "growth.session_metrics", criticality: "Tier 1", relationship: "1 hop downstream" },
          { name: "ml.recommender_train", criticality: "Tier 2", relationship: "2 hops downstream" }] } },
    { id: "access", day: "Issue 4", sev: 1, type: "Access / ACL change", entity: "pii.customers", trigger: "Ownership and ACL changed on PII",
      plain: "The permissions on a table full of customer personal data were just widened to everyone, and its owner was cleared. That is a potential privacy and security exposure.",
      signal: [
        "ownership + policy  pii.customers    ⚠ SENSITIVE",
        "  - grant  role:trust-safety    SELECT",
        "  + grant  role:all-employees   SELECT",
        "  - owner  trust-safety@team",
        "  + owner  (unset)",
      ],
      fix: "Raise a SEV-1, page Trust & Safety, and file an access-review ticket. It never edits the ACL itself — widening or narrowing access is out of its allowlist by design.",
      receipts: { act: ["fixture://pagerduty/incidents/782", "fixture://slack/messages/1712.6644", "fixture://jira/issues/SEC-231"], writeback: "fixture://datahub/writeback/inc-access-pii/receipt-a7d3", memory: "mem-inc-access-pii-v1" },
      ctx: { owner: "Trust & Safety", tier: "Tier 1", change: "Ownership + ACL widened on a PII dataset",
        assets: [
          { name: "support.customer_360", criticality: "Tier 1", relationship: "1 hop downstream" },
          { name: "marketing.audiences", criticality: "Tier 2", relationship: "2 hops downstream" }] } },
    { id: "deploy", day: "Issue 5", sev: 1, type: "Upstream deploy break", entity: "finance.revenue_dashboard", trigger: "dbt deploy invalidated the model",
      plain: "A code change upstream (a dbt model deploy) removed a filter, so the finance revenue dashboard is now built on the wrong rows — and the board pack reads straight from it.",
      signal: [
        "deploy  dbt:rev_model @ a1f9c2      INVALIDATED",
        "  revenue_recognized AS (",
        "  -   WHERE status = 'recognized'",
        "  +   -- filter removed in this deploy",
        "  )",
        "  stale → finance.revenue_dashboard → exec.board_pack (T1)",
      ],
      fix: "Link the incident to the exact deploy commit, page Finance, and open a rollback/repair ticket. The fix stays with the owning engineer, with a full receipt trail.",
      receipts: { act: ["fixture://github/issues/514", "fixture://slack/messages/1712.7120", "fixture://jira/issues/FIN-560"], writeback: "fixture://datahub/writeback/inc-deploy-rev/receipt-2b58", memory: "mem-inc-deploy-rev-v1" },
      ctx: { owner: "Finance", tier: "Tier 1", change: "Upstream dbt model deploy (rev_model) marked stale",
        assets: [
          { name: "exec.board_pack", criticality: "Tier 1", relationship: "1 hop downstream" },
          { name: "finance.daily_close", criticality: "Tier 2", relationship: "2 hops downstream" }] } },
    { id: "ingest", day: "Issue 6", sev: 3, type: "Ingestion failure", entity: "vendor.billing_feed", trigger: "Connector run failed; lineage stale",
      plain: "The nightly job that pulls a vendor's billing data failed, so the feed is stale. Anything that reconciles money against it — the accounts-receivable ledger — is now out of date.",
      signal: [
        "ingestion  vendor-billing-cdc            FAILED",
        "  connector     billing_feed",
        "  error         ConnectorError: source 402 auth expired",
        "  lastObserved  2026-07-30T23:10Z   (28h stale)",
      ],
      fix: "Record the failed run, notify Vendor Ops, and flag the AR ledger as running on stale data — so no one closes the books on numbers that never actually arrived.",
      receipts: { act: ["fixture://github/issues/515", "fixture://slack/messages/1712.7788", "fixture://jira/issues/OPS-419"], writeback: "fixture://datahub/writeback/inc-ingest-billing/receipt-9e42", memory: "mem-inc-ingest-billing-v1" },
      ctx: { owner: "Vendor Ops", tier: "Tier 3", change: "Ingestion run failed; systemMetadata.lastObserved stale",
        assets: [
          { name: "finance.ar_ledger", criticality: "Tier 2", relationship: "1 hop downstream" }] } },
  ];

  let backend = null;
  let liveReceipts = {};
  let current = SCENARIOS[0];
  let nodes = [];
  let arrows = [];
  let active = -1;
  let runTimer = null;
  let mode = "walk";

  // ---- timeline ------------------------------------------------------------
  const buildTimeline = () => {
    timelineEl.replaceChildren();
    for (const s of SCENARIOS) {
      const card = h("button", { class: "tevent", type: "button", "aria-label": s.type },
        h("span", { class: "tday", text: s.day }),
        h("span", { class: "ttype", text: s.type }),
        h("span", { class: "tent", text: s.entity }),
        h("span", { class: "tsev sev" + s.sev, text: "SEV-" + s.sev }),
        hasRealRun(s) ? h("span", { class: "tstar", text: "★ backed by a real run" }) : null);
      card.addEventListener("click", () => { current = s; paintTimeline(); stopRun(); setMode("walk"); buildStory(); active = -1; setActive(0); });
      timelineEl.append(card);
    }
  };
  const paintTimeline = () => {
    timelineEl.querySelectorAll(".tevent").forEach((c, i) => c.classList.toggle("on", SCENARIOS[i].id === current.id));
  };

  // ---- pinned flowchart ----------------------------------------------------
  const buildPipe = () => {
    pipeEl.replaceChildren();
    nodes = []; arrows = [];
    NODES.forEach((n, i) => {
      const node = h("button", { class: "pnode", type: "button", "aria-label": n.label },
        h("span", { class: "pnode-icon", text: n.icon }),
        h("span", { class: "pnode-label", text: n.label }),
        h("code", { class: "pnode-mod", text: n.mod }));
      node.addEventListener("click", () => { stopRun(); setMode("walk"); setActive(i); });
      pipeEl.append(node);
      nodes.push(node);
      if (i < NODES.length - 1) {
        const arrow = h("span", { class: "parrow" }, h("span", { class: "packet", "aria-hidden": "true" }));
        pipeEl.append(arrow);
        arrows.push(arrow);
      }
    });
  };

  const flowArrow = (i) => {
    const a = arrows[i];
    if (!a) return;
    a.classList.remove("flowing");
    void a.offsetWidth; // restart the packet animation
    a.classList.add("flowing");
  };

  const paintDiagram = (i) => {
    nodes.forEach((node, k) => {
      node.classList.toggle("active", k === i);
      node.classList.toggle("done", k < i);
    });
    arrows.forEach((a, k) => a.classList.toggle("filled", k < i));
  };

  // ---- DataHub-forward extras ----------------------------------------------
  const mcpBadge = (tool) => h("span", { class: "logtag mcp" }, "MCP · ", h("code", { text: tool }));

  const lineageGraph = () => {
    const be = (backend && backend.context) || {};
    const ctx = current.ctx || {};
    const owner = ctx.owner || be.entity?.owner || "Data Platform";
    const tier = ctx.tier || be.entity?.tier || "Tier 1";
    const assets = (ctx.assets && ctx.assets.length) ? ctx.assets : arr(be.blast_radius && be.blast_radius.assets);
    const g = h("div", { class: "lineage" });
    g.append(h("div", { class: "lin-node src" },
      h("b", { text: current.entity || be.entity?.name || "entity" }),
      h("small", { text: tier + " · " + owner })));
    g.append(h("div", { class: "lin-arrow", "aria-hidden": "true", text: "⇢" }));
    const col = h("div", { class: "lin-col" });
    for (const a of assets.slice(0, 4)) {
      col.append(h("div", { class: "lin-node t" + (String(a.criticality || "").includes("1") ? "1" : "2") },
        h("b", { text: a.name }), h("small", { text: a.relationship || "" })));
    }
    if (col.childElementCount) g.append(col);
    return g;
  };

  // Plain-language situation + a concrete "what went wrong" data/code block + the fix,
  // shown at the Trigger step so an outsider grasps each incident before the flow runs.
  const situationCard = () => {
    const s = current;
    const card = h("div", { class: "situation" });
    if (s.plain) card.append(h("p", { class: "sit-plain" }, h("b", { text: "In plain terms — " }), s.plain));
    if (s.signal && s.signal.length) {
      card.append(h("div", { class: "sit-signal" },
        h("div", { class: "sit-cap", text: "WHAT DATAHUB SAW · fixture" }),
        h("pre", { class: "sit-code", text: s.signal.join("\n") })));
    }
    if (s.fix) card.append(h("p", { class: "sit-fix" }, h("b", { text: "How LedgerLens responds — " }), s.fix));
    return card;
  };

  const hasRealRun = (s) => !!(s && liveReceipts && liveReceipts[s.id]);

  const chipRow = (values) => {
    const wrap = h("div", { class: "chips" });
    for (const v of arr(values)) if (v) wrap.append(h("code", { class: "chip", text: v }));
    return wrap.childElementCount ? wrap : null;
  };

  // Real-run receipts: linked and verifiable where the provider returns a URL.
  const realChipRow = (actions) => {
    const wrap = h("div", { class: "chips" });
    for (const a of arr(actions)) {
      if (!a || !a.receipt) continue;
      const label = (a.provider ? a.provider + " · " : "") + String(a.receipt);
      wrap.append(a.url
        ? h("a", { class: "chip chip-real", href: a.url, target: "_blank", rel: "noopener", text: label })
        : h("code", { class: "chip chip-real", text: label }));
    }
    return wrap.childElementCount ? wrap : null;
  };

  const receiptChips = (i) => {
    // Real executed run (published by build_live_receipts_index.py) takes precedence.
    const live = liveReceipts[current.id];
    if (live) {
      if (i === 5) return realChipRow(live.actions);
      if (i === 6 && live.writeback) return chipRow([live.writeback]);
      if (i === 7 && live.memory) return chipRow([live.memory]);
      return null;
    }
    // Featured scenario: the backend executed the deterministic fixture pipeline.
    if (current.featured && backend) {
      if (i === 5) return chipRow(arr(backend.actions).map((a) => a.receipt));
      if (i === 6 && backend.writeback?.receipt) return chipRow([backend.writeback.receipt]);
      if (i === 7 && backend.memory?.memory_id) return chipRow([backend.memory.memory_id]);
      return null;
    }
    // Other scenarios: deterministic simulated fixture receipts.
    const r = current.receipts;
    if (!r) return null;
    if (i === 5) return chipRow(r.act);
    if (i === 6 && r.writeback) return chipRow([r.writeback]);
    if (i === 7 && r.memory) return chipRow([r.memory]);
    return null;
  };

  // Persistent per-incident facts shown beside every stage (no scrolling to find them).
  const factsRail = () => {
    const s = current;
    const be = (backend && backend.context) || {};
    const ctx = s.ctx || {};
    const assets = (ctx.assets && ctx.assets.length) ? ctx.assets : arr(be.blast_radius && be.blast_radius.assets);
    const rail = h("aside", { class: "facts-rail" });
    rail.append(h("div", { class: "fact-hd" }, h("span", { class: "fact-sev sev" + s.sev, text: "SEV-" + s.sev }), h("strong", { text: s.type })));
    rail.append(h("div", { class: "fact-row" }, h("small", { text: "ENTITY" }), h("code", { text: s.entity })));
    rail.append(h("div", { class: "fact-row" }, h("small", { text: "OWNER" }), h("span", { text: (ctx.owner || be.entity?.owner || "—") + " · " + (ctx.tier || be.entity?.tier || "—") })));
    rail.append(h("div", { class: "fact-row" }, h("small", { text: "BLAST RADIUS" }), h("span", { text: assets.length + " downstream asset" + (assets.length === 1 ? "" : "s") })));
    const real = hasRealRun(s);
    rail.append(h("div", { class: "fact-run " + (real ? "real" : "sim") },
      h("small", { text: real ? "★ BACKED BY A REAL RUN" : "SIMULATED FIXTURE" }),
      h("span", { text: real ? "Real provider receipts — click to verify" : "Illustrative — real run pending" })));
    return rail;
  };

  // ---- one compact stage panel (Run / click drives progress; no page scroll) ----
  const buildStep = (i) => {
    const n = NODES[i];
    const top = h("div", { class: "logtop" },
      h("span", { class: "logicon", text: n.icon }),
      h("strong", { text: n.label }),
      h("code", { class: "logmod", text: n.mod }));
    if (i === 1) top.append(mcpBadge("get_entities"));
    if (i === 4) top.append(h("span", { class: "logtag", text: "AI can't authorize" }));
    if (i === 6) top.append(mcpBadge("save_document"));
    const bodyEl = h("div", { class: "logbody" }, top, h("p", { class: "logline", text: n.line(current) }));
    if (i === 0) bodyEl.append(situationCard());
    if (i === 1 && backend && backend.context) bodyEl.append(lineageGraph());
    if (i === 6) {
      const wb = h("p", { class: "dhback" }, "↳ writes the incident receipt back to DataHub via save_document (MCP mutation).");
      wb.append(" A real DataHub OSS write + official-MCP read-back was also recorded 2026-07-31 — ",
        h("a", { href: "https://github.com/tomyimkc/ledgerlens/blob/main/docs/EVIDENCE_INDEX.md", target: "_blank", rel: "noopener", text: "evidence (E-07)" }));
      bodyEl.append(wb);
    }
    const chips = receiptChips(i);
    if (chips) bodyEl.append(chips);
    if (i === 5 && hasRealRun(current)) bodyEl.append(h("p", { class: "dhback" },
      "↳ real four-provider run — click a receipt above to verify, or see the ",
      h("a", { href: "https://github.com/tomyimkc/ledgerlens/blob/main/docs/EVIDENCE_INDEX.md", target: "_blank", rel: "noopener", text: "evidence index" }),
      ". One bounded rehearsal action each; a receipt does not prove recovery."));
    if (i === 5 && !hasRealRun(current)) bodyEl.append(h("p", { class: "dnote", text: "Simulated fixture receipts — illustrative. Run this incident live (make run-all-incidents-live) to back it with real, clickable receipts." }));
    const row = h("div", { class: "logrow", "data-i": String(i) },
      h("div", { class: "logmark" }, h("span", { class: "lognum", text: (i + 1).toString().padStart(2, "0") })),
      bodyEl,
      factsRail());
    return row;
  };

  // All eight stages are built once; only the active one is shown (CSS), so the
  // whole flow lives on one page. Run / click / arrows move the active stage.
  const buildStory = () => {
    logEl.replaceChildren();
    for (let i = 0; i < NODES.length; i++) logEl.append(buildStep(i));
  };

  const setActive = (i) => {
    i = Math.max(0, Math.min(NODES.length - 1, i));
    const advancing = i > active;
    active = i;
    paintDiagram(i);
    logEl.querySelectorAll(".logrow").forEach((r) => r.classList.toggle("active", Number(r.dataset.i) === i));
    if (advancing && i > 0) flowArrow(i - 1);
  };

  // ---- run controller + mode toggle (replaces the scroll driver) -----------
  const stopRun = () => { if (runTimer) { clearTimeout(runTimer); runTimer = null; } root.classList.remove("running"); };
  const stepRun = () => {
    if (active >= NODES.length - 1) { stopRun(); return; }
    setActive(active + 1);
    runTimer = setTimeout(stepRun, 1050);
  };
  const runFlow = () => { setMode("walk"); stopRun(); active = -1; setActive(0); root.classList.add("running"); runTimer = setTimeout(stepRun, 700); };
  const resetFlow = () => { stopRun(); setMode("walk"); active = -1; setActive(0); };

  const MODES = [
    { key: "walk", label: "Walkthrough" },
    { key: "proofs", label: "Why it wins" },
    { key: "compare", label: "How it compares" },
    { key: "code", label: "How it works" },
  ];
  const tabButtons = {};
  function setMode(m) {
    if (m !== "walk") stopRun();
    mode = m;
    root.dataset.mode = m;
    for (const key of Object.keys(tabButtons)) tabButtons[key].classList.toggle("on", key === m);
    if (m === "walk") setActive(active < 0 ? 0 : active);
  }

  const buildControls = () => {
    if (!hintEl) return;
    const runB = h("button", { class: "ctl ctl-run", type: "button" }, h("span", { "aria-hidden": "true", text: "▶" }), " Run");
    const resetB = h("button", { class: "ctl", type: "button" }, h("span", { "aria-hidden": "true", text: "↺" }), " Restart");
    runB.addEventListener("click", runFlow);
    resetB.addEventListener("click", resetFlow);
    const tabs = h("div", { class: "ctl-grp tabs" });
    for (const m of MODES) {
      const btn = h("button", { class: "ctl tab" + (m.key === "walk" ? " on" : ""), type: "button", text: m.label });
      btn.addEventListener("click", () => setMode(m.key));
      tabButtons[m.key] = btn;
      tabs.append(btn);
    }
    hintEl.replaceChildren(h("div", { class: "ctl-grp" }, runB, resetB), tabs);
    hintEl.classList.add("controls");
    hintEl.classList.remove("gone");
    buildCompare();
    buildCode();
  };

  // ---- honest three-way comparison (matches README §"not the Actions Framework") ----
  // DataHub already detects (assertions), holds context (lineage/owner/tier), and fires
  // pre-wired automations (Actions Framework). This does NOT claim DataHub can't act — it
  // positions LedgerLens as the middle path between fixed rules and a self-authorizing agent.
  const CMP_ROWS = [
    ["Chooses the response", "Human, at config time", "Model, at run time", "Model proposes, at run time"],
    ["Approves execution", "Human, at config time (fixed rule)", "Model approves itself", "Deterministic policy — not the model"],
    ["Handles a novel incident", "No — only pre-wired rules", "Yes", "Yes"],
    ["Binds approval to the exact plan", "n/a", "No", "Yes — exact plan fingerprint"],
    ["Rejects off-allowlist / ungrounded actions", "n/a", "Best-effort in the prompt", "Fail-closed, with reason codes"],
    ["Record of what happened", "Action logs", "Chat logs", "Receipts + DataHub write-back + handoff"],
  ];
  const buildCompare = () => {
    let el = root.querySelector("[data-compare]");
    if (!el) { el = h("section", { class: "compare-view", "data-compare": "" }); root.append(el); }
    const tbody = h("tbody");
    for (const [dim, af, agent, us] of CMP_ROWS) {
      tbody.append(h("tr", {},
        h("th", { scope: "row", text: dim }),
        h("td", { text: af }),
        h("td", { text: agent }),
        h("td", { class: "us", text: us })));
    }
    const table = h("table", { class: "cmp-table cmp3" },
      h("thead", {}, h("tr", {},
        h("th", { text: "" }),
        h("th", { text: "DataHub Actions Framework" }),
        h("th", { text: "Generic LLM agent" }),
        h("th", { class: "us", text: "LedgerLens" }))),
      tbody);
    el.replaceChildren(
      h("p", { class: "proofs-eyebrow", text: "THE MIDDLE PATH — NOT ACTIONS FRAMEWORK, NOT A LOOSE AGENT" }),
      h("h2", { class: "proofs-title", text: "How LedgerLens compares" }),
      h("p", { class: "cmp-note" }, "DataHub already ", h("b", { text: "detects" }), " these incidents (assertions), ",
        h("b", { text: "holds the context" }), " LedgerLens reads (lineage, owner, tier), and can ",
        h("b", { text: "fire pre-wired automations" }), " (its Actions Framework). LedgerLens adds the missing middle: an AI plans a bounded response, and deterministic policy — not the model — authorizes the exact reviewed plan."),
      table);
  };

  // ---- "How it works" — real code that engineers the data flow -------------
  const CODE = [
    {
      title: "The data flow, engineered as one graph",
      file: "src/ledgerlens/orchestrator.py · IncidentOrchestrator.run",
      code: [
        "# trigger → context → plan → verify → authorize → execute → writeback",
        "context = IncidentContext.model_validate(self.context_provider(incident))   # DataHub read",
        "plan = ActionPlan.model_validate(self.planner.plan(context))                # AI proposes",
        "verification = self.verifier_panel.verify(context, plan)                    # AI reviews",
        "authorization = self.policy_gate.authorize(context, plan, verification)     # deterministic gate",
        "if not authorization.authorized:",
        "    return self._blocked(...)          # fail closed — nothing runs",
        "for action in plan.actions:",
        "    receipts.append(self._execute_action(..., action=action))              # allowlisted fanout",
        "writeback_outcome = self.writeback(snapshot)                               # DataHub write-back",
      ],
    },
    {
      title: "Read the DataHub lineage graph over MCP",
      file: "src/ledgerlens/datahub_context.py · DataHubMCPContextProvider",
      code: [
        "entities = self.client.get_entities([root_urn])           # MCP: read the entity",
        "lineage  = self.client.get_lineage(root_urn, direction=\"downstream\",",
        "                                   max_hops=self.max_hops, count=self.max_results)",
        "downstream_urns = tuple(dict.fromkeys(",
        "    str(item[\"urn\"]) for item in lineage if item[\"urn\"] != root_urn))",
        "facts = (",
        "    _fact(\"root-asset\",    f\"The triggering DataHub entity is {root_urn}.\", root_urn),",
        "    _fact(\"primary-owner\", f\"The recorded owner is {owner}.\", f\"{root_urn}#ownership\"),",
        "    _fact(\"blast-radius\",  f\"{len(downstream_urns)} downstream entities.\", ...),",
        ")",
      ],
    },
    {
      title: "The deterministic gate on the flow",
      file: "src/ledgerlens/verification.py · PolicyGate.authorize",
      code: [
        "for action in plan.actions:",
        "    allowance = self._allowances.get(action.action_type)",
        "    if allowance is None:",
        "        reasons.append(f\"action_not_allowlisted:{action.action_id}\")",
        "    if action.target not in allowance.targets:",
        "        reasons.append(f\"target_not_allowlisted:{action.action_id}\")    # off-graph target",
        "    if not frozenset(action.evidence_fact_ids) <= context.fact_ids:",
        "        reasons.append(f\"action_references_unknown_fact:{...}\")          # ungrounded action",
        "authorized = not reasons     # any failed check blocks the whole plan",
      ],
    },
  ];
  const buildCode = () => {
    let el = root.querySelector("[data-code]");
    if (!el) { el = h("section", { class: "code-view", "data-code": "" }); root.append(el); }
    const grid = h("div", { class: "code-grid" });
    for (const c of CODE) {
      grid.append(h("article", { class: "code-card" },
        h("div", { class: "code-hd" }, h("h3", { text: c.title }), h("code", { class: "code-file", text: c.file })),
        h("pre", { class: "code-block", text: c.code.join("\n") })));
    }
    el.replaceChildren(
      h("p", { class: "proofs-eyebrow", text: "GRAPH-ENGINEERING THE FLOW OF DATA" }),
      h("h2", { class: "proofs-title", text: "How the flow is built — real repo code (condensed)" }),
      grid);
  };

  // ---- differentiator proofs (real gate rejections) ------------------------
  const short = (fp) => (fp ? String(fp).slice(0, 8) + "…" : "—");

  const gateCard = (d) =>
    h("article", { class: "proof" },
      h("div", { class: "proof-head" },
        h("span", { class: "proof-icon", text: "⛨" }),
        h("h3", { text: "Plan-exact authorization" }),
        h("span", { class: "proof-tag", text: "the differentiator" })),
      h("p", { class: "proof-sub", text: "Same DataHub context — the executed plan differs from the reviewed plan by one appended action." }),
      h("div", { class: "proof-fps" },
        h("div", { class: "fp ok" }, h("small", { text: "REVIEWED PLAN" }), h("code", { text: short(d.reviewedPlanFingerprint) }), h("span", { class: "fpv ok", text: "✓ authorized" })),
        h("div", { class: "proof-vs", text: "+1 action ⇒" }),
        h("div", { class: "fp bad" }, h("small", { text: "EXECUTED PLAN" }), h("code", { text: short(d.executedPlanFingerprint) }), h("span", { class: "fpv bad", text: "✕ DENIED" }))),
      h("p", { class: "proof-fail" }, h("b", { text: "Gate refused: " }), (d.denied?.failedConditions || []).join(" · ")),
      h("p", { class: "proof-point", text: d.point || "" }));

  const quorumCard = (d) => {
    const chips = h("div", { class: "proof-verifiers" });
    for (const v of (d.verifiers || [])) {
      chips.append(h("span", { class: "vchip " + (v.verdict === "pass" ? "ok" : "bad"), text: v.id + (v.verdict === "pass" ? " ✓" : " ✕ objected") }));
    }
    return h("article", { class: "proof" },
      h("div", { class: "proof-head" },
        h("span", { class: "proof-icon", text: "◈" }),
        h("h3", { text: "Independent verifier quorum" }),
        h("span", { class: "proof-tag", text: "2-of-2 required" })),
      h("p", { class: "proof-sub", text: "AI review is advisory. One of two independent verifiers objecting is enough to hold the gate." }),
      chips,
      h("p", { class: "proof-line" }, "Unanimous → ", h("b", { class: "ok", text: (d.unanimous?.decision || "") }),
        "   ·   Split → ", h("b", { class: "bad", text: (d.split?.decision || "").toUpperCase() }),
        " (" + (d.split?.failedConditions || []).join(", ") + ")"),
      h("p", { class: "proof-point", text: d.point || "" }));
  };

  const allowlistCard = (d) =>
    h("article", { class: "proof" },
      h("div", { class: "proof-head" },
        h("span", { class: "proof-icon", text: "⛔" }),
        h("h3", { text: "AI cannot widen the allowlist" }),
        h("span", { class: "proof-tag", text: "deterministic policy" })),
      h("p", { class: "proof-sub", text: "Same grounded action, same passing AI review — only the destination changed. The production PolicyGate that runs the real fanout refuses an off-allowlist target." }),
      h("div", { class: "proof-fps" },
        h("div", { class: "fp ok" }, h("small", { text: "ALLOWLISTED TARGET" }), h("code", { text: d.allowlistedTarget }), h("span", { class: "fpv ok", text: "✓ authorized" })),
        h("div", { class: "proof-vs", text: "change target ⇒" }),
        h("div", { class: "fp bad" }, h("small", { text: "OFF-ALLOWLIST TARGET" }), h("code", { text: d.offAllowlistTarget }), h("span", { class: "fpv bad", text: "✕ DENIED" }))),
      h("p", { class: "proof-fail" }, h("b", { text: "Gate refused: " }), (d.denied?.failedConditions || []).join(" · ")),
      h("p", { class: "proof-point", text: d.point || "" }));

  const comparisonCard = () =>
    h("article", { class: "proof compare" },
      h("div", { class: "proof-head" },
        h("span", { class: "proof-icon", text: "⧉" }),
        h("h3", { text: "Beyond DataHub's built-ins" }),
        h("span", { class: "proof-tag", text: "originality" })),
      h("div", { class: "cmp" },
        h("div", { class: "cmp-row" }, h("span", { class: "cmp-who", text: "DataHub Actions Framework" }), h("span", { class: "cmp-what", text: "rule → one fixed integration (e.g. open a PagerDuty incident)" })),
        h("div", { class: "cmp-row" }, h("span", { class: "cmp-who", text: "Generic LLM agent" }), h("span", { class: "cmp-what", text: "the model decides and acts — it authorizes itself" })),
        h("div", { class: "cmp-row us" }, h("span", { class: "cmp-who", text: "LedgerLens" }), h("span", { class: "cmp-what", text: "AI proposes + reviews → deterministic policy authorizes the exact plan → receipted actions + DataHub write-back" }))));

  const contributeBackCard = () =>
    h("article", { class: "proof compare" },
      h("div", { class: "proof-head" },
        h("span", { class: "proof-icon", text: "↥" }),
        h("h3", { text: "We contributed back to DataHub" }),
        h("span", { class: "proof-tag", text: "open-source · proposed" })),
      h("p", { class: "proof-sub", text: "Building this surfaced a real gap in the official DataHub MCP server — so we filed a fix upstream." }),
      h("div", { class: "cmp" },
        h("div", { class: "cmp-row" }, h("span", { class: "cmp-who", text: "The gap" }), h("span", { class: "cmp-what", text: "get_entities returns cleaned metadata but not per-aspect systemMetadata (lastObserved, runId) — an agent can't tell DataHub ingestion time from a business event without a second, non-MCP API call." })),
        h("div", { class: "cmp-row us" }, h("span", { class: "cmp-who", text: "Our proposal" }), h("span", { class: "cmp-what", text: "an opt-in provenance_aspects parameter that attaches a compact, allow-listed aspectProvenance object — default output unchanged." }))),
      h("p", { class: "proof-point" },
        h("a", { href: "https://github.com/acryldata/mcp-server-datahub/issues/159", target: "_blank", rel: "noopener", text: "Issue #159" }),
        " · ",
        h("a", { href: "https://github.com/acryldata/mcp-server-datahub/pull/160", target: "_blank", rel: "noopener", text: "PR #160" }),
        " — open, not merged."));

  const buildProofs = async () => {
    const el = document.querySelector("[data-proofs]");
    if (!el) return;
    el.replaceChildren(
      h("p", { class: "proofs-eyebrow", text: "DIFFERENT — AND EVERY CLAIM IS CHECKABLE" }),
      h("h2", { class: "proofs-title", text: "What makes this different from the other DataHub agents" }),
      comparisonCard());
    try {
      const [g, q, a] = await Promise.all([
        fetch(`${apiBase}/gate-demo`, { credentials: "same-origin" }).then((r) => r.json()),
        fetch(`${apiBase}/quorum-demo`, { credentials: "same-origin" }).then((r) => r.json()),
        fetch(`${apiBase}/allowlist-demo`, { credentials: "same-origin" }).then((r) => r.json()),
      ]);
      if (g && g.demo) el.append(gateCard(g.demo));
      if (q && q.demo) el.append(quorumCard(q.demo));
      if (a && a.demo) el.append(allowlistCard(a.demo));
    } catch (error) { /* leave the heading; proofs are best-effort */ }
    el.append(contributeBackCard());
  };

  const start = async () => {
    if (replayBtn) replayBtn.disabled = true;
    body.classList.add("js");
    logEl.replaceChildren(h("div", { class: "logloading" }, h("span", { class: "sv-spinner", "aria-hidden": "true" }), GATE));
    try {
      const res = await fetch(`${apiBase}/trigger`, {
        method: "POST", credentials: "same-origin",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify({ replay: true }),
      });
      const data = await res.json();
      if (!res.ok || !data.ok || !data.state) throw new Error(data.detail || "Trigger failed.");
      backend = data.state;
      try {
        const lr = await fetch(`${apiBase}/live-receipts`, { credentials: "same-origin" }).then((r) => r.json());
        if (lr && lr.receipts && typeof lr.receipts === "object") liveReceipts = lr.receipts;
      } catch (error) { /* real receipts are best-effort; fall back to simulated */ }
      buildTimeline(); paintTimeline(); buildPipe(); buildControls(); buildStory(); buildProofs();
      resetFlow();
    } catch (error) {
      body.classList.remove("js");
      logEl.replaceChildren();
    } finally {
      if (replayBtn) replayBtn.disabled = false;
    }
  };

  replayBtn?.addEventListener("click", resetFlow);
  document.addEventListener("keydown", (e) => {
    if (mode !== "walk") return;
    if (e.key === "ArrowRight" || e.key === "ArrowDown") { stopRun(); setActive(Math.min(active + 1, NODES.length - 1)); }
    else if (e.key === "ArrowLeft" || e.key === "ArrowUp") { stopRun(); setActive(Math.max(active - 1, 0)); }
  });

  start();
})();
