(() => {
  "use strict";

  // Product page for judges and operators:
  //   1) what it is (DataHub client, not a plugin)
  //   2) how THIS REPO works — file-linked steps
  //   3) real MCP I/O (get_entities → save_document)
  //   4) see it run (fixture terminal)
  //   5) plan-exact gate proof (live /api/gate-demo)
  //   6) why not a chatbot / comparison
  //   7) get started
  // Server-rendered `.legacy-content` remains the no-JS fallback.

  const body = document.body;
  const apiBase = body.dataset.apiBase;
  const root = document.querySelector("[data-flow-root]");
  const pipeEl = document.querySelector("[data-pipe]");
  const detailEl = document.querySelector("[data-detail]");
  const proofsEl = document.querySelector("[data-proofs]");
  const timelineEl = document.querySelector("[data-timeline]");
  const hintEl = document.querySelector("[data-scrollhint]");
  const replayBtn = document.querySelector("[data-flow-replay]");
  const GATE = "Loading live gate proof…";

  if (!root || !pipeEl || !detailEl) return;

  const h = (tag, attrs, ...kids) => {
    const node = document.createElement(tag);
    if (attrs) for (const [k, v] of Object.entries(attrs)) {
      if (v == null) continue;
      if (k === "class") node.className = v;
      else if (k === "text") node.textContent = v;
      else if (k === "html") node.innerHTML = v;
      else node.setAttribute(k, v);
    }
    for (const kid of kids) if (kid != null) node.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
    return node;
  };

  const REPO = "https://github.com/tomyimkc/ledgerlens";
  const BLOB = REPO + "/blob/main/";
  const EVIDENCE = BLOB + "docs/EVIDENCE_INDEX.md";
  const fileLink = (path, label) =>
    h("a", {
      class: "file-link",
      href: BLOB + path,
      target: "_blank",
      rel: "noopener",
      text: label || path,
    });

  // ---- 1. What is it -------------------------------------------------------
  const buildWhat = () => {
    const box = (t, s, cls) =>
      h("div", { class: "sysbox" + (cls ? " " + cls : "") }, h("strong", { text: t }), h("small", { text: s }));
    const arrow = (label, sub) =>
      h("div", { class: "sysarrow" },
        h("span", { class: "sysarrow-l", text: label }),
        sub ? h("small", { text: sub }) : null,
        h("span", { class: "sysarrow-h", "aria-hidden": "true", text: "→" }));
    return h("section", { class: "sec", id: "what" },
      h("p", { class: "sec-eyebrow", text: "WHAT THIS IS" }),
      h("h2", { class: "sec-title", text: "A service next to DataHub — not a chatbot, not a plugin" }),
      h("p", { class: "sec-note" },
        "LedgerLens is Python you run beside your catalog. It ",
        h("b", { text: "calls the official DataHub MCP server as a client" }),
        " to read ownership and lineage, plans a bounded response with an LLM, ",
        h("b", { text: "lets deterministic policy authorize the exact plan" }),
        " (the model never self-approves), runs allowlisted tools, and writes a receipt back with ",
        h("code", { text: "save_document" }), "."),
      h("div", { class: "sysmap", "data-testid": "system-map" },
        box("Your DataHub", "owners · lineage · assertions"),
        arrow("MCP read", "get_entities / get_lineage"),
        box("This repo", "plan → verify → gate → act", "us"),
        arrow("allowlisted", "GitHub · Slack · PD · Jira"),
        box("Your tools", "receipted fanout")),
      h("p", { class: "syswrite" },
        "↩ MCP write-back ", h("code", { text: "save_document" }),
        " — incident receipt returns to DataHub for the next agent."));
  };

  // ---- 2. How THIS REPO works (file-linked steps) --------------------------
  const REPO_STEPS = [
    {
      n: "01",
      title: "Trigger — DataHub assertion / intake",
      file: "src/ledgerlens/orchestrator.py",
      fileLabel: "orchestrator.py",
      why: "Something in the catalog fails a freshness or quality check. LedgerLens starts a typed incident run.",
      does: "Builds an incident record (id, severity, entity URN, observed vs threshold). Invalidates any earlier authorization.",
      io: "IN  assertion / trigger payload\nOUT incident_id + root dataset URN",
    },
    {
      n: "02",
      title: "Read DataHub context (MCP client)",
      file: "src/ledgerlens/datahub_context.py",
      fileLabel: "datahub_context.py",
      why: "Authority must be grounded in catalog facts, not model guesses.",
      does: "Calls official MCP get_entities + get_lineage. Records owner, tier, runbook pointers, schema hints, and a bounded blast radius. Unknowns stay explicit.",
      io: "IN  get_entities([urn]) · get_lineage(urn, downstream, hops=2)\nOUT grounded facts the gate will check against",
    },
    {
      n: "03",
      title: "Plan — AI proposes bounded actions",
      file: "src/ledgerlens/orchestrator.py",
      fileLabel: "orchestrator.py (planner)",
      why: "The model is good at drafting; it is not allowed to decide safety alone.",
      does: "Proposes only allowlisted, reversible collaboration actions (issue, Slack, page, Jira). Binds them to a cryptographic plan fingerprint.",
      io: "IN  grounded context + allowlist\nOUT plan steps + plan_fingerprint",
    },
    {
      n: "04",
      title: "Verify — AI review is advisory only",
      file: "src/ledgerlens/verification.py",
      fileLabel: "verification.py",
      why: "A second model can catch mistakes — but still cannot open the gate.",
      does: "2-of-2 verifier quorum votes approve / reject. Votes feed policy checks; they never mint authorization.",
      io: "IN  plan + evidence IDs\nOUT advisory approvals / confidence (not a grant)",
    },
    {
      n: "05",
      title: "Policy gate — deterministic authorization",
      file: "src/ledgerlens/verification.py",
      fileLabel: "PolicyGate / evaluate_authorization",
      why: "This is the differentiator: exact-plan authorization in plain Python.",
      does: "Checks grounding, allowlist, reversibility, quorum, confidence, and that the executed plan fingerprint still matches the reviewed plan. Fail closed.",
      io: "IN  reviewed fingerprint + confirmation\nOUT AUTHORIZED | DENIED + reason codes",
    },
    {
      n: "06",
      title: "Act — allowlisted adapters only",
      file: "src/ledgerlens/actions/",
      fileLabel: "actions/* adapters",
      why: "Work must leave a receipt, not a chat transcript.",
      does: "GitHub / Slack / PagerDuty / Jira adapters run preview/execute with idempotency. Off-allowlist targets never run.",
      io: "IN  authorized action set\nOUT provider receipts (live or fixture://)",
    },
    {
      n: "07",
      title: "Write-back — receipt to DataHub",
      file: "src/ledgerlens/datahub_writeback.py",
      fileLabel: "datahub_writeback.py",
      why: "The next agent must inherit facts, not re-derive them from chat.",
      does: "One allowlisted mutation: MCP save_document with the incident command receipt, then get_entities retrieval for handoff.",
      io: "IN  save_document(title, content, related_assets)\nOUT document URN + next-agent memory package",
    },
    {
      n: "08",
      title: "Handoff — next agent inherits state",
      file: "src/ledgerlens/orchestrator.py",
      fileLabel: "orchestrator (memory)",
      why: "Continuity without confabulating recovery.",
      does: "Packages known facts, unknowns (cause / impact / recovery stay unknown unless proven), provenance, and required next checks.",
      io: "OUT memory package · ready for the next operator or agent",
    },
  ];

  const buildRepoHow = () => {
    const list = h("div", { class: "repo-steps", "data-testid": "repo-how-it-works" });
    for (const s of REPO_STEPS) {
      const body = h("div", { class: "repo-step-body" },
        h("p", { class: "repo-why" }, h("b", { text: "Why — " }), s.why),
        h("p", { class: "repo-does" }, h("b", { text: "What the code does — " }), s.does),
        h("pre", { class: "code-block repo-io", text: s.io }),
        h("p", { class: "repo-file" }, "Code: ", fileLink(s.file, s.fileLabel)));
      const head = h("button", {
        type: "button",
        class: "repo-step-hd",
        "aria-expanded": "true",
      },
        h("span", { class: "repo-n", text: s.n }),
        h("span", { class: "repo-title", text: s.title }),
        h("span", { class: "repo-chev", "aria-hidden": "true", text: "▾" }));
      head.addEventListener("click", () => {
        const open = head.getAttribute("aria-expanded") === "true";
        head.setAttribute("aria-expanded", open ? "false" : "true");
        body.hidden = open;
        head.querySelector(".repo-chev").textContent = open ? "▸" : "▾";
      });
      list.append(h("article", { class: "repo-step", "data-step": s.n }, head, body));
    }
    return h("section", { class: "sec", id: "how-repo-works" },
      h("p", { class: "sec-eyebrow", text: "HOW THIS REPO WORKS" }),
      h("h2", { class: "sec-title", text: "Eight code steps — DataHub in, receipts out" }),
      h("p", { class: "sec-note" },
        "Each step maps to a real module in ",
        h("a", { href: REPO, target: "_blank", rel: "noopener", text: "tomyimkc/ledgerlens" }),
        ". Open a step to see why it exists, what runs, and the I/O contract."),
      list);
  };

  // ---- 3. MCP I/O (prominent) ----------------------------------------------
  const buildMcpIo = () => {
    const ioCard = (tagText, tagCls, tool, code, note) =>
      h("article", { class: "io-card" },
        h("div", { class: "io-hd" },
          h("span", { class: "io-tag " + tagCls, text: tagText }),
          h("code", { class: "io-tool", text: tool })),
        h("pre", { class: "code-block io-code", text: code.join("\n") }),
        note);
    return h("section", { class: "sec", id: "mcp-io", "data-testid": "mcp-io" },
      h("p", { class: "sec-eyebrow", text: "DATAHUB MCP CONTRACT" }),
      h("h2", { class: "sec-title", text: "What goes into DataHub, what comes out" }),
      h("p", { class: "sec-note" },
        "LedgerLens speaks only the official DataHub MCP surface — no bespoke catalog API. ",
        "Read path is read-only; the only mutation is one allowlisted document write-back."),
      h("div", { class: "io-grid" },
        ioCard("INPUT · READ", "read", "mcp-server-datahub · read-only", [
          "get_entities([\"urn:li:dataset:(…,analytics.payments_daily,PROD)\"])",
          "  → ownership, tier, schemaMetadata,",
          "     customProperties{ ledgerlens.runbookUrl, … }",
          "",
          "get_lineage(root_urn, direction=\"downstream\", max_hops=2)",
          "  → [ finance.revenue_executive, risk.payment_anomaly_features, … ]",
        ], h("p", { class: "io-note" }, "⇒ becomes the grounded facts the ", h("b", { text: "policy gate" }), " authorizes against.")),
        ioCard("OUTPUT · WRITE-BACK", "write", "mcp-server-datahub · save_document", [
          "// the ONE allowlisted mutation",
          "{ document_type: \"Context\",",
          "  title:   \"LedgerLens incident command receipt: INC-…\",",
          "  content: \"## Bounded incident command receipt …\",",
          "  related_assets: [\"urn:li:dataset:(…,mart_product_kpis,PROD)\"] }",
          "",
          "// DataHub response",
          "{ success: true, urn: \"urn:li:document:…\" }",
          "// then get_entities(urn) for the next agent",
        ], h("p", { class: "io-note" }, "⇒ real local DataHub OSS evidence: ",
          h("a", { href: EVIDENCE, target: "_blank", rel: "noopener", text: "E-07" }),
          ". A receipt is not recovery."))));
  };

  // ---- 4. Compact pipeline strip -------------------------------------------
  const NODES = [
    ["◎", "Trigger", "assertion / intake"],
    ["◇", "DataHub", "get_entities + lineage"],
    ["▤", "Plan", "AI proposes"],
    ["◈", "Verify", "advisory only"],
    ["⛨", "Gate", "exact plan hash"],
    ["⇶", "Act", "allowlisted tools"],
    ["⤴", "Write-back", "save_document"],
    ["⇉", "Handoff", "next agent"],
  ];
  const buildPipe = () => {
    const pipe = h("div", { class: "pipe" });
    NODES.forEach(([icon, label, sub], i) => {
      pipe.append(h("div", { class: "pnode done" },
        h("span", { class: "pnode-icon", text: icon }),
        h("span", { class: "pnode-label", text: label }),
        h("small", { class: "pnode-sub", text: sub })));
      if (i < NODES.length - 1) {
        pipe.append(h("span", { class: "parrow filled" },
          h("span", { class: "packet", "aria-hidden": "true" })));
      }
    });
    return h("section", { class: "sec", id: "pipeline" },
      h("p", { class: "sec-eyebrow", text: "ONE PIPELINE" }),
      h("h2", { class: "sec-title", text: "DataHub MCP → context → plan → gate → act → write-back" }),
      h("div", { class: "pipe-wrap" }, pipe));
  };

  // ---- 5. Terminal: see the orchestrator path ------------------------------
  const TERMINAL = [
    { cmd: "uv run ledgerlens incident --replay freshness_breach" },
    { tag: "orchestrator", msg: "trigger    freshness assertion FAILED (observed 23m > 15m SLO)" },
    { tag: "datahub_context", msg: "MCP read   get_entities + get_lineage …", ok: "owner=data-platform tier=1 · 3 downstream" },
    { tag: "planner", msg: "plan       4 bounded, reversible actions", ok: "fingerprint=20f3ace2" },
    { tag: "verification", msg: "verify     verifier-A ✓  verifier-B ✓  quorum 2/2", ok: "advisory only" },
    { tag: "PolicyGate", msg: "authorize  exact-plan hash · allowlist · grounding", ok: "AUTHORIZED" },
    { tag: "actions", msg: "act        github / slack / pagerduty / jira", ok: "fixture://… ×4" },
    { tag: "datahub_writeback", msg: "writeback  save_document → DataHub", ok: "recorded" },
    { tag: "memory", msg: "handoff    known facts + unknowns packaged", ok: "ready" },
    { done: "✓ done · cause, impact, recovery remain unknown unless proven · fixture replay" },
  ];
  const termLine = (l) => {
    if (l.cmd) return h("div", { class: "term-line cmd" }, h("span", { class: "term-prompt", text: "$ " }), l.cmd);
    if (l.done) return h("div", { class: "term-line term-done", text: l.done });
    const row = h("div", { class: "term-line" },
      h("span", { class: "term-tag", text: "[" + l.tag + "] " }), l.msg);
    if (l.ok) row.append(h("span", { class: "term-ok", text: "  " + l.ok }));
    return row;
  };
  const buildCode = () => {
    const bodyT = h("div", { class: "term-body" });
    const term = h("div", { class: "terminal", "data-testid": "pipeline-terminal" },
      h("div", { class: "term-bar" },
        h("span", { class: "tdot r" }), h("span", { class: "tdot y" }), h("span", { class: "tdot g" }),
        h("span", { class: "term-title", text: "orchestrator path · fixture replay (same code as live)" })),
      bodyT);
    const reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let started = false;
    const stream = () => {
      if (started) return;
      started = true;
      if (reduce) { for (const l of TERMINAL) bodyT.append(termLine(l)); return; }
      let i = 0;
      const step = () => {
        if (i >= TERMINAL.length) {
          bodyT.append(h("span", { class: "term-cursor", "aria-hidden": "true" }));
          return;
        }
        const line = termLine(TERMINAL[i]);
        line.classList.add("term-in");
        bodyT.append(line);
        i += 1;
        setTimeout(step, 260);
      };
      step();
    };
    if (typeof IntersectionObserver === "function") {
      const io = new IntersectionObserver((entries) => {
        for (const e of entries) if (e.isIntersecting) { io.disconnect(); stream(); }
      }, { threshold: 0.2 });
      io.observe(term);
    } else stream();
    return h("section", { class: "sec", id: "see-it-run" },
      h("p", { class: "sec-eyebrow", text: "SEE IT RUN" }),
      h("h2", { class: "sec-title", text: "Same modules, one fixture incident" }),
      h("p", { class: "sec-note" },
        "Tags in the log match package modules (",
        fileLink("src/ledgerlens/orchestrator.py", "orchestrator"), ", ",
        fileLink("src/ledgerlens/datahub_context.py", "datahub_context"), ", ",
        fileLink("src/ledgerlens/verification.py", "verification"), ", ",
        fileLink("src/ledgerlens/datahub_writeback.py", "datahub_writeback"),
        "). Public demo receipts stay ", h("code", { text: "fixture://" }), "."),
      term);
  };

  // ---- 6. Gate proof -------------------------------------------------------
  const short = (fp) => (fp ? String(fp).slice(0, 8) + "…" : "—");
  const list = (v) => (Array.isArray(v) ? v : []);
  const mark = (status) =>
    h("span", {
      class: "gc-col " + (status === "pass" ? "ok" : "bad"),
      text: status === "pass" ? "✓" : "✕",
    });

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
        h("span", { class: "gc-name" },
          h("strong", { text: c.name }),
          flipped && c.detail ? h("small", { text: c.detail }) : null),
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
      h("p", { class: "proof-sub", text:
        "Reviewed plan authorized. Then one Slack action is appended after review — same DataHub context, different plan fingerprint. Watch which checks flip." }),
      h("div", { class: "proof-fps" },
        h("div", { class: "fp ok" },
          h("small", { text: "REVIEWED PLAN" }),
          h("code", { text: short(d.reviewedPlanFingerprint) }),
          h("span", { class: "fpv ok", text: "✓ authorized" })),
        h("div", { class: "proof-vs", text: "+1 action ⇒" }),
        h("div", { class: "fp bad" },
          h("small", { text: "EXECUTED PLAN" }),
          h("code", { text: short(d.executedPlanFingerprint) }),
          h("span", { class: "fpv bad", text: "✕ DENIED" }))),
      gateChecks(d),
      h("p", { class: "gate-why" },
        h("b", { class: "ok", text: "Why authorized — " }),
        "grounded DataHub context, bounded blast radius, allowlisted reversible actions, complete verifier checks, exact fingerprint + confirmation."),
      h("p", { class: "gate-why" },
        h("b", { class: "bad", text: "Why denied — " }),
        "post-review drift changed the fingerprint, so ",
        h("span", { class: "risk", text: fails.join(" · ") || "fingerprint-bound checks" }),
        " fail closed."),
      h("p", { class: "proof-point" },
        h("b", { text: "AI review is advisory — it cannot open this gate. " }),
        d.point || ""));
  };

  const gateWhere = () => {
    const strip = h("div", { class: "gate-where-strip" });
    NODES.forEach(([, label], i) => {
      const cls = i === 4 ? " active" : (i < 4 ? " done" : "");
      strip.append(h("div", { class: "gw-node" + cls },
        h("span", { class: "gw-n", text: String(i + 1) }),
        h("span", { class: "gw-label", text: label })));
      if (i < NODES.length - 1) {
        strip.append(h("span", { class: "gw-arrow", "aria-hidden": "true", text: "→" }));
      }
    });
    return h("div", { class: "gate-where" },
      strip,
      h("p", { class: "gate-where-cap" },
        h("b", { text: "Where in the repo — " }),
        "phase 5, after plan + advisory verify, before any adapter runs. Implemented in ",
        fileLink("src/ledgerlens/verification.py", "verification.py"),
        ". Change one action after review and nothing executes."));
  };

  const buildProofSection = async () => {
    try {
      const g = await fetch(`${apiBase}/gate-demo`, { credentials: "same-origin" }).then((r) => r.json());
      if (g && g.demo) {
        return h("section", { class: "sec", id: "gate-demo", "data-testid": "gate-demo" },
          h("p", { class: "sec-eyebrow", text: "LIVE PROOF · REAL GATE" }),
          h("h2", { class: "sec-title", text: "Plan drifts after review → DENIED" }),
          gateWhere(),
          gateCard(g.demo));
      }
    } catch (_e) { /* best-effort */ }
    return null;
  };

  // ---- 7. Comparison (secondary) -------------------------------------------
  const COMPARISON = [
    { s: "Freshness SLO breach", d: "payments_daily is 23m stale",
      af: "Pre-wired Slack if configured.",
      ag: "Improvises and self-approves", agRisk: "— may page or “fix” without review.",
      us: "Pages recorded owner, posts blast radius, opens issue.", usGate: "only the reviewed plan runs." },
    { s: "Schema drift", d: "order_total INT → DECIMAL",
      af: "Schema rule notify only.",
      ag: "May auto-migrate the column", agRisk: "— can rewrite production money fields.",
      us: "Flags downstream models, files change record.", usGate: "data-mutation off-allowlist → refused." },
    { s: "ACL change on PII", d: "customers ACL widened",
      af: "Policy-change notify if wired.",
      ag: "Might revert ACL itself", agRisk: "— security incident.",
      us: "SEV-1 + Trust & Safety review.", usGate: "ACL edits refused by design." },
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
    return h("section", { class: "sec", id: "why-not-chatbot" },
      h("p", { class: "sec-eyebrow", text: "WHY NOT A GENERIC AGENT" }),
      h("h2", { class: "sec-title", text: "Same incident — three outcomes" }),
      h("div", { class: "cmp-wrap" },
        h("table", { class: "cmp-table cmp3" },
          h("thead", {}, h("tr", {},
            h("th", { text: "Incident" }),
            h("th", { text: "DataHub Actions" }),
            h("th", { text: "Self-authorizing LLM" }),
            h("th", { class: "us", text: "This repo (policy gate)" }))),
          tbody)),
      h("p", { class: "sec-foot" },
        "Live rehearsal once ran GitHub ",
        h("a", { href: "https://github.com/tomyimkc/ledgerlens/issues/29", target: "_blank", rel: "noopener", text: "#29" }),
        " · Slack · PagerDuty · Jira — ",
        h("a", { href: EVIDENCE, target: "_blank", rel: "noopener", text: "evidence E-16" }),
        ". One bounded action each; not recovery."));
  };

  // ---- 8. Setup ------------------------------------------------------------
  const buildSetup = () => {
    const cards = [
      {
        n: "1",
        t: "Offline fixture (this Space)",
        code: [
          "git clone https://github.com/tomyimkc/ledgerlens.git && cd ledgerlens",
          "make setup && make incident-demo",
          "# → http://127.0.0.1:8000/incident  (fixture:// receipts)",
        ],
        note: "No DataHub call, no provider APIs, no paid model.",
      },
      {
        n: "2",
        t: "Point at your DataHub (live)",
        code: [
          "export DATAHUB_GMS_URL=…  DATAHUB_TOKEN=…",
          "export GITHUB_TOKEN=…  # + Slack / PD / Jira if used",
          "export LEDGERLENS_LLM_API_KEY=…  LEDGERLENS_LLM_BASE_URL=…",
          "make run-all-incidents-live",
        ],
        note: "You own the allowlist. Policy still authorizes the exact plan.",
      },
    ];
    const grid = h("div", { class: "setup-grid" });
    for (const s of cards) {
      grid.append(h("article", { class: "setup-card" },
        h("div", { class: "setup-hd" },
          h("span", { class: "setup-n", text: s.n }),
          h("h3", { text: s.t })),
        h("pre", { class: "code-block setup-code", text: s.code.join("\n") }),
        h("p", { class: "setup-note", text: s.note })));
    }
    return h("section", { class: "sec", id: "get-started" },
      h("p", { class: "sec-eyebrow", text: "GET STARTED" }),
      h("h2", { class: "sec-title", text: "Reproduce from the repo" }),
      grid,
      h("p", { class: "sec-foot" },
        h("a", { href: REPO + "#readme", target: "_blank", rel: "noopener", text: "README" }),
        " · ",
        h("a", { href: EVIDENCE, target: "_blank", rel: "noopener", text: "Evidence index" }),
        " · ",
        h("a", { href: BLOB + "ARCHITECTURE.md", target: "_blank", rel: "noopener", text: "ARCHITECTURE.md" })));
  };

  // ---- page chrome ---------------------------------------------------------
  const decorateHero = () => {
    replayBtn?.remove();
    const heroCopy = root.querySelector(".flow-hero > div");
    if (heroCopy && !heroCopy.querySelector(".hero-sub")) {
      heroCopy.append(h("p", { class: "hero-sub", text:
        "This page walks the real modules: DataHub MCP read → plan → advisory verify → deterministic gate → allowlisted act → save_document write-back. Fixture mode never mutates providers." }));
    }
    const orient = root.querySelector(".orient");
    if (orient && !orient.querySelector(".toc-links")) {
      orient.append(h("nav", { class: "toc-links", "aria-label": "On this page" },
        h("a", { href: "#how-repo-works", text: "How the repo works" }),
        h("a", { href: "#mcp-io", text: "MCP I/O" }),
        h("a", { href: "#see-it-run", text: "See it run" }),
        h("a", { href: "#gate-demo", text: "Gate proof" }),
        h("a", { href: "#get-started", text: "Setup" })));
    }
  };

  const start = async () => {
    body.classList.add("js");
    decorateHero();
    timelineEl?.replaceChildren();
    hintEl?.replaceChildren();
    pipeEl.closest(".pipe-sticky")?.remove();
    proofsEl?.remove();
    detailEl.replaceChildren(
      h("div", { class: "logloading" },
        h("span", { class: "sv-spinner", "aria-hidden": "true" }), GATE));
    const proof = await buildProofSection();
    detailEl.replaceChildren(
      buildWhat(),
      buildRepoHow(),
      buildMcpIo(),
      buildPipe(),
      buildCode(),
      ...(proof ? [proof] : []),
      buildComparison(),
      buildSetup());
  };

  start();
})();
