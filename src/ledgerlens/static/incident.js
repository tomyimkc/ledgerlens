(() => {
  "use strict";

  // Clean, static product page (no playback controls): hero → how it works (pipeline)
  // → how each of six incidents is handled vs the alternatives → a live gate proof →
  // the real code → easy adoption. The server-rendered `.legacy-content` stays as the
  // no-JS fallback. "Evaluating deterministic gate" shows briefly while the proof loads.

  const body = document.body;
  const apiBase = body.dataset.apiBase;
  const root = document.querySelector("[data-flow-root]");
  const pipeEl = document.querySelector("[data-pipe]");
  const detailEl = document.querySelector("[data-detail]");
  const proofsEl = document.querySelector("[data-proofs]");
  const timelineEl = document.querySelector("[data-timeline]");
  const hintEl = document.querySelector("[data-scrollhint]");
  const replayBtn = document.querySelector("[data-flow-replay]");
  const GATE = "Evaluating deterministic gate…";

  if (!root || !pipeEl || !detailEl) return; // keep the server fallback

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

  const EVIDENCE = "https://github.com/tomyimkc/ledgerlens/blob/main/docs/EVIDENCE_INDEX.md";

  // ---- how it works: a static pipeline diagram -----------------------------
  const NODES = [
    ["◎", "Trigger", "DataHub assertion fires"],
    ["◇", "DataHub context", "get_entities + lineage"],
    ["▤", "Plan", "AI proposes bounded actions"],
    ["◈", "Verify", "AI review — advisory only"],
    ["⛨", "Policy gate", "deterministic authorization"],
    ["⇶", "Act", "GitHub · Slack · PagerDuty · Jira"],
    ["⤴", "Write-back", "receipt to DataHub"],
    ["⇉", "Handoff", "next agent inherits facts"],
  ];
  const buildPipe = () => {
    const pipe = h("div", { class: "pipe" });
    NODES.forEach(([icon, label, sub], i) => {
      pipe.append(h("div", { class: "pnode done" },
        h("span", { class: "pnode-icon", text: icon }),
        h("span", { class: "pnode-label", text: label }),
        h("small", { class: "pnode-sub", text: sub })));
      if (i < NODES.length - 1) pipe.append(h("span", { class: "parrow filled" }, h("span", { class: "packet", "aria-hidden": "true" })));
    });
    return h("section", { class: "sec" },
      h("p", { class: "sec-eyebrow", text: "HOW IT WORKS" }),
      h("h2", { class: "sec-title", text: "One pipeline, any incident" }),
      h("div", { class: "pipe-wrap" }, pipe));
  };

  // ---- what is LedgerLens? -------------------------------------------------
  const buildWhat = () => {
    const box = (t, s, cls) => h("div", { class: "sysbox" + (cls ? " " + cls : "") }, h("strong", { text: t }), h("small", { text: s }));
    const arrow = (label, sub) => h("div", { class: "sysarrow" },
      h("span", { class: "sysarrow-l", text: label }), sub ? h("small", { text: sub }) : null,
      h("span", { class: "sysarrow-h", "aria-hidden": "true", text: "→" }));
    return h("section", { class: "sec" },
      h("p", { class: "sec-eyebrow", text: "WHAT IS IT" }),
      h("h2", { class: "sec-title", text: "LedgerLens is a deployable incident-response agent" }),
      h("p", { class: "sec-note" }, "Not a dashboard, and not a DataHub plugin. It is a service you run next to DataHub: it ",
        h("b", { text: "calls the official DataHub MCP server as a client" }), " to read context (get_entities, get_lineage), turns the incident into a bounded LLM-planned response, gates it, acts across your tools, and writes an incident receipt back (save_document)."),
      h("div", { class: "sysmap" },
        box("Your DataHub", "owners · lineage · assertions"),
        arrow("get_entities / get_lineage", "MCP read"),
        box("LedgerLens agent", "plan → verify → gate → act", "us"),
        arrow("allowlisted · receipted", "your tools"),
        box("Your incident tools", "GitHub · Slack · PagerDuty · Jira")),
      h("p", { class: "syswrite" }, "↩ save_document (MCP write-back) — the incident receipt returns to DataHub for the next agent."));
  };

  // ---- master table: six incidents × three approaches, with the risk inline --
  const COMPARISON = [
    { s: "Freshness SLO breach", d: "payments_daily is 23m stale (15m SLO)",
      af: "Fires one pre-wired rule — a Slack ping, if you configured it.",
      ag: "Improvises a response and self-approves it;", agRisk: "may page, post, or 'fix' with no human review.",
      us: "Pages the recorded owner, posts the blast radius, opens a tracked issue.", usGate: "only the reviewed, allowlisted plan runs — with receipts." },
    { s: "Schema drift", d: "order_total INT → DECIMAL (breaking)",
      af: "Notifies only if a schema-change rule exists; can't tell which models break.",
      ag: "May auto-migrate the column", agRisk: "→ rewrites production order_total, silently rounding money on every order.",
      us: "Flags the two downstream models, files a change record.", usGate: "a data-mutation is off-allowlist → refused." },
    { s: "Volume anomaly", d: "clickstream rows −62% vs baseline",
      af: "Sends a notification if a volume rule fired; no downstream awareness.",
      ag: "May rerun jobs or edit data to 'fix' it", agRisk: "→ can double-write or corrupt, unbounded.",
      us: "Records the drop, notifies Growth, warns downstream metrics + ML.", usGate: "nothing is fixed automatically; receipts kept." },
    { s: "Access / ACL change on PII", d: "customers ACL widened to all-employees",
      af: "Can notify on a policy-change event, if wired.",
      ag: "Might revert the ACL itself", agRisk: "→ grants or strips access with no review — a security & privacy incident.",
      us: "Raises a SEV-1, pages Trust & Safety, files an access review.", usGate: "ACL edits are off-allowlist by design → refused." },
    { s: "Upstream deploy break", d: "a dbt deploy removed a revenue filter",
      af: "Not triggered by a dbt deploy unless wired into CI — no incident opens.",
      ag: "Improvises a rollback or data edit and self-approves it", agRisk: "→ an unreviewed change hits production.",
      us: "Links the incident to the exact deploy commit, pages Finance, opens a rollback ticket.", usGate: "the fix stays with the engineer; full receipt trail." },
    { s: "Ingestion failure", d: "billing connector auth expired; feed stale",
      af: "Notifies if an ingestion-failure rule exists.",
      ag: "May retry or 'repair' the connector", agRisk: "→ unbounded retries against a flaky source.",
      us: "Records the failed run, notifies Vendor Ops, flags the AR ledger as stale.", usGate: "no closing the books on data that never arrived." },
  ];

  const buildComparison = () => {
    const tbody = h("tbody");
    for (const r of COMPARISON) {
      tbody.append(h("tr", {},
        h("th", { scope: "row" }, h("strong", { text: r.s }), h("small", { text: r.d })),
        h("td", { text: r.af }),
        h("td", { class: "ag" }, r.ag + " ", r.agRisk ? h("span", { class: "risk", text: r.agRisk }) : null),
        h("td", { class: "us" }, r.us + " ", r.usGate ? h("span", { class: "gate", text: r.usGate }) : null)));
    }
    return h("section", { class: "sec" },
      h("p", { class: "sec-eyebrow", text: "SIX INCIDENTS · THREE APPROACHES · THE RISK, INLINE" }),
      h("h2", { class: "sec-title", text: "How each real incident is handled — and what a loose agent risks" }),
      h("p", { class: "sec-note" }, "DataHub already ", h("b", { text: "detects" }), " these (assertions) and can ",
        h("b", { text: "fire pre-wired automations" }), " (its Actions Framework). The difference is what happens next — a self-authorizing agent decides for itself that its action is safe (the ",
        h("span", { class: "risk", text: "red" }), " is what can go wrong); LedgerLens lets deterministic policy authorize the exact plan."),
      h("div", { class: "cmp-wrap" }, h("table", { class: "cmp-table cmp3 cmp6" },
        h("thead", {}, h("tr", {},
          h("th", { text: "Incident" }),
          h("th", { text: "DataHub Actions Framework" }),
          h("th", { text: "Generic LLM agent (self-authorizing)" }),
          h("th", { class: "us", text: "LedgerLens (policy-authorized)" }))),
        tbody)),
      h("p", { class: "sec-foot" },
        "Across all of these a self-authorizing agent can also ", h("span", { class: "risk", text: "run a plan that drifted after review" }),
        ", or hit a ", h("span", { class: "risk", text: "hallucinated / prompt-injected target" }),
        ". LedgerLens binds authorization to the exact plan fingerprint and executes only allowlisted targets — both are refused."),
      h("p", { class: "sec-foot", "data-realrun": "" },
        "And the LedgerLens column isn't hypothetical — the whole pipeline was executed for real once: GitHub ",
        h("a", { href: "https://github.com/tomyimkc/ledgerlens/issues/29", target: "_blank", rel: "noopener", text: "#29" }),
        " · Slack · PagerDuty · Jira KAN-2 — ",
        h("a", { href: EVIDENCE, target: "_blank", rel: "noopener", text: "evidence (E-16)" }),
        ". One bounded rehearsal action each; a receipt is not proof of recovery."));
  };

  // ---- easy to adopt -------------------------------------------------------
  const buildAdoption = () => {
    const feats = [
      ["Reads your catalog", "Uses the same official DataHub MCP surface — get_entities + get_lineage. No new pipeline to stand up."],
      ["Stays in your allowlist", "Define the actions and targets once; LedgerLens only ever plans within them."],
      ["Writes receipts back", "Records an incident-command receipt to DataHub (save_document) and hands off to the next agent."],
      ["Policy authorizes, not the model", "A deterministic gate approves the exact reviewed plan; the AI can propose, never approve."],
    ];
    const grid = h("div", { class: "adopt-grid" });
    for (const [t, d] of feats) grid.append(h("article", { class: "adopt-card" }, h("h3", { text: t }), h("p", { text: d })));
    return h("section", { class: "sec" },
      h("p", { class: "sec-eyebrow", text: "ALREADY ON DATAHUB? IT DROPS IN" }),
      h("h2", { class: "sec-title", text: "Easy to adopt into your existing workflow" }),
      grid);
  };

  // ---- see it run: a terminal streaming the real flow (fixture replay) ------
  const TERMINAL = [
    { cmd: "uv run ledgerlens incident --replay freshness_breach" },
    { tag: "incident_dashboard", msg: "trigger    freshness assertion FAILED (observed 23m > 15m SLO)" },
    { tag: "mcp_client", msg: "context    get_entities + get_lineage …", ok: "owner=data-platform tier=1 · 3 downstream" },
    { tag: "agent", msg: "plan       4 bounded, reversible actions proposed", ok: "fingerprint=20f3ace2" },
    { tag: "VerifierPanel", msg: "verify     verifier-A ✓  verifier-B ✓  quorum 2/2", ok: "approved (advisory)" },
    { tag: "PolicyGate", msg: "authorize  exact-plan hash match · allowlist · grounding", ok: "AUTHORIZED" },
    { tag: "action_adapters", msg: "act        github.issue.create", ok: "fixture://github/issues/481" },
    { tag: "action_adapters", msg: "act        slack.message.post", ok: "fixture://slack/messages/1712.4401" },
    { tag: "action_adapters", msg: "act        pagerduty.event.trigger", ok: "fixture://pagerduty/incidents/778" },
    { tag: "action_adapters", msg: "act        jira.issue.create", ok: "fixture://jira/issues/DATAOPS-219" },
    { tag: "mcp_mutations", msg: "writeback  save_document → DataHub", ok: "recorded" },
    { tag: "memory", msg: "handoff    next agent inherits facts + unknowns", ok: "ready" },
    { done: "✓ done · cause, user impact, and recovery remain unknown · fixture replay" },
  ];
  const termLine = (l) => {
    if (l.cmd) return h("div", { class: "term-line cmd" }, h("span", { class: "term-prompt", text: "$ " }), l.cmd);
    if (l.done) return h("div", { class: "term-line term-done", text: l.done });
    const row = h("div", { class: "term-line" }, h("span", { class: "term-tag", text: "[" + l.tag + "] " }), l.msg);
    if (l.ok) row.append(h("span", { class: "term-ok", text: "  " + l.ok }));
    return row;
  };
  const buildCode = () => {
    const bodyT = h("div", { class: "term-body" });
    const term = h("div", { class: "terminal" },
      h("div", { class: "term-bar" },
        h("span", { class: "tdot r" }), h("span", { class: "tdot y" }), h("span", { class: "tdot g" }),
        h("span", { class: "term-title", text: "orchestrator.py — LedgerLens · fixture replay" })),
      bodyT);
    const reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let started = false;
    const stream = () => {
      if (started) return;
      started = true;
      if (reduce) { for (const l of TERMINAL) bodyT.append(termLine(l)); return; }
      let i = 0;
      const step = () => {
        if (i >= TERMINAL.length) { bodyT.append(h("span", { class: "term-cursor", "aria-hidden": "true" })); return; }
        const line = termLine(TERMINAL[i]); line.classList.add("term-in"); bodyT.append(line); i += 1;
        setTimeout(step, 270);
      };
      step();
    };
    if (typeof IntersectionObserver === "function") {
      const io = new IntersectionObserver((entries) => {
        for (const e of entries) if (e.isIntersecting) { io.disconnect(); stream(); }
      }, { threshold: 0.25 });
      io.observe(term);
    } else { stream(); }
    return h("section", { class: "sec" },
      h("p", { class: "sec-eyebrow", text: "SEE IT RUN" }),
      h("h2", { class: "sec-title", text: "The pipeline, running — a live terminal" }),
      h("p", { class: "sec-note" }, "The real orchestrator (",
        h("a", { href: "https://github.com/tomyimkc/ledgerlens/blob/main/src/ledgerlens/orchestrator.py", target: "_blank", rel: "noopener", text: "orchestrator.py" }),
        ") running the fixture incident — the same code path a live run takes. Every receipt here is fixture://."),
      term);
  };

  // ---- live gate proof -----------------------------------------------------
  const short = (fp) => (fp ? String(fp).slice(0, 8) + "…" : "—");
  const list = (v) => (Array.isArray(v) ? v : []);
  const mark = (status) => h("span", { class: "gc-col " + (status === "pass" ? "ok" : "bad"), text: status === "pass" ? "✓" : "✕" });

  const gateChecks = (d) => {
    const rev = list(d.approved && d.approved.conditions);
    const exe = list(d.denied && d.denied.conditions);
    const wrap = h("div", { class: "gate-checks" });
    wrap.append(h("div", { class: "gate-check hd" },
      h("span", { class: "gc-name", text: "Deterministic check" }),
      h("span", { class: "gc-col", text: "Reviewed" }),
      h("span", { class: "gc-col", text: "Executed" })));
    for (let i = 0; i < exe.length; i += 1) {
      const c = exe[i];
      const r = rev[i] || {};
      const flipped = c.status === "fail";
      wrap.append(h("div", { class: "gate-check" + (flipped ? " flip" : "") },
        h("span", { class: "gc-name" }, h("strong", { text: c.name }), flipped && c.detail ? h("small", { text: c.detail }) : null),
        mark(r.status),
        mark(c.status)));
    }
    return wrap;
  };

  const gateCard = (d) => {
    const fails = list(d.denied && d.denied.failedConditions);
    return h("article", { class: "proof gate-detail" },
      h("div", { class: "proof-head" },
        h("span", { class: "proof-icon", text: "⛨" }),
        h("h3", { text: "Plan-exact authorization" }),
        h("span", { class: "proof-tag", text: "the differentiator" })),
      h("p", { class: "proof-sub", text: "The reviewed plan was authorized. Then one Slack action was appended after review — same DataHub context, different plan. Here is exactly what the deterministic gate checks, and what flips." }),
      h("div", { class: "proof-fps" },
        h("div", { class: "fp ok" }, h("small", { text: "REVIEWED PLAN" }), h("code", { text: short(d.reviewedPlanFingerprint) }), h("span", { class: "fpv ok", text: "✓ authorized" })),
        h("div", { class: "proof-vs", text: "+1 action ⇒" }),
        h("div", { class: "fp bad" }, h("small", { text: "EXECUTED PLAN" }), h("code", { text: short(d.executedPlanFingerprint) }), h("span", { class: "fpv bad", text: "✕ DENIED" }))),
      gateChecks(d),
      h("p", { class: "gate-why" }, h("b", { class: "ok", text: "Why authorized — " }),
        "the reviewed plan passed every check: grounded DataHub context, bounded blast radius, allowlisted + reversible actions, complete verifier checks, and an exact fingerprint + confirmation match."),
      h("p", { class: "gate-why" }, h("b", { class: "bad", text: "Why denied — " }),
        "appending one action changed the plan's computed fingerprint, so " + fails.length + " fingerprint-bound checks fail closed: ",
        h("span", { class: "risk", text: fails.join(" · ") }),
        ". The hash and confirmation phrase the operator supplied for the reviewed plan no longer match the executed plan."),
      h("p", { class: "proof-point" }, h("b", { text: "AI review is advisory — it cannot open this gate. " }), d.point || ""));
  };

  const buildProofSection = async () => {
    try {
      const g = await fetch(`${apiBase}/gate-demo`, { credentials: "same-origin" }).then((r) => r.json());
      if (g && g.demo) return h("section", { class: "sec" },
        h("p", { class: "sec-eyebrow", text: "PROVEN, NOT CLAIMED" }),
        h("h2", { class: "sec-title", text: "The real gate refuses a plan that drifted after review" }),
        gateCard(g.demo));
    } catch (error) { /* best-effort */ }
    return null;
  };

  // ---- get started: a simple setup guide -----------------------------------
  const SETUP = [
    { n: "1", t: "Try it offline — no credentials",
      code: [
        "git clone https://github.com/tomyimkc/ledgerlens.git",
        "cd ledgerlens",
        "make setup          # provision the toolchain with uv",
        "make incident-demo  # opens http://127.0.0.1:8000/incident",
      ],
      note: "A labelled deterministic replay: no DataHub call, no provider API, no paid model — every receipt is fixture://." },
    { n: "2", t: "Point it at your DataHub + tools (live)",
      code: [
        "# read your catalog over the official DataHub MCP",
        "export DATAHUB_GMS_URL=https://your-datahub  DATAHUB_TOKEN=…",
        "# scoped credentials for the tools you allow",
        "export GITHUB_TOKEN=…  LEDGERLENS_SLACK_WEBHOOK_URL=…",
        "export LEDGERLENS_PAGERDUTY_ROUTING_KEY=…  LEDGERLENS_JIRA_SITE_URL=…",
        "# bring your own LLM — any OpenAI-compatible endpoint",
        "export LEDGERLENS_LLM_API_KEY=…   LEDGERLENS_LLM_BASE_URL=…   LEDGERLENS_LLM_MODEL=…",
        "make run-all-incidents-live   # fires real, allowlisted actions",
      ],
      note: "You define the action allowlist once; LedgerLens only ever plans within it. Full env + allowlist setup is in the README." },
  ];
  const buildSetup = () => {
    const grid = h("div", { class: "setup-grid" });
    for (const s of SETUP) {
      grid.append(h("article", { class: "setup-card" },
        h("div", { class: "setup-hd" }, h("span", { class: "setup-n", text: s.n }), h("h3", { text: s.t })),
        h("pre", { class: "code-block setup-code", text: s.code.join("\n") }),
        h("p", { class: "setup-note", text: s.note })));
    }
    return h("section", { class: "sec" },
      h("p", { class: "sec-eyebrow", text: "GET STARTED" }),
      h("h2", { class: "sec-title", text: "Set up LedgerLens in a few commands" }),
      grid,
      h("p", { class: "sec-foot" }, "Full guide → ",
        h("a", { href: "https://github.com/tomyimkc/ledgerlens#readme", target: "_blank", rel: "noopener", text: "README" })));
  };

  // ---- assemble the page ---------------------------------------------------
  const decorateHero = () => {
    replayBtn?.remove(); // no playback controls
    const heroCopy = root.querySelector(".flow-hero > div");
    if (heroCopy && !heroCopy.querySelector(".hero-sub")) {
      heroCopy.append(h("p", { class: "hero-sub", text:
        "LedgerLens is a deployable incident-response agent for teams already on DataHub. It reads your catalog over MCP, plans a bounded response, and lets deterministic policy — not the model — authorize the exact plan before anything runs." }));
    }
  };

  const start = async () => {
    body.classList.add("js");
    decorateHero();
    timelineEl?.replaceChildren();
    hintEl?.replaceChildren();
    pipeEl.closest(".pipe-sticky")?.remove(); // the pipeline now lives inside the sections
    proofsEl?.remove();
    detailEl.replaceChildren(h("div", { class: "logloading" }, h("span", { class: "sv-spinner", "aria-hidden": "true" }), GATE));
    const proof = await buildProofSection();
    detailEl.replaceChildren(
      buildWhat(), buildPipe(), buildComparison(), buildCode(),
      ...(proof ? [proof] : []), buildAdoption(), buildSetup());
  };

  start();
})();
