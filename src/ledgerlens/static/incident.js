(() => {
  "use strict";

  const body = document.body;
  const apiBase = body.dataset.apiBase;
  const root = document.querySelector("[data-flow-root]");
  const pipeEl = document.querySelector("[data-pipe]");
  const detailEl = document.querySelector("[data-detail]");
  const proofsEl = document.querySelector("[data-proofs]");
  const timelineEl = document.querySelector("[data-timeline]");
  const hintEl = document.querySelector("[data-scrollhint]");
  const replayBtn = document.querySelector("[data-flow-replay]");
  const GATE = "Loading the live safety check…";

  if (!root || !pipeEl || !detailEl) return;

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

  const REPO = "https://github.com/tomyimkc/ledgerlens";
  // Prefer main; line anchors still resolve once the PR lands. Path-only links always work.
  const BLOB = REPO + "/blob/main/";
  const EVIDENCE = BLOB + "docs/EVIDENCE_INDEX.md";
  const fileLink = (path, label, lines) => {
    let href = BLOB + path;
    if (lines) href += "#L" + String(lines).replace("-", "-L");
    return h("a", {
      class: "file-link",
      href: href,
      target: "_blank",
      rel: "noopener",
      text: label || path,
    });
  };
  const codeCard = (title, path, lines, code, note) => {
    const head = h("div", { class: "code-card-hd" },
      h("strong", { text: title }),
      fileLink(path, path + (lines ? ":" + lines : ""), lines));
    return h("article", { class: "code-card real-code", "data-testid": "real-code" },
      head,
      h("pre", { class: "code-block", text: code }),
      note ? h("p", { class: "code-card-note", text: note }) : null);
  };

  const buildWhat = () => {
    const box = (t, s, cls) =>
      h("div", { class: "sysbox" + (cls ? " " + cls : "") }, h("strong", { text: t }), h("small", { text: s }));
    const arrow = (label, sub) =>
      h("div", { class: "sysarrow" },
        h("span", { class: "sysarrow-l", text: label }),
        sub ? h("small", { text: sub }) : null,
        h("span", { class: "sysarrow-h", "aria-hidden": "true", text: "\u2192" }));
    return h("section", { class: "sec", id: "what" },
      h("p", { class: "sec-eyebrow", text: "IN ONE SENTENCE" }),
      h("h2", { class: "sec-title", text: "An AI agent for data incidents — with tools you own, and a lock the model cannot open" }),
      h("p", { class: "sec-note" },
        "Think of ", h("b", { text: "DataHub" }),
        " as the company map of its data. LedgerLens is an ",
        h("b", { text: "AI-native incident agent" }),
        ": it ", h("b", { text: "calls tools" }),
        " (DataHub MCP, GitHub, Slack, PagerDuty, Jira — and more you allowlist), ",
        "uses ", h("b", { text: "your LLM" }),
        " to choose which tool calls to propose, then a ",
        h("b", { text: "non-model policy gate" }),
        " decides whether that exact tool plan may run. Receipts go back into DataHub."),
      h("p", { class: "sec-note pitch-line" },
        h("b", { text: "Agentic, not a fixed BPMN workflow: " }),
        "the model selects from a tool belt; the sequence is one agent turn with observe → plan tool calls → (optional) review → authorize → execute tools → write memory. ",
        "Planning is not authority — tool use only after the seal matches."),
      h("p", { class: "sec-note" },
        "Not a free-chat bot that invents owners. Not a rigid eight-box flowchart product. ",
        "It is an agent runtime you put next to DataHub, with ",
        h("b", { text: "bring-your-own model" }),
        " and ",
        h("b", { text: "tools you integrate" }),
        "."),
      h("div", { class: "sysmap", "data-testid": "system-map" },
        box("Your DataHub", "MCP tools · owners · lineage"),
        arrow("agent tools", "get_entities · get_lineage"),
        box("LedgerLens agent", "LLM plan + policy gate", "us"),
        arrow("allowlisted tools", "you register targets"),
        box("Your tools", "GitHub · Slack · PD · Jira · …")),
      h("p", { class: "syswrite" },
        "\u21a9 After tool runs, one allowlisted write-back tool files a receipt in DataHub for the next agent or human."));
  };

  const buildAiSplit = () => {
    const uses = h("article", { class: "ai-card uses" },
      h("h3", { text: "AI-native (agent brain + tool choice)" }),
      h("ul", {},
        h("li", { text: "Planner model proposes a structured tool plan (which allowlisted tools, which targets)." }),
        h("li", { text: "Optional verifier models review that tool plan — still advice, not authority." }),
        h("li", { text: "Bring your own LLM: any OpenAI-compatible endpoint (LEDGERLENS_LLM_*). Public demo uses fixed fixture structure without charging your key." })));
    const noAi = h("article", { class: "ai-card no-ai" },
      h("h3", { text: "Not AI (tool facts + policy lock)" }),
      h("ul", {},
        h("li", { text: "Catalog facts come from DataHub tool calls, not from the model inventing owners." }),
        h("li", { text: "Tool execution is gated by ordinary Python policy: allowlists, reversible actions, exact plan fingerprint." }),
        h("li", { text: "If the agent’s tool plan changes after review (even one extra Slack post), the lock refuses. The model cannot override that." })));
    return h("section", { class: "sec", id: "ai-or-not", "data-testid": "ai-or-not" },
      h("p", { class: "sec-eyebrow", text: "DOES IT USE AN LLM?" }),
      h("h2", { class: "sec-title", text: "Yes for drafting. No for the final go / no-go." }),
      h("p", { class: "sec-note" },
        "This is the most important thing to understand. Many AI demos let the model ",
        h("b", { text: "both invent the plan and approve it" }),
        ". That is risky at 2 a.m. when data is on fire. LedgerLens splits those jobs."),
      h("div", { class: "ai-split", "data-testid": "ai-split" }, uses, noAi),
      h("p", { class: "sec-foot" },
        "Plain English: ",
        h("b", { text: "AI may propose. AI may comment. AI may not authorize itself." })));
  };

  /** Build a responsive comparison table. cols = header labels; rows = array of cell arrays (string or node). */
  const dataTable = (cols, rows, opts) => {
    const o = opts || {};
    const thead = h("thead", {},
      h("tr", {}, ...cols.map((c, i) =>
        h("th", {
          class: (o.colClass && o.colClass[i]) || (i === cols.length - 1 ? "us" : null),
          scope: "col",
          text: c,
        }))));
    const tbody = h("tbody");
    for (const row of rows) {
      const tr = h("tr", {});
      row.forEach((cell, i) => {
        const cls = (o.colClass && o.colClass[i]) || null;
        if (i === 0 && o.firstIsHeader !== false) {
          tr.append(h("th", { scope: "row", class: cls },
            typeof cell === "string" ? h("strong", { text: cell }) : cell));
        } else if (typeof cell === "string") {
          tr.append(h("td", { class: cls, text: cell }));
        } else {
          tr.append(h("td", { class: cls }, cell));
        }
      });
      tbody.append(tr);
    }
    return h("div", { class: "cmp-wrap judge-table-wrap" + (o.wrapClass ? " " + o.wrapClass : "") },
      h("table", {
        class: "cmp-table judge-table" + (o.tableClass ? " " + o.tableClass : ""),
        "data-testid": o.testId || null,
      }, thead, tbody));
  };

  const buildUnique = () =>
    h("section", { class: "sec", id: "unique", "data-testid": "what-is-unique" },
      h("p", { class: "sec-eyebrow", text: "WHAT MAKES THIS DIFFERENT" }),
      h("h2", { class: "sec-title", text: "Not a smarter plan — a different place for authority" }),
      h("p", { class: "pitch-line", "data-testid": "authority-pitch" },
        h("b", { text: "In one line: " }),
        "Most AI plan modes treat the model as both author and approver of work. LedgerLens treats the model as an advisor: DataHub supplies the facts, a deterministic policy authorizes only the exact allowlisted plan that was reviewed, and every action leaves a receipt — so a drifted or self-expanded plan cannot run."),
      h("div", { class: "unique-grid" },
        h("article", { class: "unique-card" },
          h("h3", { text: "AI plan mode (typical)" }),
          h("p", { text: "Model drafts a plan → the same model (or a soft score) decides it is fine → tools run. Approve the idea, not the exact bytes. Quiet plan drift after “OK” is easy." })),
        h("article", { class: "unique-card us" },
          h("h3", { text: "LedgerLens" }),
          h("p", { text: "DataHub grounds facts → model may draft/review → non-model policy binds a fingerprint of the exact step list + allowlist → only that plan runs → receipts back into DataHub. Change one step after the seal? Denied." }))),
      h("p", { class: "sec-foot" },
        "Comparison tables next. Live gate proof: ",
        h("a", { href: "#gate-demo", text: "same context, changed plan → blocked" }),
        ". Disagree with the AI draft? ",
        h("a", { href: "#alternate-plan", text: "re-seal under the same lock" }),
        "."));

  // Three columns only: no meta “how hard to scrutinize” column for external readers.
  const VS_PLAN_MODE = [
    ["Who can say “run it”",
      "Often the same model that planned, or a human click with no plan binding",
      "Deterministic gate: grounded DataHub context, reversible allowlisted actions, plan fingerprint, grant"],
    ["What “approve” means",
      "Approve the idea (“looks good”)",
      "Approve this exact step list (hash of objective + scope + steps)"],
    ["Where truth comes from",
      "Chat context / model memory / scraped docs",
      "DataHub owners, lineage, quality signal as first-class context"],
    ["What can run",
      "Whatever tools the agent session has",
      "Fixed collaboration surface (GitHub / Slack / PagerDuty / Jira + one write-back). No production mutation by default"],
    ["Self-expansion after review",
      "Model can invent new targets or tools mid-run",
      "Off-allowlist target → deny. Extra step after seal → deny"],
    ["After the action",
      "Chat log / raw tool JSON",
      "Provider receipts + optional DataHub document + explicit unknowns handoff"],
    ["Human disagrees with AI plan",
      "Re-prompt or abort (often deny-stuck or free-form re-plan)",
      "Alternate template / custom steps → new seal → same gate (prior grant wiped)"],
    ["How autonomy is bounded",
      "Often a continuous agent loop that self-approves",
      "Operator confirmation or verifier quorum + policy; this public page is a labeled fixture replay"],
  ];

  const NOT_DIFFERENT = [
    ["Having a multi-step plan", "Plan-then-execute is common; the difference is who authorizes"],
    ["Using an LLM at all", "Models draft and optionally review; they do not open the gate"],
    ["Human confirmation", "Many systems ask a human; we bind confirmation to the plan fingerprint"],
    ["A multi-stage pipeline UI", "The product center is the fail-closed policy, not the diagram"],
    ["Calling the system “safe AI”", "We block silent expansion and self-authorization; we do not certify every message’s wording"],
  ];

  const REDUCE_VS_NOT = [
    ["Silent plan drift after review", "Yes — fingerprint mismatch closes the gate", "No — if a human authorizes a bad-but-allowed plan"],
    ["Model inventing owners / lineage", "Yes — facts come from DataHub, not the model", "No — if DataHub metadata is wrong or stale"],
    ["Off-allowlist tools / channels", "Yes — PolicyGate + dashboard allowlist refuse", "No — allowlisted text can still be noisy or unhelpful"],
    ["Self-authorization by the model", "Yes — AI cannot open the gate", "No — a human can still approve a weak plan"],
    ["Accountability / handoff", "Yes — receipts + unknowns preserved", "No — does not prove root cause, impact, or recovery"],
    ["Incident fully fixed", "Out of scope by design", "We coordinate work; we do not claim automatic recovery or MTTR reduction"],
  ];

  const CLAIM_LAYERS = [
    ["Public Space (this page)", "Full visible flow with fixture:// receipts", "Live DataHub, live pages, or production reliability", "Open this Space · E-01"],
    ["Plan-exact gate", "Same DataHub context + one extra step → denied", "That every organization’s full policy is encoded here", "Live proof below · tests"],
    ["Real pipeline gate (E-15)", "Context-on authorizes; context-off refuses with reason codes", "Model uplift or better planning ability", "Benchmarks · real-pipeline receipt"],
    ["Live four-provider run (E-16)", "One supervised plan→verify→authorize→GitHub+Slack+PD+Jira", "Sustained production multi-provider operation", "GitHub #29 · KAN-2 · receipt"],
    ["DataHub write-back (E-07)", "Controlled save_document + MCP read-back on OSS", "Hosted public DataHub or recovery proof", "Write-back receipt"],
    ["Upstream MCP contribution", "Open issue #159 / PR #160 with tests", "Merged or accepted by DataHub maintainers", "GitHub PR (open)"],
  ];

  const SCOPE_TABLE = [
    ["DataHub context and write-back", "Reads owners/lineage/quality via MCP; controlled document write-back path", "This public page does not call a live DataHub"],
    ["End-to-end command path", "Typed state machine, policy gate, tests, one linked live four-provider rehearsal", "Not continuous production multi-provider ops"],
    ["Design focus", "Plan-fingerprint + fail-closed policy over a DataHub incident loop", "Not a new foundation model; not unrestricted automation"],
    ["Operational role", "Coordinate allowlisted collaboration and handoff at incident time", "Does not auto-remediate pipelines or assert root cause"],
    ["Reproducibility", "Open Apache-2.0 repo, one-command fixture demo, labeled receipts", "Full live path needs your own credentials"],
  ];

  const buildVsPlanMode = () =>
    h("section", { class: "sec", id: "vs-plan-mode", "data-testid": "vs-plan-mode" },
      h("p", { class: "sec-eyebrow", text: "COMPARISON" }),
      h("h2", { class: "sec-title", text: "AI plan mode vs LedgerLens" }),
      h("p", { class: "sec-note" },
        "The shape (plan → act) is shared by many agents. The product difference is ",
        h("b", { text: "where authority sits" }),
        ": model advisory output versus a deterministic gate bound to an exact plan and an allowlist. The tables below also state what is ",
        h("b", { text: "not" }),
        " claimed."),

      h("h3", { class: "table-title", text: "1. Side-by-side" }),
      dataTable(
        ["Dimension", "Typical AI plan mode", "LedgerLens"],
        VS_PLAN_MODE.map((r) => r.slice()),
        { testId: "table-vs-plan-mode", tableClass: "cmp3" }
      ),

      h("h3", { class: "table-title", text: "2. Shared building blocks (still different in the middle)" }),
      h("p", { class: "sec-note" },
        "These pieces are common; the binding of authorization to the exact plan is not."),
      dataTable(
        ["Building block", "How LedgerLens uses it"],
        NOT_DIFFERENT.map((r) => r.slice()),
        { testId: "table-not-different", tableClass: "cmp2", colClass: [null, null] }
      ),

      h("h3", { class: "table-title", text: "3. What risk is reduced — and what is not" }),
      dataTable(
        ["Risk / outcome", "Reduced by LedgerLens?", "Still open / out of scope"],
        REDUCE_VS_NOT.map((r) => r.slice()),
        { testId: "table-reduce-vs-not", tableClass: "cmp3" }
      ),

      h("h3", { class: "table-title", text: "4. Evidence layers (keep them separate)" }),
      h("p", { class: "sec-note" },
        "This public page is a ",
        h("b", { text: "safe fixture" }),
        " (",
        h("code", { text: "fixture://" }),
        " receipts). Live runs are separate, narrow, and labeled."),
      dataTable(
        ["Layer", "What is shown", "What is not claimed", "Where to verify"],
        CLAIM_LAYERS.map((r) => r.slice()),
        { testId: "table-claim-layers", tableClass: "cmp4" }
      ),

      h("h3", { class: "table-title", text: "5. Scope and limits" }),
      dataTable(
        ["Area", "In scope for this project", "Out of scope / not claimed"],
        SCOPE_TABLE.map((r) => r.slice()),
        { testId: "table-scope-limits", tableClass: "cmp3" }
      ),

      h("div", { class: "judge-takeaway", "data-testid": "compare-takeaway" },
        h("p", {},
          h("b", { text: "Summary. " }),
          "AI may draft; AI may comment; AI may not authorize itself. The seal is the exact reviewed plan. DataHub is the map and the paper trail."),
        h("p", { class: "sec-foot" },
          "Next: ",
          h("a", { href: "#gate-demo", text: "live gate on plan drift" }),
          " · ",
          h("a", { href: "#real-code", text: "real Python" }),
          " · ",
          h("a", { href: EVIDENCE, target: "_blank", rel: "noopener", text: "evidence index" }),
          ".")));

  const TEMPLATES_UI = [
    { id: "notify_and_ticket", label: "Notify + ticket only", why: "Quieter human choice: Slack + one GitHub issue + DataHub receipt." },
    { id: "ticket_only", label: "Ticket trackers only", why: "GitHub + Jira + receipt. No chat or page noise." },
    { id: "notify_only", label: "Notify on-call only", why: "Slack + PagerDuty note + receipt. No new tickets." },
    { id: "full_fanout", label: "Restore full fanout", why: "Back to the AI-style default (all four tools + receipt)." },
  ];

  const buildAlternatePlan = () => {
    const status = h("div", {
      class: "alt-status",
      "data-alt-status": "1",
      "aria-live": "polite",
    }, h("p", { class: "alt-status-lead", text: "Loading this page live demo state…" }));
    const buttons = h("div", { class: "alt-grid", "data-testid": "alternate-plan-buttons" });

    const setStatus = (nodes) => {
      status.replaceChildren(...(Array.isArray(nodes) ? nodes : [nodes]));
    };

    const refreshStateLine = async () => {
      try {
        const r = await fetch(apiBase + "/state", { credentials: "same-origin" }).then((x) => x.json());
        const s = r && r.state;
        if (!s || !s.planner) {
          setStatus(h("p", { text: "Demo state not ready yet." }));
          return;
        }
        const fp = (s.authorization && s.authorization.plan_hash) || s.planner.plan_hash || "-";
        const n = (s.planner.steps || []).length;
        const actions = (s.actions || []).map((a) => a.provider).join(", ") || "none yet";
        setStatus([
          h("p", {},
            h("b", { text: "Current sealed plan - " }),
            h("code", { text: String(fp).slice(0, 12) + (String(fp).length > 12 ? "..." : "") }),
            " · " + n + " step(s) · providers: " + actions),
          h("p", { class: "alt-hint", text:
            "Pick a template below. The seal changes, any prior grant is wiped, and the same Python lock must pass again." }),
        ]);
      } catch (_e) {
        setStatus(h("p", { text: "Could not load demo state (safe to ignore offline)." }));
      }
    };

    const revise = async (templateId, btn) => {
      buttons.querySelectorAll("button").forEach((b) => { b.disabled = true; });
      if (btn) btn.classList.add("is-busy");
      setStatus(h("p", { text: "Revising plan and wiping any prior grant…" }));
      try {
        const response = await fetch(apiBase + "/plan/revise", {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "Content-Type": "application/json",
            "X-Requested-With": "LedgerLens-Incident-Commander",
          },
          body: JSON.stringify({ template_id: templateId }),
        });
        const r = await response.json();
        if (!response.ok || !r || !r.ok) {
          throw new Error((r && r.detail) || ("Plan revision failed (HTTP " + response.status + ")."));
        }
        const s = r.state || {};
        const fp = r.plan_hash || (s.authorization && s.authorization.plan_hash) || "-";
        const steps = (s.planner && s.planner.steps) || [];
        const decision = (s.authorization && s.authorization.decision) || "pending";
        setStatus([
          h("p", {},
            h("b", { class: "ok", text: "Plan revised · grant wiped. " }),
            "New seal: ", h("code", { text: String(fp) }),
            " · decision: " + decision + " (must re-authorize)."),
          h("p", { text: "Steps now: " + steps.map((st) => st.action).join(" → ") }),
          h("p", { class: "alt-hint", text:
            "Same allowlist and reversibility rules still apply. AI did not approve this change — you did, and the lock still has the final yes/no." }),
        ]);
      } catch (err) {
        setStatus(h("p", { class: "alt-err", text: String(err && err.message ? err.message : err) }));
      } finally {
        buttons.querySelectorAll("button").forEach((b) => {
          b.disabled = false;
          b.classList.remove("is-busy");
        });
      }
    };

    for (const t of TEMPLATES_UI) {
      const btn = h("button", {
        type: "button",
        class: "button button-secondary alt-btn",
        "data-alt-template": t.id,
      },
        h("strong", { text: t.label }),
        h("small", { text: t.why }));
      btn.addEventListener("click", (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        revise(t.id, btn);
      });
      buttons.append(btn);
    }

    refreshStateLine();

    return h("section", { class: "sec", id: "alternate-plan", "data-testid": "alternate-plan" },
      h("p", { class: "sec-eyebrow", text: "IF YOU DISAGREE WITH THE AI PLAN" }),
      h("h2", { class: "sec-title", text: "You are not stuck on deny — swap the plan, re-seal, same lock" }),
      h("p", { class: "sec-note" },
        "A common fear with hard safety locks: if the AI draft is wrong, does everything freeze? ",
        h("b", { text: "No." }),
        " A human commander can replace the proposed steps with a quieter template (or a custom allowlisted list). ",
        "That wipes any old authorization grant, computes a ", h("b", { text: "new fingerprint" }),
        ", and requires the same deterministic gate again. Flexibility without letting the model approve itself."),
      h("div", { class: "alt-api", "data-testid": "alternate-plan-api" },
        h("p", {}, h("b", { text: "In the API — " }),
          h("code", { text: "GET /api/plan-templates" }), ", ",
          h("code", { text: "POST /api/plan/revise" }), " or ",
          h("code", { text: "PUT /api/plan" }),
          " with ", h("code", { text: "template_id" }), " or custom ", h("code", { text: "steps" }), "."),
        h("p", { class: "alt-hint" },
          "Only allowlisted, reversible actions are accepted. Implementation: ",
          fileLink("src/ledgerlens/incident_dashboard.py", "set_plan()", "1268-1293"),
          ".")),
      status,
      buttons,
      h("p", { class: "sec-foot" },
        "Code: ", fileLink("src/ledgerlens/incident_dashboard.py", "incident_dashboard.py"),
        " · ", fileLink("src/ledgerlens/incident_dashboard.py", "PLAN_TEMPLATES", "72"),
        " · ", fileLink("src/ledgerlens/incident_dashboard.py", "validate_plan_payload", "397")));
  };

  const buildRealCode = () =>
    h("section", { class: "sec", id: "real-code", "data-testid": "see-real-code" },
      h("p", { class: "sec-eyebrow", text: "REAL CODE FROM THIS REPO" }),
      h("h2", { class: "sec-title", text: "What actually runs — click through to GitHub" }),
      h("p", { class: "sec-note" },
        "These are not mockups. Each block is a short excerpt of the Python that powers the demo. ",
        "The file link opens the full source on GitHub (with line anchors when known)."),
      h("div", { class: "real-code-grid" },
        codeCard(
          "Seal the exact plan (fingerprint)",
          "src/ledgerlens/incident_dashboard.py",
          "339-346",
          [
            "def plan_fingerprint(state: Mapping[str, Any]) -> str | None:",
            '    """Return a stable fingerprint for the exact proposed plan."""',
            "    payload = _canonical_plan_payload(state)",
            "    if payload is None:",
            "        return None",
            "    canonical = json.dumps(",
            "        payload, ensure_ascii=False,",
            "        separators=(\",\", \":\"), sort_keys=True)",
            "    return hashlib.sha256(",
            "        canonical.encode(\"utf-8\")).hexdigest()[:16]",
          ].join("\n"),
          "Used by the safety lock and by every authorize/execute call."
        ),
        codeCard(
          "Fail-closed gate (no model judgment)",
          "src/ledgerlens/incident_dashboard.py",
          "1064-1093",
          [
            "def evaluate_authorization(state, payload=None) -> JsonObject:",
            '    """Evaluate the fail-closed authorization policy without model judgment."""',
            "    fingerprint = plan_fingerprint(state)",
            "    safe_steps = bool(step_items) and all(",
            "        step.get(\"action\") in ALLOWED_ACTIONS",
            "        and step.get(\"reversible\") is True",
            "        for step in step_items",
            "    )",
            "    # ... phrase + plan_hash must match the seal ...",
            "    allowed = has_request and all(item[\"status\"] == \"pass\" for item in conditions)",
          ].join("\n"),
          "AI output is not an input to this function. Deterministic checks only."
        ),
        codeCard(
          "Disagree with AI: revise + wipe grant",
          "src/ledgerlens/incident_dashboard.py",
          "1268-1293",
          [
            "async def set_plan(self, payload: Mapping[str, Any]) -> JsonObject:",
            "    plan = validate_plan_payload(payload)",
            "    await _backend_call(self.backend, \"set_plan\", plan)",
            "    # Grant wipe: any prior authorization is void once the seal changes.",
            "    with self._lock:",
            "        self._authorizations.clear()",
            "    return await self.snapshot()",
          ].join("\n"),
          "Alternate templates and custom steps both land here."
        ),
        codeCard(
          "Production PolicyGate (allowlist + quorum)",
          "src/ledgerlens/verification.py",
          "311-374",
          [
            "def authorize(self, context, plan, verification) -> AuthorizationDecision:",
            '    """Evaluate all policy rules and deny when any required fact is unknown."""',
            "    if not verification.approved:",
            "        reasons.append(\"verification_not_approved\")",
            "    if len(eligible_families) < self.config.required_quorum:",
            "        reasons.append(\"verifier_quorum_not_met\")",
            "    for action in plan.actions:",
            "        allowance = self._allowances.get(action.action_type)",
            "        if allowance is None:",
            "            reasons.append(f\"action_not_allowlisted:{action.action_id}\")",
            "        if action.target not in allowance.targets:",
            "            reasons.append(f\"target_not_allowlisted:{action.action_id}\")",
          ].join("\n"),
          "This is the production gate for real multi-provider fanout (E-16)."
        ),
        codeCard(
          "How you run the demo locally",
          "src/ledgerlens/cli.py",
          "406-448",
          [
            '@app.command("incident-commander")',
            "def incident_commander(",
            "    host: str = \"127.0.0.1\",",
            "    port: int = 8000,",
            "    fixture: bool = True,",
            "    autonomous: bool = False,",
            ") -> None:",
            '    """Launch the policy-sealed Data Incident Commander."""',
            "    _run_server(..., incident_fixture_mode=fixture,",
            "               incident_autonomous_execution=autonomous,",
            "               incident_only=True)",
          ].join("\n"),
          "Or: make incident-demo  →  scripts/demo_incident_commander.sh"
        )),
      h("p", { class: "sec-foot" },
        "Full tree: ",
        h("a", { href: REPO, target: "_blank", rel: "noopener", text: REPO }),
        " · evidence index: ",
        h("a", { href: EVIDENCE, target: "_blank", rel: "noopener", text: "EVIDENCE_INDEX.md" }),
        "."));

  // Agentic turn phases (not a fixed BPMN workflow product).
  const AGENT_PHASES = [
    { n: "A", role: "sense", title: "Observe with tools", file: "src/ledgerlens/datahub_context.py", fileLabel: "datahub_context.py",
      why: "The agent must ground on catalog truth, not chat memory.",
      does: "Tool calls into DataHub (MCP): entity, owners, tier, lineage / blast radius. Unknowns stay unknown.",
      ai: "No LLM inventing owners — tools return facts.",
      io: "Tools: get_entities · get_lineage  →  IncidentContext" },
    { n: "B", role: "plan", title: "Agent plans tool calls", file: "src/ledgerlens/orchestrator.py", fileLabel: "orchestrator + planner",
      why: "An agent without tools is only prose. Here the model chooses from a tool schema.",
      does: "Your LLM proposes a structured ActionPlan: which allowlisted tools, targets, and parameters. That plan is fingerprinted (the seal).",
      ai: "Yes — LLM agent drafts the tool plan (BYO model).",
      io: "In: context + tool schema  →  Out: plan + plan_fingerprint" },
    { n: "C", role: "critique", title: "Optional AI critique", file: "src/ledgerlens/verification.py", fileLabel: "verification.py",
      why: "A second model can catch a bad tool proposal — still not a green light.",
      does: "Verifier models vote on the same plan. Votes are advisory; they cannot open the gate alone.",
      ai: "Yes — LLM advice only.",
      io: "Out: advisory quorum signals (not authorization)" },
    { n: "D", role: "gate", title: "Policy authorizes the exact tool plan", file: "src/ledgerlens/verification.py", fileLabel: "PolicyGate",
      why: "This is what free-form agents usually skip: non-model authority.",
      does: "Python policy: grounded facts, allowlisted tools/targets, reversible, fingerprint match, claim boundary. Fail closed.",
      ai: "No LLM. Deterministic policy.",
      io: "Out: AUTHORIZED | DENIED + reason codes" },
    { n: "E", role: "act", title: "Execute only sealed tool calls", file: "src/ledgerlens/actions/", fileLabel: "actions/* adapters",
      why: "Real work happens in your systems — with receipts.",
      does: "Tool adapters run the authorized invocations (GitHub issue, Slack post, PagerDuty note, Jira task, …). No extra tools mid-flight.",
      ai: "No LLM inventing new targets after the seal.",
      io: "Out: provider receipts (demo page: fixture:// examples)" },
    { n: "F", role: "memory", title: "Write memory + hand off", file: "src/ledgerlens/datahub_writeback.py", fileLabel: "datahub_writeback.py",
      why: "The next agent or human should not start from zero.",
      does: "Allowlisted DataHub write-back tool stores the receipt; handoff keeps knowns and unknowns explicit.",
      ai: "No LLM rewriting history.",
      io: "Tools: save_document  →  next-agent package" },
  ];

  const TOOL_BELT = [
    { kind: "read", name: "DataHub MCP read", tools: "get_entities · get_lineage", how: "Official DataHub tools — map + blast radius", file: "src/ledgerlens/datahub_context.py" },
    { kind: "write", name: "DataHub MCP write", tools: "save_document (allowlisted)", how: "One receipt document, not free catalog edits", file: "src/ledgerlens/datahub_writeback.py" },
    { kind: "act", name: "GitHub", tools: "github.issue.create", how: "Adapter + allowlisted repo targets", file: "src/ledgerlens/actions/github.py" },
    { kind: "act", name: "Slack", tools: "slack.message.post", how: "Adapter + allowlisted channels", file: "src/ledgerlens/actions/slack.py" },
    { kind: "act", name: "PagerDuty", tools: "pagerduty.incident.note", how: "Adapter + allowlisted incidents", file: "src/ledgerlens/actions/pagerduty.py" },
    { kind: "act", name: "Jira", tools: "jira.issue.create", how: "Adapter + allowlisted projects", file: "src/ledgerlens/actions/jira.py" },
    { kind: "brain", name: "Your LLM", tools: "OpenAI-compatible chat API", how: "Planner + optional verifiers via LEDGERLENS_LLM_*", file: "src/ledgerlens/config.py" },
    { kind: "you", name: "Your tool next", tools: "new action type + adapter", how: "Implement adapter, register allowlist targets, expose in tool schema", file: "src/ledgerlens/actions/base.py" },
  ];

  const buildRepoHow = () => {
    const list = h("div", { class: "repo-steps", "data-testid": "repo-how-it-works" });
    for (const s of AGENT_PHASES) {
      const bodyEl = h("div", { class: "repo-step-body" },
        h("p", { class: "repo-why" }, h("b", { text: "Why — " }), s.why),
        h("p", { class: "repo-does" }, h("b", { text: "Agent does — " }), s.does),
        h("p", { class: "repo-ai" },
          h("b", { text: "AI / tools — " }),
          h("span", { class: s.ai.startsWith("Yes") ? "ai-yes" : "ai-no", text: s.ai })),
        h("pre", { class: "code-block repo-io", text: s.io }),
        h("p", { class: "repo-file" }, "In the code: ", fileLink(s.file, s.fileLabel)));
      const head = h("button", { type: "button", class: "repo-step-hd", "aria-expanded": "true" },
        h("span", { class: "repo-n role-" + s.role, text: s.n }),
        h("span", { class: "repo-title", text: s.title }),
        h("span", { class: "repo-chev", "aria-hidden": "true", text: "\u25be" }));
      head.addEventListener("click", () => {
        const open = head.getAttribute("aria-expanded") === "true";
        head.setAttribute("aria-expanded", open ? "false" : "true");
        bodyEl.hidden = open;
        head.querySelector(".repo-chev").textContent = open ? "\u25b8" : "\u25be";
      });
      list.append(h("article", { class: "repo-step", "data-step": s.n, "data-role": s.role }, head, bodyEl));
    }
    return h("section", { class: "sec", id: "how-repo-works", "data-testid": "agentic-flow" },
      h("p", { class: "sec-eyebrow", text: "AGENTIC FLOW — ONE AGENT TURN" }),
      h("h2", { class: "sec-title", text: "Not a fixed 8-step workflow — an AI agent that uses tools under a policy lock" }),
      h("p", { class: "sec-note" },
        "What looked like “eight boxes” is really ",
        h("b", { text: "one agentic turn" }),
        ": observe with tools → plan tool calls with your LLM → optional critique → ",
        h("b", { text: "non-model authorize" }),
        " → execute sealed tools → write memory. ",
        "The agent chooses among tools you enable; it does not invent authority. ",
        "Wrong tool plan? ",
        h("a", { href: "#alternate-plan", text: "Revise and re-seal" }),
        " under the same lock."),
      list);
  };

  const FLEX_VS_FIXED = [
    ["Which tools to call on this incident", "AI planner agent (selects from catalog)", "Yes — flexible within allowlist"],
    ["Tool targets (repo, channel, project)", "AI proposes; must be in catalog targets", "Yes — among registered destinations"],
    ["Message / issue wording", "AI fills parameters", "Yes — content is model-driven"],
    ["Orchestration phases (sense→plan→gate→act)", "Code state machine", "No — skeleton stays fail-closed"],
    ["May this exact plan run?", "Deterministic policy gate", "No — not model judgment"],
    ["How GitHub/Slack/… I/O works", "Adapter code you ship", "No — agents cannot invent clients"],
    ["Add a brand-new system (e.g. webhook)", "register_tool_spec + adapter + allowlist", "Yes — after you register it once"],
  ];

  const buildToolBelt = () => {
    const grid = h("div", { class: "tool-belt-grid", "data-testid": "tool-belt" });
    for (const t of TOOL_BELT) {
      grid.append(h("article", { class: "tool-card kind-" + t.kind },
        h("span", { class: "tool-kind", text: t.kind }),
        h("h3", { text: t.name }),
        h("code", { class: "tool-names", text: t.tools }),
        h("p", { text: t.how }),
        h("p", { class: "repo-file" }, fileLink(t.file, t.file.split("/").pop()))));
    }
    return h("section", { class: "sec", id: "tool-belt", "data-testid": "integrate-tools" },
      h("p", { class: "sec-eyebrow", text: "AI-NATIVE TOOL USE" }),
      h("h2", { class: "sec-title", text: "Enable AI + integrate your tools" }),
      h("p", { class: "sec-note" },
        "Some parts of the repo look “hard-coded” on purpose. ",
        h("b", { text: "Adapters and the gate are code" }),
        " (safe I/O + authority). ",
        h("b", { text: "Which tools to call" }),
        " is agent work: the planner LLM receives an ",
        h("b", { text: "agent tool catalog" }),
        " and chooses flexibly among allowlisted tools — it does not invent new systems out of thin air."),
      h("h3", { class: "table-title", text: "What the agent chooses vs what stays in code" }),
      dataTable(
        ["Capability", "Who decides", "Flexible via AI?"],
        FLEX_VS_FIXED.map((r) => r.slice()),
        { testId: "table-flex-vs-fixed", tableClass: "cmp3" }
      ),
      h("p", { class: "sec-note" },
        "Catalog implementation: ",
        fileLink("src/ledgerlens/tool_catalog.py", "tool_catalog.py"),
        " · planner injects ",
        h("code", { text: "agentToolCatalog" }),
        " into the model context (",
        fileLink("src/ledgerlens/ai_roles.py", "ai_roles.py"),
        "). Live rehearsals pass the same target map into the planner and the policy gate."),
      h("div", { class: "tool-enable", "data-testid": "enable-ai" },
        h("h3", { class: "table-title", text: "1. Enable the agent brain (your LLM)" }),
        h("pre", { class: "code-block", text: [
          "export LEDGERLENS_LLM_ENABLED=true",
          "export LEDGERLENS_LLM_API_KEY=…          # your key",
          "export LEDGERLENS_LLM_BASE_URL=…        # any OpenAI-compatible endpoint",
          "export LEDGERLENS_LLM_MODEL=…           # planner / verifier model id",
          "# → planner proposes tool plans; verifiers may critique (still advisory)",
        ].join("\n") }),
        h("p", { class: "sec-note" },
          "Config: ", fileLink("src/ledgerlens/config.py", "config.py"),
          ". Public Space stays fixture-only so judges need no key.")),
      h("h3", { class: "table-title", text: "2. Tool belt the agent can propose" }),
      grid,
      h("h3", { class: "table-title", text: "3. Integrate your own tool (pattern)" }),
      h("pre", { class: "code-block", text: [
        "# Pattern (see actions/base.py + runtime_factory allowlists):",
        "1. Implement an ActionAdapter for your system (preview + execute + receipt)",
        "2. Register action_type in the policy allowlist with allowed targets",
        "3. Expose that action in the planner tool schema so the LLM can select it",
        "4. Gate still seals the exact plan — new tool cannot self-authorize",
        "",
        "# Built-ins today: github.issue.create · slack.message.post",
        "#   pagerduty.incident.note · jira.issue.create · datahub.incident.writeback",
      ].join("\n") }),
      h("p", { class: "sec-foot" },
        "Code: ",
        fileLink("src/ledgerlens/actions/base.py", "actions/base.py"),
        " · ",
        fileLink("src/ledgerlens/runtime_factory.py", "runtime_factory.py"),
        " · ",
        fileLink("src/ledgerlens/orchestrator.py", "orchestrator.py"),
        ". Live four-tool rehearsal: evidence E-16."));
  };

  const buildMcpIo = () => {
    const ioCard = (tagText, tagCls, title, lines, note) =>
      h("article", { class: "io-card" },
        h("div", { class: "io-hd" },
          h("span", { class: "io-tag " + tagCls, text: tagText }),
          h("strong", { class: "io-tool", text: title })),
        h("pre", { class: "code-block io-code", text: lines.join("\n") }),
        note);
    return h("section", { class: "sec", id: "mcp-io", "data-testid": "mcp-io" },
      h("p", { class: "sec-eyebrow", text: "TALKING TO DATAHUB" }),
      h("h2", { class: "sec-title", text: "What we ask DataHub for — and what we put back" }),
      h("p", { class: "sec-note" },
        "We do not invent a private API. We use DataHub official tools: read the map, then write one document as a receipt."),
      h("div", { class: "io-grid" },
        ioCard("WE READ", "read", "Who owns this? What depends on it?", [
          "Ask DataHub about the broken dataset…",
          "  → owner, importance, schema notes",
          "  → downstream tables / models (blast radius)",
          "",
          "These facts feed the safety lock.",
          "The model does not invent the owner.",
        ], h("p", { class: "io-note" }, "Technical name: MCP get_entities + get_lineage.")),
        ioCard("WE WRITE BACK", "write", "One receipt document for the next person", [
          "After allowed actions run…",
          "  → create one short incident report in DataHub",
          "  → link it to the same dataset",
          "  → next agent can read that report again",
          "",
          "Only this one write is allowlisted.",
          "A receipt is not we fixed the root cause.",
        ], h("p", { class: "io-note" },
          "Technical name: MCP save_document · evidence ",
          h("a", { href: EVIDENCE, target: "_blank", rel: "noopener", text: "E-07" }), "."))));
  };

  const NODES = [
    ["A", "Sense", "tools → DataHub"],
    ["B", "Plan", "LLM picks tools"],
    ["C", "Critique", "LLM advice"],
    ["D", "Gate", "policy yes/no"],
    ["E", "Tools", "your adapters"],
    ["F", "Memory", "receipt + handoff"],
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
      h("p", { class: "sec-eyebrow", text: "ONE AGENT TURN" }),
      h("h2", { class: "sec-title", text: "Sense → plan tools → gate → run tools → memory" }),
      h("div", { class: "pipe-wrap" }, pipe),
      h("p", { class: "sec-foot" },
        "B–C are AI-native. ", h("b", { text: "D (Gate)" }),
        " is plain Python and has the final say. E is ",
        h("b", { text: "your tool integrations" }),
        " — only what the sealed plan named."));
  };

  const TERMINAL = [
    { cmd: "make incident-demo", href: BLOB + "Makefile" },
    { cmd: "# → uv run bash scripts/demo_incident_commander.sh", href: BLOB + "scripts/demo_incident_commander.sh" },
    { cmd: "# → ledgerlens incident-commander --fixture", href: BLOB + "src/ledgerlens/cli.py#L406" },
    { tag: "trigger", msg: "payments table late (23 min > 15 min limit)" },
    { tag: "tool", msg: "DataHub get_entities + get_lineage", ok: "owner · 3 downstream", href: BLOB + "src/ledgerlens/datahub_context.py" },
    { tag: "agent", msg: "LLM planned tool calls (allowlisted only)", ok: "sealed plan_fingerprint", href: BLOB + "src/ledgerlens/orchestrator.py" },
    { tag: "critique", msg: "verifier models reviewed tool plan", ok: "advice only", href: BLOB + "src/ledgerlens/verification.py" },
    { tag: "gate", msg: "policy: allowlist · seal · grounded", ok: "AUTHORIZED", href: BLOB + "src/ledgerlens/verification.py" },
    { tag: "tools", msg: "GitHub · Slack · PagerDuty · Jira adapters", ok: "receipts", href: BLOB + "src/ledgerlens/actions/" },
    { tag: "tool", msg: "DataHub save_document write-back", ok: "next agent can continue", href: BLOB + "src/ledgerlens/datahub_writeback.py" },
    { done: "agent turn complete · no root-cause claim · fixture data on this public page" },
  ];
  const termLine = (l) => {
    if (l.cmd) {
      const row = h("div", { class: "term-line cmd" }, h("span", { class: "term-prompt", text: "$ " }));
      if (l.href) {
        row.append(h("a", {
          class: "term-code-link",
          href: l.href,
          target: "_blank",
          rel: "noopener",
          text: l.cmd,
        }));
      } else {
        row.append(document.createTextNode(l.cmd));
      }
      return row;
    }
    if (l.done) return h("div", { class: "term-line term-done", text: l.done });
    const row = h("div", { class: "term-line" }, h("span", { class: "term-tag", text: "[" + l.tag + "] " }), l.msg);
    if (l.ok) row.append(h("span", { class: "term-ok", text: "  " + l.ok }));
    if (l.href) {
      row.append(h("a", {
        class: "term-src",
        href: l.href,
        target: "_blank",
        rel: "noopener",
        text: " source",
      }));
    }
    return row;
  };
  const buildCode = () => {
    const bodyT = h("div", { class: "term-body" });
    const term = h("div", { class: "terminal", "data-testid": "pipeline-terminal" },
      h("div", { class: "term-bar" },
        h("span", { class: "tdot r" }), h("span", { class: "tdot y" }), h("span", { class: "tdot g" }),
        h("span", { class: "term-title", text: "what a run looks like · links open real files" })),
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
        setTimeout(step, 280);
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
      h("p", { class: "sec-eyebrow", text: "SEE A RUN" }),
      h("h2", { class: "sec-title", text: "One example, end to end" }),
      h("p", { class: "sec-note" },
        "This public page uses a ", h("b", { text: "safe replay" }),
        " (no real pages or tickets fire). Blue links open the actual repo files that implement each stage. ",
        "Full source cards are in ",
        h("a", { href: "#real-code", text: "Real code from this repo" }), "."),
      term);
  };

  const short = (fp) => (fp ? String(fp).slice(0, 8) + "…" : "—");
  const list = (v) => (Array.isArray(v) ? v : []);
  const mark = (status) =>
    h("span", { class: "gc-col " + (status === "pass" ? "ok" : "bad"), text: status === "pass" ? "✓" : "✕" });

  const gateChecks = (d) => {
    const rev = list(d.approved && d.approved.conditions);
    const exe = list(d.denied && d.denied.conditions);
    const wrap = h("div", { class: "gate-checks" });
    wrap.append(h("div", { class: "gate-check hd" },
      h("span", { class: "gc-name", text: "Safety check" }),
      h("span", { class: "gc-col", text: "Reviewed plan" }),
      h("span", { class: "gc-col", text: "Changed plan" })));
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
        h("h3", { text: "The safety lock in action" }),
        h("span", { class: "proof-tag", text: "what makes us different" })),
      h("p", { class: "proof-sub", text:
        "First the reviewed plan is allowed. Then we secretly add one extra Slack message after review — same data map, different plan. Watch the lock refuse." }),
      h("div", { class: "proof-fps" },
        h("div", { class: "fp ok" },
          h("small", { text: "REVIEWED PLAN (sealed)" }),
          h("code", { text: short(d.reviewedPlanFingerprint) }),
          h("span", { class: "fpv ok", text: "✓ allowed" })),
        h("div", { class: "proof-vs", text: "+1 extra step \u21d2" }),
        h("div", { class: "fp bad" },
          h("small", { text: "CHANGED PLAN" }),
          h("code", { text: short(d.executedPlanFingerprint) }),
          h("span", { class: "fpv bad", text: "✕ blocked" }))),
      gateChecks(d),
      h("p", { class: "gate-why" },
        h("b", { class: "ok", text: "Why allowed — " }),
        "DataHub facts present, only safe tools, reviews complete, seal matches."),
      h("p", { class: "gate-why" },
        h("b", { class: "bad", text: "Why blocked — " }),
        "the seal no longer matches after the extra step. Failed checks: ",
        h("span", { class: "risk", text: fails.join(" · ") || "plan fingerprint" }), "."),
      h("p", { class: "proof-point" },
        h("b", { text: "The AI cannot open this lock. " }),
        d.point || "Only the exact reviewed plan can."));
  };

  const gateWhere = () => {
    const strip = h("div", { class: "gate-where-strip" });
    // Gate is phase D (index 3) in the agent turn.
    NODES.forEach(([icon, label], i) => {
      const cls = i === 3 ? " active" : (i < 3 ? " done" : "");
      strip.append(h("div", { class: "gw-node" + cls },
        h("span", { class: "gw-n", text: icon }),
        h("span", { class: "gw-label", text: label })));
      if (i < NODES.length - 1) {
        strip.append(h("span", { class: "gw-arrow", "aria-hidden": "true", text: "\u2192" }));
      }
    });
    return h("div", { class: "gate-where" },
      strip,
      h("p", { class: "gate-where-cap" },
        h("b", { text: "When the gate runs — " }),
        "after the agent planned tool calls and optional AI critique, ",
        h("b", { text: "before" }),
        " any adapter fires. Ordinary Python in ",
        fileLink("src/ledgerlens/verification.py", "verification.py"), "."));
  };

  const buildProofSection = async () => {
    const scenarios = [
      { id: "reviewed-plan", label: "Run reviewed plan", hint: "unchanged" },
      { id: "append-tool-call", label: "+ unreviewed tool call", hint: "plan drift" },
      { id: "verifier-objection", label: "Verifier objects", hint: "quorum split" },
      { id: "off-allowlist-target", label: "Change tool target", hint: "scope escape" },
    ];
    const controls = h("div", { class: "seal-controls", role: "group", "aria-label": "Seal Lab mutation" });
    const output = h("div", { class: "seal-output", "aria-live": "polite" },
      h("div", { class: "logloading" },
        h("span", { class: "sv-spinner", "aria-hidden": "true" }), " Evaluating reviewed plan…"));
    const proofJson = h("pre", { class: "seal-json", hidden: "hidden" });
    const copyStatus = h("span", { class: "seal-copy-status", "aria-live": "polite" });
    const copyButton = h("button", {
      class: "button seal-copy",
      type: "button",
      text: "Copy redacted proof JSON",
      disabled: "disabled",
    });
    let latestLab = null;

    const renderLab = (lab) => {
      latestLab = lab;
      const result = lab.result || {};
      const authorized = result.decision === "authorized";
      const checks = list(result.conditions);
      const failures = list(result.failedConditions);
      const reviewFp = String(result.reviewedPlanFingerprint || "not available");
      const evaluatedFp = String(result.evaluatedPlanFingerprint || "not available");
      const context = lab.context || {};
      const checkList = h("div", { class: "seal-check-list" });
      if (checks.length) {
        checks.forEach((check) => {
          const status = check.status || "pending";
          checkList.append(h("div", { class: "seal-check " + status },
            mark(status),
            h("span", {},
              h("strong", { text: check.name || "Gate condition" }),
              check.detail ? h("small", { text: check.detail }) : null)));
        });
      } else {
        failures.forEach((failure) => {
          checkList.append(h("div", { class: "seal-check fail" },
            mark("fail"),
            h("span", {}, h("strong", { text: failure }))));
        });
      }
      output.replaceChildren(
        h("div", { class: "seal-verdict " + (authorized ? "authorized" : "denied") },
          h("span", { class: "seal-verdict-k", text: "SERVER GATE DECISION" }),
          h("strong", { text: authorized ? "AUTHORIZED" : "DENIED" }),
          h("small", { text: "tools held · external mutations false" })),
        h("div", { class: "seal-context" },
          h("span", { text: "DATAHUB CONTEXT · UNCHANGED" }),
          h("strong", { text: context.asset || "grounded fixture asset" }),
          h("small", { text:
            (context.owner ? "owner: " + context.owner + " · " : "") +
            (context.blastRadius || "bounded blast radius") })),
        h("div", { class: "seal-fingerprint-row" },
          h("div", {},
            h("small", { text: "REVIEWED SEAL" }),
            h("code", { text: reviewFp })),
          h("span", { class: "seal-arrow", text: reviewFp === evaluatedFp ? "=" : "≠" }),
          h("div", { class: reviewFp === evaluatedFp ? "" : "changed" },
            h("small", { text: "EVALUATED PLAN" }),
            h("code", { text: evaluatedFp }))),
        h("div", { class: "seal-mutation" },
          h("small", { text: "YOUR MUTATION" }),
          h("strong", { text: result.mutation || "None" }),
          h("p", { text: result.explanation || "" })),
        checkList,
        h("p", { class: "seal-engine" },
          h("b", { text: "Executed on the server by " }),
          h("code", { text: result.gate || "deterministic policy" }),
          ". The browser only renders the returned decision."));
      proofJson.textContent = JSON.stringify(lab, null, 2);
      copyButton.removeAttribute("disabled");
    };

    const buttons = new Map();
    const runScenario = async (scenario) => {
      buttons.forEach((button, id) => {
        const active = id === scenario;
        button.classList.toggle("active", active);
        button.setAttribute("aria-pressed", active ? "true" : "false");
      });
      output.replaceChildren(
        h("div", { class: "logloading" },
          h("span", { class: "sv-spinner", "aria-hidden": "true" }),
          " Running the real gate…"));
      copyButton.setAttribute("disabled", "disabled");
      copyStatus.textContent = "";
      const response = await fetch(apiBase + "/seal-lab", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scenario }),
      });
      const payload = await response.json();
      if (!response.ok || !payload.lab) {
        throw new Error(payload.detail || "Seal Lab request failed.");
      }
      renderLab(payload.lab);
    };

    scenarios.forEach((scenario) => {
      const button = h("button", {
        class: "seal-control",
        type: "button",
        "aria-pressed": "false",
      },
      h("strong", { text: scenario.label }),
      h("small", { text: scenario.hint }));
      button.addEventListener("click", () => {
        runScenario(scenario.id).catch((error) => {
          output.replaceChildren(h("p", { class: "seal-error", text: error.message }));
        });
      });
      buttons.set(scenario.id, button);
      controls.append(button);
    });

    copyButton.addEventListener("click", async () => {
      if (!latestLab) return;
      try {
        await navigator.clipboard.writeText(JSON.stringify(latestLab, null, 2));
        copyStatus.textContent = "Copied.";
      } catch (_error) {
        proofJson.hidden = false;
        copyStatus.textContent = "Clipboard unavailable; JSON shown below.";
      }
    });

    const section = h("section", {
      class: "sec seal-lab",
      id: "gate-demo",
      "data-testid": "seal-lab",
    },
    h("p", { class: "sec-eyebrow", text: "INTERACTIVE FIXTURE · REAL GATE CODE" }),
    h("h2", { class: "sec-title", text: "Tamper with the plan. The seal should refuse." }),
    h("p", { class: "sec-note" },
      "Choose one controlled change. Every click calls the server-side authorization code; ",
      h("b", { text: "no provider tool executes" }),
      ". The fixture keeps the DataHub context stable so only the selected boundary changes."),
    gateWhere(),
    controls,
    output,
    h("div", { class: "seal-copy-row" }, copyButton, copyStatus),
    proofJson,
    h("p", { class: "sec-foot" },
      "This demonstrates deterministic gate behavior, not production safety or incident recovery. ",
      h("a", { href: EVIDENCE, target: "_blank", rel: "noopener", text: "Evidence scopes E-01, E-04, E-05, E-15" }),
      "."));
    await runScenario("reviewed-plan");
    return section;
  };

  const contextCutReason = (code) => {
    const parts = String(code || "").split(":");
    if (parts[0] === "required_context_fact_missing") {
      return "tool contract needs " + (parts[2] || "a DataHub fact");
    }
    if (parts[0] === "required_evidence_not_cited") {
      return "recorded plan did not cite " + (parts[2] || "a required fact");
    }
    if (parts[0] === "action_references_unknown_fact") {
      return "recorded plan cites a fact removed by this cut";
    }
    if (parts[0] === "authorized") return "all evidence contracts satisfied";
    return parts[0].replaceAll("_", " ");
  };

  const buildContextCutLab = async () => {
    const scenarios = [
      { id: "full-map", label: "Full map", hint: "owner + lineage + runbook" },
      { id: "owner-cut", label: "Cut ownership", hint: "remove primary-owner" },
      { id: "lineage-cut", label: "Cut lineage", hint: "remove blast-radius" },
      { id: "alert-only", label: "Alert only", hint: "ID + severity" },
    ];
    const controls = h("div", {
      class: "context-cut-controls",
      role: "group",
      "aria-label": "DataHub context cut",
    });
    const output = h("div", { class: "context-cut-output", "aria-live": "polite" },
      h("div", { class: "logloading" },
        h("span", { class: "sv-spinner", "aria-hidden": "true" }),
        " Loading the recorded plan…"));
    const raw = h("pre", { class: "seal-json", hidden: "hidden" });
    const reveal = h("button", {
      class: "button seal-copy",
      type: "button",
      text: "Show redacted replay JSON",
      disabled: "disabled",
    });
    let latest = null;

    const render = (lab) => {
      latest = lab;
      const scenario = lab.scenario || {};
      const replay = lab.livePolicyReplay || {};
      const auth = replay.authorization || {};
      const model = lab.recordedModel || {};
      const plan = model.plan || {};
      const authorized = !!auth.authorized;
      const selected = list(plan.actions).map((action) => action.action_type);
      const removed = list(scenario.removedFactIds);
      const reasons = Array.from(new Set(list(auth.reason_codes).map(contextCutReason)));
      const toolGrid = h("div", { class: "context-tool-grid" });
      list(lab.toolEligibility).forEach((tool) => {
        const eligible = !!tool.eligibleFromContext;
        toolGrid.append(h("div", { class: "context-tool " + (eligible ? "eligible" : "held") },
          h("span", { text: eligible ? "AVAILABLE" : "HELD" }),
          h("strong", { text: tool.actionType || "tool" }),
          h("small", { text: eligible
            ? "required DataHub facts present"
            : "missing: " + list(tool.missingEvidenceFactIds).join(", ") })));
      });
      const reasonList = h("ul", { class: "context-reasons" });
      reasons.forEach((reason) => reasonList.append(h("li", { text: reason })));
      output.replaceChildren(
        h("div", { class: "context-cut-verdict " + (authorized ? "authorized" : "denied") },
          h("div", {},
            h("span", { class: "seal-verdict-k", text: "CURRENT SERVER POLICY" }),
            h("strong", { text: authorized ? "AUTHORIZED" : "DENIED" }),
            h("small", { text: "tools executed: no · external mutations: false" })),
          h("div", { class: "context-cut-seal" },
            h("small", { text: "SAME RECORDED PLAN SEAL" }),
            h("code", { text: replay.planFingerprint || "unavailable" }),
            h("span", { text: selected.length + " selected tools held fixed" }))),
        h("div", { class: "context-cut-facts" },
          h("div", {},
            h("small", { text: "DATAHUB FACTS REMOVED" }),
            h("strong", { text: removed.length ? removed.join(" · ") : "none — full map" })),
          h("div", {},
            h("small", { text: "CONTROLLED QUESTION" }),
            h("p", { text: scenario.question || "" }))),
        toolGrid,
        h("div", { class: "context-cut-explain" },
          h("div", {},
            h("small", { text: "WHY THE GATE DECIDED" }),
            reasonList),
          h("div", {},
            h("small", { text: "EVIDENCE SPLIT" }),
            h("p", {},
              h("b", { text: "Recorded model: " }),
              model.planner || "planner", " proposed the fixed plan. ",
              h("b", { text: "Live now: " }),
              "ordinary Python re-evaluated the typed plan against this context cut. ",
              h("b", { text: "Not run: " }),
              "the planner, verifiers, and provider tools."))),
        h("p", { class: "seal-engine" },
          h("b", { text: "DataHub is load-bearing here: " }),
          authorized
            ? "the cited owner, lineage, asset, and runbook facts satisfy the per-tool evidence contracts."
            : "removing catalog evidence makes the unchanged model plan unexecutable; model approval cannot replace the missing facts."));
      raw.textContent = JSON.stringify(lab, null, 2);
      reveal.removeAttribute("disabled");
    };

    const buttons = new Map();
    const run = async (scenarioId) => {
      buttons.forEach((button, id) => {
        const active = id === scenarioId;
        button.classList.toggle("active", active);
        button.setAttribute("aria-pressed", active ? "true" : "false");
      });
      output.replaceChildren(
        h("div", { class: "logloading" },
          h("span", { class: "sv-spinner", "aria-hidden": "true" }),
          " Replaying the same sealed plan through PolicyGate…"));
      reveal.setAttribute("disabled", "disabled");
      const response = await fetch(apiBase + "/context-cut/" + encodeURIComponent(scenarioId), {
        credentials: "same-origin",
      });
      const payload = await response.json();
      if (!response.ok || !payload.lab) {
        throw new Error(payload.detail || "Context Cut request failed.");
      }
      render(payload.lab);
    };

    scenarios.forEach((scenario) => {
      const button = h("button", {
        class: "seal-control",
        type: "button",
        "aria-pressed": "false",
      },
      h("strong", { text: scenario.label }),
      h("small", { text: scenario.hint }));
      button.addEventListener("click", () => {
        run(scenario.id).catch((error) => {
          output.replaceChildren(h("p", { class: "seal-error", text: error.message }));
        });
      });
      buttons.set(scenario.id, button);
      controls.append(button);
    });
    reveal.addEventListener("click", () => {
      if (!latest) return;
      raw.hidden = !raw.hidden;
      reveal.textContent = raw.hidden ? "Show redacted replay JSON" : "Hide replay JSON";
    });

    const section = h("section", {
      class: "sec context-cut-lab",
      id: "context-cut",
      "data-testid": "context-cut-lab",
    },
    h("p", { class: "sec-eyebrow", text: "RECORDED MODEL PLAN · LIVE POLICY REPLAY" }),
    h("h2", { class: "sec-title", text: "Cut DataHub out. Watch authority disappear." }),
    h("p", { class: "sec-note" },
      "The plan and model verdicts stay exactly fixed. Toggle one synthetic DataHub context cut; ",
      h("b", { text: "the current server gate" }),
      " decides again using per-tool evidence contracts. This is a controlled authorization ablation, not a claim that the planner re-planned."),
    h("div", { class: "context-cut-badges" },
      h("span", { text: "SOURCE · RECORDED MODEL TRACE" }),
      h("span", { text: "NOW · DETERMINISTIC POLICY" }),
      h("span", { text: "PLANNER NOT RE-RUN" }),
      h("span", { text: "TOOLS HELD" })),
    controls,
    output,
    h("div", { class: "seal-copy-row" }, reveal),
    raw,
    h("p", { class: "sec-foot" },
      "Synthetic contexts; no live DataHub request on this page. The source trace used model network calls and zero external mutations. ",
      h("a", { href: EVIDENCE, target: "_blank", rel: "noopener", text: "Evidence scope E-20" }),
      "."));
    await run("full-map");
    return section;
  };

  const buildLiveEvidenceLadder = async () => {
    const response = await fetch(apiBase + "/live-evidence-ladder", {
      credentials: "same-origin",
    });
    const payload = await response.json();
    if (!response.ok || !payload.ladder) {
      throw new Error(payload.detail || "Live-evidence ladder request failed.");
    }
    const ladder = payload.ladder;
    const cards = h("div", { class: "evidence-ladder-grid" });
    const artifacts = {
      "E-16": BLOB + "benchmarks/incident_commander/public-live-incident-rehearsal-receipt.json",
      "E-07": BLOB + "benchmarks/incident_commander/public-datahub-live-writeback-receipt.json",
      "E-21": REPO + "/actions/workflows/hosted-continuity.yml",
    };
    list(ladder.layers).forEach((layer, index) => {
      const mutations = layer.externalMutations === true;
      const badge = mutations ? "BOUNDED LIVE MUTATION" : "NO EXTERNAL MUTATION";
      const facts = [];
      if (layer.providerActionCount) facts.push(layer.providerActionCount + " provider actions");
      if (layer.retrieved) facts.push("MCP read-back observed");
      if (layer.evidenceId === "E-21") facts.push("time-separated public samples");
      cards.append(h("article", {
        class: "evidence-rung " + (mutations ? "live" : "sample"),
      },
      h("div", { class: "evidence-rung-index", text: String(index + 1).padStart(2, "0") }),
      h("div", { class: "evidence-rung-body" },
        h("div", { class: "evidence-rung-head" },
          h("span", { text: badge }),
          h("a", {
            href: artifacts[layer.evidenceId] || EVIDENCE,
            target: "_blank",
            rel: "noopener",
            text: layer.evidenceId || "evidence",
          })),
        h("h3", { text: layer.label || "Evidence layer" }),
        facts.length ? h("p", { class: "evidence-rung-facts", text: facts.join(" · ") }) : null,
        h("p", {}, h("b", { text: "Proves: " }), layer.proves || ""),
        h("p", { class: "evidence-rung-limit" },
          h("b", { text: "Does not prove: " }), layer.doesNotProve || ""))));
    });
    const gap = ladder.openGap || {};
    const checks = ladder.crossReceiptChecks || {};
    return h("section", {
      class: "sec live-evidence-ladder",
      id: "live-evidence",
      "data-testid": "live-evidence-ladder",
    },
    h("p", { class: "sec-eyebrow", text: "LIVE EVIDENCE · NO COLLAPSING THE LAYERS" }),
    h("h2", { class: "sec-title", text: "A flight manifest for what actually touched a network" }),
    h("p", { class: "sec-note" },
      "Instead of calling one rehearsal “production,” this ladder binds each evidence class to ",
      h("b", { text: "exactly what happened" }),
      ": provider actions, DataHub write/read, or repeated public contract checks. The records share an incident identity, but the page refuses to pretend they were one process."),
    h("div", { class: "evidence-chain-meta" },
      h("div", {}, h("small", { text: "SHARED INCIDENT" }),
        h("code", { text: ladder.incidentId || "unavailable" })),
      h("div", {}, h("small", { text: "CHAIN DIGEST" }),
        h("code", { text: checks.evidenceChainDigest || "unavailable" })),
      h("div", {}, h("small", { text: "SAME PROCESS?" }),
        h("strong", { text: checks.integratedSameProcessRun ? "YES" : "NO — DISCLOSED" }))),
    cards,
    h("article", { class: "evidence-open-gap" },
      h("span", { text: gap.label || "Not yet proven" }),
      h("h3", { text: "The missing receipt is visible, not hand-waved away" }),
      h("p", { text: gap.nextSafeTest || "" }),
      h("ul", {},
        h("li", { text: "Integrated live DataHub read → provider act → write-back in one run: not proven" }),
        h("li", { text: "Sustained provider operation or production reliability: not proven" }),
        h("li", { text: "Incident recovery or independent validation: not proven" }))),
    h("p", { class: "sec-foot" },
      "E-21 samples the public fixture and policy labs repeatedly; it executes no provider tool. ",
      h("a", {
        href: REPO + "/actions/workflows/hosted-continuity.yml",
        target: "_blank",
        rel: "noopener",
        text: "Open the latest hosted continuity workflow",
      }),
      " · ",
      h("a", { href: EVIDENCE, target: "_blank", rel: "noopener", text: "Evidence index" }),
      "."));
  };

  const COMPARISON = [
    { s: "Late data table", d: "payments feed is behind schedule",
      af: "May send a fixed alert if someone wired a rule.",
      ag: "Invent a fix and approve itself", agRisk: "— risky at 2 a.m.",
      us: "Notify the real owner, open a tracked ticket.", usGate: "only the sealed plan runs." },
    { s: "Schema change", d: "a money column changes type",
      af: "Notify if a schema rule exists.",
      ag: "Maybe rewrite the column", agRisk: "— can break money math.",
      us: "Warn downstream teams; no silent rewrite.", usGate: "data edits are not on the allowlist." },
    { s: "Access too wide", d: "private customer data opened broadly",
      af: "Notify if a policy rule exists.",
      ag: "Maybe fix access itself", agRisk: "— security incident.",
      us: "Escalate to security; no self-edit of access.", usGate: "access changes refused by design." },
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
      h("p", { class: "sec-eyebrow", text: "SAME INCIDENT, THREE OUTCOMES" }),
      h("h2", { class: "sec-title", text: "Catalog rule vs self-approving AI vs LedgerLens" }),
      h("p", { class: "sec-note" },
        "Situation table (complement to ",
        h("a", { href: "#vs-plan-mode", text: "AI plan mode vs us" }),
        "). We win on ",
        h("b", { text: "bounded coordination" }),
        ", not on inventing root cause."),
      h("div", { class: "cmp-wrap" },
        h("table", { class: "cmp-table cmp3", "data-testid": "table-situations" },
          h("thead", {}, h("tr", {},
            h("th", { text: "Situation" }),
            h("th", { text: "Fixed catalog rule" }),
            h("th", { text: "AI plan mode that self-approves" }),
            h("th", { class: "us", text: "LedgerLens" }))),
          tbody)),
      h("p", { class: "sec-foot" },
        "One supervised live chain (GitHub ",
        h("a", { href: "https://github.com/tomyimkc/ledgerlens/issues/29", target: "_blank", rel: "noopener", text: "#29" }),
        ", Slack, PagerDuty, Jira) — ",
        h("a", { href: EVIDENCE, target: "_blank", rel: "noopener", text: "evidence E-16" }),
        ". Proves adapters + gate once; not sustained production or full recovery."));
  };

  const buildSetup = () => {
    const cards = [
      { n: "1", t: "Try the safe agent demo (this page)",
        code: [
          "git clone https://github.com/tomyimkc/ledgerlens.git",
          "cd ledgerlens && make setup && make incident-demo",
          "# fixture agent turn — no live tool side effects",
        ],
        note: "See the agent loop without charging an LLM or firing real tools." },
      { n: "2", t: "Enable AI-native planning (your model)",
        code: [
          "export LEDGERLENS_LLM_ENABLED=true",
          "export LEDGERLENS_LLM_API_KEY=…",
          "export LEDGERLENS_LLM_BASE_URL=…   # OpenAI-compatible",
          "export LEDGERLENS_LLM_MODEL=…",
        ],
        note: "Planner + optional verifiers become live. Gate stays non-model." },
      { n: "3", t: "Connect DataHub + your tools",
        code: [
          "export DATAHUB_GMS_URL=…  DATAHUB_TOKEN=…",
          "# allowlist only the tools/targets you trust",
          "# GitHub / Slack / PagerDuty / Jira tokens as needed",
          "# add your adapter under src/ledgerlens/actions/",
        ],
        note: "You integrate tools; the agent may only propose allowlisted ones." },
    ];
    const grid = h("div", { class: "setup-grid setup-grid-3" });
    for (const s of cards) {
      grid.append(h("article", { class: "setup-card" },
        h("div", { class: "setup-hd" }, h("span", { class: "setup-n", text: s.n }), h("h3", { text: s.t })),
        h("pre", { class: "code-block setup-code", text: s.code.join("\n") }),
        h("p", { class: "setup-note", text: s.note })));
    }
    return h("section", { class: "sec", id: "get-started" },
      h("p", { class: "sec-eyebrow", text: "TRY IT" }),
      h("h2", { class: "sec-title", text: "Fixture first — then AI + your tools" }),
      grid,
      h("p", { class: "sec-foot" },
        h("a", { href: REPO + "#readme", target: "_blank", rel: "noopener", text: "README" }),
        " · ",
        h("a", { href: "#tool-belt", text: "Tool belt" }),
        " · ",
        h("a", { href: EVIDENCE, target: "_blank", rel: "noopener", text: "Evidence" }),
        " · ",
        h("a", { href: BLOB + "ARCHITECTURE.md", target: "_blank", rel: "noopener", text: "Architecture" })));
  };

  const scrollToId = (id) => {
    if (!id) return false;
    const el = document.getElementById(id);
    if (!el) return false;
    const switcher = document.querySelector(".page-switcher");
    const header = document.querySelector(".command-header");
    const topbar = document.querySelector(".topbar");
    const offset =
      (switcher ? switcher.offsetHeight : 0) +
      (header ? header.offsetHeight : 0) +
      (topbar ? topbar.offsetHeight : 0) +
      12;
    const top = el.getBoundingClientRect().top + window.scrollY - offset;
    window.scrollTo({ top: Math.max(0, top), behavior: "smooth" });
    try { history.replaceState(null, "", "#" + id); } catch (_e) { /* ignore */ }
    return true;
  };

  const wireInPageNav = () => {
    document.querySelectorAll('a[href^="#"]').forEach((a) => {
      a.addEventListener("click", (ev) => {
        const href = a.getAttribute("href") || "";
        if (href.length < 2) return;
        const id = href.slice(1);
        if (scrollToId(id)) {
          ev.preventDefault();
        }
      });
    });
  };

  const decorateHero = () => {
    // Keep Restart visible and clickable (do not remove the button).
    if (replayBtn) {
      replayBtn.hidden = false;
      replayBtn.removeAttribute("disabled");
      replayBtn.style.display = "";
    }
    const heroCopy = root.querySelector(".flow-hero > div");
    if (heroCopy && !heroCopy.querySelector(".hero-sub")) {
      heroCopy.append(h("p", { class: "hero-sub", text:
        "An LLM proposes allowlisted tool calls. DataHub evidence determines which are eligible. A non-model gate seals the exact reviewed plan before any tool runs — then receipts return to DataHub." }));
    }
    const orient = root.querySelector(".orient");
    if (orient && !orient.querySelector(".toc-links")) {
      const home = (apiBase || "").replace(/\/api\/?$/, "") || "";
      orient.append(h("nav", { class: "toc-links", "aria-label": "On this page" },
        h("a", { href: "#unique", text: "What is unique?" }),
        h("a", { href: "#gate-demo", text: "Seal Lab" }),
        h("a", { href: "#context-cut", text: "Context Cut" }),
        h("a", { href: "#live-evidence", text: "Live Evidence" }),
        h("a", { class: "toc-page", href: home + "/agent-io", text: "Agent I/O →" }),
        h("a", { href: "#how-repo-works", text: "Agentic flow" }),
        h("a", { href: "#alternate-plan", text: "Revise plan" }),
        h("a", { href: "#get-started", text: "Try it" })));
    }
  };

  // Legacy command-surface handlers (authorize / execute / plan revise) when that
  // panel is visible (no-JS or manual mode). Harmless no-ops if nodes are absent.
  const toast = document.querySelector("[data-command-toast]");
  let toastTimer;
  const showToast = (message, isError) => {
    if (!toast) return;
    window.clearTimeout(toastTimer);
    toast.textContent = message;
    toast.classList.toggle("error", !!isError);
    toast.classList.add("visible");
    toastTimer = window.setTimeout(() => toast.classList.remove("visible"), 3200);
  };
  const command = async (path, payload, method) => {
    const response = await fetch(apiBase + path, {
      method: method || "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-Requested-With": "LedgerLens-Incident-Commander",
      },
      body: payload === undefined ? undefined : JSON.stringify(payload || {}),
    });
    const result = await response.json();
    if (!response.ok || !result.ok) {
      const failures = result.authorization && result.authorization.failures;
      const suffix = Array.isArray(failures) && failures.length ? " " + failures.join("; ") + "." : "";
      throw new Error((result.detail || "Command failed.") + suffix);
    }
    return result;
  };
  document.querySelectorAll("[data-copy]").forEach((button) => {
    button.addEventListener("click", async () => {
      const value = button.getAttribute("data-copy");
      if (!value || !navigator.clipboard) return;
      try {
        await navigator.clipboard.writeText(value);
        showToast("Plan fingerprint copied.");
      } catch (_e) {
        showToast("Could not copy.", true);
      }
    });
  });
  const wireTrigger = (el) => {
    el && el.addEventListener("click", async () => {
      try {
        await command("/trigger", { source: body.dataset.mode });
        showToast("Incident trigger accepted. Authorization was reset.");
        window.location.reload();
      } catch (error) {
        showToast(error.message, true);
      }
    });
  };
  wireTrigger(document.querySelector("[data-trigger-incident]"));
  wireTrigger(document.querySelector("[data-legacy-trigger]"));
  const authorizationForm = document.querySelector("[data-authorization-form]");
  authorizationForm && authorizationForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(authorizationForm);
    const feedback = document.querySelector("[data-gate-feedback]");
    try {
      await command("/authorize", {
        actor: form.get("actor"),
        confirmation: form.get("confirmation"),
        plan_hash: form.get("plan_hash"),
        acknowledge_claim_boundary: form.get("acknowledge_claim_boundary") === "on",
      });
      showToast("Authorization grant recorded for the exact plan.");
      window.location.reload();
    } catch (error) {
      if (feedback) feedback.textContent = error.message;
      showToast("Authorization denied.", true);
    }
  });
  const executeBtn = document.querySelector("[data-execute-fanout]");
  executeBtn && executeBtn.addEventListener("click", async () => {
    try {
      await command("/execute");
      showToast("Fanout completed.");
      window.location.reload();
    } catch (error) {
      showToast(error.message, true);
    }
  });
  document.querySelectorAll("[data-plan-template]").forEach((button) => {
    button.addEventListener("click", async () => {
      const templateId = button.getAttribute("data-plan-template");
      const feedback = document.querySelector("[data-plan-revise-feedback]");
      try {
        const result = await command("/plan/revise", { template_id: templateId });
        if (feedback) {
          feedback.textContent =
            "Plan revised. New fingerprint: " +
            (result.plan_hash || "") +
            ". Prior grant wiped — re-authorize the exact new plan.";
        }
        showToast("Alternate plan sealed. Re-authorize before execute.");
        window.location.reload();
      } catch (error) {
        if (feedback) feedback.textContent = error.message;
        showToast(error.message, true);
      }
    });
  });

  const start = async () => {
    body.classList.add("js");
    decorateHero();
    if (timelineEl) timelineEl.replaceChildren();
    if (hintEl) hintEl.replaceChildren();
    const sticky = pipeEl.closest(".pipe-sticky");
    if (sticky) sticky.remove();
    if (proofsEl) proofsEl.remove();
    detailEl.replaceChildren(
      h("div", { class: "logloading" },
        h("span", { class: "sv-spinner", "aria-hidden": "true" }), GATE));
    let proof = null;
    let contextCut = null;
    let liveEvidence = null;
    try {
      proof = await buildProofSection();
    } catch (_e) {
      proof = null;
    }
    try {
      contextCut = await buildContextCutLab();
    } catch (_e) {
      contextCut = null;
    }
    try {
      liveEvidence = await buildLiveEvidenceLadder();
    } catch (_e) {
      liveEvidence = null;
    }
    detailEl.replaceChildren(
      buildWhat(),
      buildAiSplit(),
      buildUnique(),
      ...(proof ? [proof] : []),
      ...(contextCut ? [contextCut] : []),
      ...(liveEvidence ? [liveEvidence] : []),
      buildVsPlanMode(),
      buildRepoHow(),
      buildToolBelt(),
      buildAlternatePlan(),
      buildRealCode(),
      buildMcpIo(),
      buildPipe(),
      buildCode(),
      buildComparison(),
      buildSetup());
    wireInPageNav();
    // Honor deep links after content is mounted.
    if (location.hash && location.hash.length > 1) {
      setTimeout(() => scrollToId(location.hash.slice(1)), 50);
    }
  };

  start().catch((err) => {
    console.error("LedgerLens demo failed to start", err);
    body.classList.add("js");
    detailEl.replaceChildren(
      h("section", { class: "sec" },
        h("h2", { class: "sec-title", text: "Demo UI failed to load" }),
        h("p", { class: "sec-note", text: String(err && err.message ? err.message : err) }),
        h("p", { class: "sec-note" },
          "You can still open the source: ",
          h("a", { href: REPO, target: "_blank", rel: "noopener", text: REPO }))));
  });
})();
