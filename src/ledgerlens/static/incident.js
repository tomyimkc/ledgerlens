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

  // ---- the danger a self-authorizing agent creates -------------------------
  const DANGERS = [
    ["Auto-migrates the schema", "rewrites production order_total — every order silently rounds money.", "a data-mutation action isn't on the allowlist → refused. It files a change record instead."],
    ["Reverts the PII ACL itself", "grants or strips access with no review — a security and privacy incident.", "ACL edits are off-allowlist by design → refused. It files an access review instead."],
    ["Runs a plan that drifted after review", "a human approved plan A; the model executes plan B, so an unreviewed action runs.", "authorization is bound to the exact plan fingerprint → refused."],
    ["Pages the wrong service / posts to #all-company", "hallucinated or injected targets create noise, false alarms, or a leak.", "only allowlisted targets execute → refused."],
  ];
  const buildDanger = () => {
    const grid = h("div", { class: "danger-grid" });
    for (const [act, consequence, refuse] of DANGERS) {
      grid.append(h("article", { class: "danger-card" },
        h("div", { class: "danger-act" }, h("span", { class: "danger-tag", text: "SELF-AUTHORIZING AGENT" }), h("strong", { text: "“" + act + "”" })),
        h("p", { class: "danger-conseq" }, h("span", { class: "danger-arrow", text: "→ " }), consequence),
        h("p", { class: "danger-fix" }, h("b", { text: "LedgerLens: " }), refuse)));
    }
    return h("section", { class: "sec" },
      h("p", { class: "sec-eyebrow danger-eyebrow", text: "THE RISK — WHY THE GATE MATTERS" }),
      h("h2", { class: "sec-title", text: "What a self-authorizing agent can do to an incident" }),
      h("p", { class: "sec-note" }, "A generic LLM agent decides for itself whether its own response is safe — so a bad plan, a hallucinated target, or a prompt-injected incident payload can run unchecked. Each of these is exactly what the deterministic gate stops."),
      grid);
  };

  // ---- six incidents, three approaches -------------------------------------
  const COMPARISON = [
    { s: "Freshness SLO breach", d: "payments_daily is 23m stale (15m SLO)",
      af: "Fires one pre-wired rule — a Slack ping, if you configured it for this assertion.",
      ag: "Improvises a response and runs it; decides for itself that it is safe.",
      us: "Reads owner + lineage, pages the on-call owner, posts the blast radius, opens a tracked issue — only the reviewed, allowlisted plan runs, with receipts." },
    { s: "Schema drift", d: "order_total INT → DECIMAL (breaking)",
      af: "Notifies only if a schema-change rule exists; it doesn't reason about which models break.",
      ag: "May flag downstream — or 'auto-migrate' the column. Unbounded, self-approved.",
      us: "Grounds on lineage, files a schema-change record, flags the two downstream models; a risky auto-migrate is off-allowlist → refused." },
    { s: "Volume anomaly", d: "clickstream rows −62% vs baseline",
      af: "Sends a notification if a volume rule fired; no downstream awareness.",
      ag: "Improvises — may rerun jobs or edit data to 'fix' it.",
      us: "Records the drop, notifies the Growth owner, warns downstream metrics + ML training — nothing is fixed automatically; receipts kept." },
    { s: "Access / ACL change on PII", d: "customers ACL widened to all-employees",
      af: "Can notify on a policy-change event, if wired.",
      ag: "Might try to revert the ACL itself — dangerous and self-authorized.",
      us: "Raises a SEV-1, pages Trust & Safety, files an access-review ticket. Editing the ACL is out of its allowlist by design — refused." },
    { s: "Upstream deploy break", d: "a dbt deploy removed a revenue filter",
      af: "Not triggered by a dbt deploy unless wired into CI — no incident is opened.",
      ag: "Improvises a rollback or data edit; approves its own change.",
      us: "Links the incident to the exact deploy commit, pages Finance, opens a rollback ticket — the fix stays with the engineer, full receipt trail." },
    { s: "Ingestion failure", d: "billing connector auth expired; feed stale",
      af: "Notifies if an ingestion-failure rule exists.",
      ag: "May retry or 'repair' the connector, unbounded.",
      us: "Records the failed run, notifies Vendor Ops, flags the AR ledger as running on stale data — no closing the books on data that never arrived." },
  ];

  const buildComparison = () => {
    const tbody = h("tbody");
    for (const r of COMPARISON) {
      tbody.append(h("tr", {},
        h("th", { scope: "row" }, h("strong", { text: r.s }), h("small", { text: r.d })),
        h("td", { text: r.af }),
        h("td", { text: r.ag }),
        h("td", { class: "us", text: r.us })));
    }
    return h("section", { class: "sec" },
      h("p", { class: "sec-eyebrow", text: "SIX INCIDENTS · THREE APPROACHES" }),
      h("h2", { class: "sec-title", text: "How each real incident is handled" }),
      h("p", { class: "sec-note" }, "DataHub already ", h("b", { text: "detects" }), " these (assertions) and can ",
        h("b", { text: "fire pre-wired automations" }), " (its Actions Framework). The difference is what happens next — and who is allowed to authorize it."),
      h("div", { class: "cmp-wrap" }, h("table", { class: "cmp-table cmp3 cmp6" },
        h("thead", {}, h("tr", {},
          h("th", { text: "Incident" }),
          h("th", { text: "DataHub Actions Framework" }),
          h("th", { text: "Generic LLM agent" }),
          h("th", { class: "us", text: "LedgerLens" }))),
        tbody)),
      h("p", { class: "sec-foot", "data-realrun": "" },
        "The LedgerLens column isn't hypothetical — the whole pipeline was executed for real once: GitHub ",
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

  // ---- real code that engineers the flow -----------------------------------
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
    const grid = h("div", { class: "code-grid" });
    for (const c of CODE) {
      grid.append(h("article", { class: "code-card" },
        h("div", { class: "code-hd" }, h("h3", { text: c.title }), h("code", { class: "code-file", text: c.file })),
        h("pre", { class: "code-block", text: c.code.join("\n") })));
    }
    return h("section", { class: "sec" },
      h("p", { class: "sec-eyebrow", text: "GRAPH-ENGINEERING THE FLOW OF DATA" }),
      h("h2", { class: "sec-title", text: "How the flow is built — real repo code (condensed)" }),
      grid);
  };

  // ---- live gate proof -----------------------------------------------------
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

  const buildProof = async () => {
    if (!proofsEl) return;
    try {
      const g = await fetch(`${apiBase}/gate-demo`, { credentials: "same-origin" }).then((r) => r.json());
      if (g && g.demo) proofsEl.replaceChildren(
        h("p", { class: "sec-eyebrow", text: "PROVEN, NOT CLAIMED" }),
        h("h2", { class: "sec-title", text: "The real gate refuses a plan that drifted after review" }),
        gateCard(g.demo));
    } catch (error) { /* best-effort; the section simply stays empty */ }
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
    detailEl.replaceChildren(h("div", { class: "logloading" }, h("span", { class: "sv-spinner", "aria-hidden": "true" }), GATE));
    detailEl.replaceChildren(buildWhat(), buildPipe(), buildComparison(), buildDanger(), buildCode(), buildAdoption());
    buildProof();
  };

  start();
})();
