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
      h("h2", { class: "sec-title", text: "When company data looks wrong, LedgerLens helps the right people act — safely" }),
      h("p", { class: "sec-note" },
        "Think of ", h("b", { text: "DataHub" }),
        " as the company map of its data: who owns a table, what depends on it, and when quality checks fail. ",
        "LedgerLens is a helper that ", h("b", { text: "reads that map" }),
        ", suggests a short to-do list (page the owner, open a ticket, warn Slack), ",
        h("b", { text: "checks that list against hard safety rules" }),
        ", then only does what was approved — and writes a paper trail back into DataHub."),
      h("p", { class: "sec-note" },
        "It is ", h("b", { text: "not a chatbot you chat with" }),
        ", and ", h("b", { text: "not a plug-in that replaces DataHub" }),
        ". It is software you run next to DataHub, using DataHub official tools."),
      h("div", { class: "sysmap", "data-testid": "system-map" },
        box("Your DataHub", "who owns what · what depends on what"),
        arrow("reads the map", "official DataHub tools"),
        box("LedgerLens", "suggest \u2192 check \u2192 act", "us"),
        arrow("only allowed tools", "ticket · chat · page"),
        box("Your team tools", "GitHub · Slack · PagerDuty · Jira")),
      h("p", { class: "syswrite" },
        "\u21a9 After acting, it files a short report back into DataHub so the next person (or helper) can pick up where it left off."));
  };

  const buildAiSplit = () => {
    const uses = h("article", { class: "ai-card uses" },
      h("h3", { text: "Uses an LLM (the drafting brain)" }),
      h("ul", {},
        h("li", { text: "Suggests a short list of safe, reversible steps (open an issue, notify Slack, page on-call)." }),
        h("li", { text: "A second model pass can review that list — still only advice." }),
        h("li", { text: "You bring your own model (any OpenAI-compatible endpoint). On this public demo page, the fixture shows the same structure with fixed example data." })));
    const noAi = h("article", { class: "ai-card no-ai" },
      h("h3", { text: "Does NOT use an LLM (the safety lock)" }),
      h("ul", {},
        h("li", { text: "Reading who owns the data and what sits downstream comes from DataHub, not from the model inventing owners." }),
        h("li", { text: "The final yes/no to run actions is ordinary Python policy: allowlists, reversible actions only, and a fingerprint of the exact reviewed plan." }),
        h("li", { text: "If someone changes the plan after review (even by one Slack post), the lock refuses. The model cannot override that." })));
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

  const buildUnique = () =>
    h("section", { class: "sec", id: "unique", "data-testid": "what-is-unique" },
      h("p", { class: "sec-eyebrow", text: "WHAT MAKES THIS DIFFERENT" }),
      h("h2", { class: "sec-title", text: "Plan-exact authorization — the reviewed plan is the only plan that can run" }),
      h("div", { class: "unique-grid" },
        h("article", { class: "unique-card" },
          h("h3", { text: "Most AI agents" }),
          h("p", { text: "The model writes a plan, then the same model (or a soft score) decides it is fine to run. If the plan quietly changes later, nothing stops it." })),
        h("article", { class: "unique-card us" },
          h("h3", { text: "This repo" }),
          h("p", { text: "After review, the plan gets a unique fingerprint (like a seal on a letter). The lock only opens for that exact seal. Add one extra action after the seal? Denied. Same DataHub facts, different plan — still denied." }))),
      h("p", { class: "sec-note" },
        "Also unique in practice: it is built around ",
        h("b", { text: "DataHub as the source of truth" }),
        " (owners, lineage, quality alerts), not a free-floating chat session; every tool call can leave a ",
        h("b", { text: "receipt" }),
        "; and unknowns like root cause stay marked unknown unless proven. We do not claim to be the only possible design — we claim this split is clear, testable, and already implemented in open source."),
      h("p", { class: "sec-foot" },
        "Live proof below: the same gate code refuses a plan that drifted after review. ",
        "If you disagree with the AI draft, you are not stuck — pick an alternate plan (next section) and re-seal under the same lock."));

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
            '    """Launch the Autonomous Data Incident Commander."""',
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

  const REPO_STEPS = [
    { n: "1", title: "Something looks wrong in the data", file: "src/ledgerlens/orchestrator.py", fileLabel: "orchestrator.py",
      why: "A quality check fails — for example a daily payments table is late.",
      does: "LedgerLens opens an incident file: what broke, how bad, which dataset.",
      ai: "No LLM here.", io: "Starts from an alert / trigger about one dataset." },
    { n: "2", title: "Look up the map in DataHub", file: "src/ledgerlens/datahub_context.py", fileLabel: "datahub_context.py",
      why: "You need the real owner and what might break next — not a guess.",
      does: "Asks DataHub: who owns this? how important is it? what depends on it? Is there a runbook?",
      ai: "No LLM. Catalog facts only.", io: "Reads DataHub (entities + lineage). Notes what is still unknown." },
    { n: "3", title: "Draft a short to-do list", file: "src/ledgerlens/orchestrator.py", fileLabel: "planner (in orchestrator)",
      why: "Humans need a concrete next step, not a novel.",
      does: "An LLM may suggest only allowed, undo-friendly actions (ticket, chat, page). It fingerprints that exact list.",
      ai: "Yes — LLM drafts the plan.", io: "Out: plan + fingerprint (the seal)." },
    { n: "4", title: "Optional second opinion from AI", file: "src/ledgerlens/verification.py", fileLabel: "verification.py",
      why: "A second look can catch a bad suggestion — still not a green light.",
      does: "Verifier models vote approve/reject. Their vote is advice only.",
      ai: "Yes — LLM advice only. Cannot unlock actions.", io: "Out: advisory votes + confidence." },
    { n: "5", title: "Safety lock: may this exact plan run?", file: "src/ledgerlens/verification.py", fileLabel: "policy gate (Python)",
      why: "This is where most chatbot agents stop being safe enough for production.",
      does: "Ordinary Python checks: grounded in DataHub, only allowlisted tools, reversible, seal still matches. Fail closed.",
      ai: "No LLM. Deterministic policy.", io: "Out: AUTHORIZED or DENIED + reasons." },
    { n: "6", title: "Do the approved work only", file: "src/ledgerlens/actions/", fileLabel: "actions/*",
      why: "Teams need a ticket or a page — with a receipt.",
      does: "Runs only the approved tools (GitHub, Slack, PagerDuty, Jira). Nothing else.",
      ai: "No LLM deciding new targets.", io: "Out: receipts (on this public page: safe fixture examples)." },
    { n: "7", title: "File a report back in DataHub", file: "src/ledgerlens/datahub_writeback.py", fileLabel: "datahub_writeback.py",
      why: "The next person should not start from zero.",
      does: "Writes one allowlisted document into DataHub (the incident receipt) and can read it back.",
      ai: "No LLM inventing the receipt.", io: "Out: document id in DataHub for the next agent." },
    { n: "8", title: "Hand off cleanly", file: "src/ledgerlens/orchestrator.py", fileLabel: "memory / handoff",
      why: "Honest systems admit what they do not know.",
      does: "Packages known facts, unknowns (cause, impact, recovery unless proven), and what to check next.",
      ai: "No LLM rewriting history.", io: "Out: handoff package for the next operator or agent." },
  ];

  const buildRepoHow = () => {
    const list = h("div", { class: "repo-steps", "data-testid": "repo-how-it-works" });
    for (const s of REPO_STEPS) {
      const bodyEl = h("div", { class: "repo-step-body" },
        h("p", { class: "repo-why" }, h("b", { text: "Why — " }), s.why),
        h("p", { class: "repo-does" }, h("b", { text: "What happens — " }), s.does),
        h("p", { class: "repo-ai" },
          h("b", { text: "LLM here? " }),
          h("span", { class: s.ai.startsWith("Yes") ? "ai-yes" : "ai-no", text: s.ai })),
        h("pre", { class: "code-block repo-io", text: s.io }),
        h("p", { class: "repo-file" }, "In the code: ", fileLink(s.file, s.fileLabel)));
      const head = h("button", { type: "button", class: "repo-step-hd", "aria-expanded": "true" },
        h("span", { class: "repo-n", text: s.n }),
        h("span", { class: "repo-title", text: s.title }),
        h("span", { class: "repo-chev", "aria-hidden": "true", text: "\u25be" }));
      head.addEventListener("click", () => {
        const open = head.getAttribute("aria-expanded") === "true";
        head.setAttribute("aria-expanded", open ? "false" : "true");
        bodyEl.hidden = open;
        head.querySelector(".repo-chev").textContent = open ? "\u25b8" : "\u25be";
      });
      list.append(h("article", { class: "repo-step", "data-step": s.n }, head, bodyEl));
    }
    return h("section", { class: "sec", id: "how-repo-works" },
      h("p", { class: "sec-eyebrow", text: "HOW IT WORKS — STEP BY STEP" }),
      h("h2", { class: "sec-title", text: "Eight steps from data looks wrong to work is done and logged" }),
      h("p", { class: "sec-note" },
        "Tap a step to expand. Each one says whether an LLM is involved, in plain words, and links to the real file for technical readers. ",
        "If the draft in step 3 is wrong, jump to ",
        h("a", { href: "#alternate-plan", text: "Disagree with AI?" }),
        " — swap the plan and re-seal under the same lock."),
      list);
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
    ["1", "Alert", "data looks wrong"],
    ["2", "DataHub", "read the map"],
    ["3", "Draft", "AI suggests steps"],
    ["4", "Review", "AI advice only"],
    ["5", "Lock", "Python says go/no-go"],
    ["6", "Act", "tickets · chat · page"],
    ["7", "Receipt", "back into DataHub"],
    ["8", "Handoff", "next person"],
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
      h("p", { class: "sec-eyebrow", text: "THE FULL PATH" }),
      h("h2", { class: "sec-title", text: "Alert → map → draft → lock → act → receipt" }),
      h("div", { class: "pipe-wrap" }, pipe),
      h("p", { class: "sec-foot" },
        "Steps 3–4 can use an LLM. The ", h("b", { text: "Lock" }),
        " step is plain Python and has the final say."));
  };

  const TERMINAL = [
    { cmd: "make incident-demo", href: BLOB + "Makefile" },
    { cmd: "# → uv run bash scripts/demo_incident_commander.sh", href: BLOB + "scripts/demo_incident_commander.sh" },
    { cmd: "# → ledgerlens incident-commander --fixture", href: BLOB + "src/ledgerlens/cli.py#L406" },
    { tag: "alert", msg: "payments table late (23 min > 15 min limit)" },
    { tag: "DataHub", msg: "looked up owner + what depends on it", ok: "owner found · 3 downstream", href: BLOB + "src/ledgerlens/datahub_context.py" },
    { tag: "LLM draft", msg: "suggested safe steps", ok: "sealed plan_fingerprint", href: BLOB + "src/ledgerlens/incident_dashboard.py#L339" },
    { tag: "LLM review", msg: "second opinion: looks ok", ok: "advice only", href: BLOB + "src/ledgerlens/verification.py" },
    { tag: "Python lock", msg: "evaluate_authorization · allowlist · seal", ok: "AUTHORIZED", href: BLOB + "src/ledgerlens/incident_dashboard.py#L1064" },
    { tag: "tools", msg: "ticket · Slack · page · Jira", ok: "receipts recorded", href: BLOB + "src/ledgerlens/actions/" },
    { tag: "DataHub", msg: "filed incident receipt", ok: "next person can continue", href: BLOB + "src/ledgerlens/datahub_writeback.py" },
    { done: "finished · no root-cause or recovery claim · fixture data only" },
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
    NODES.forEach(([, label], i) => {
      const cls = i === 4 ? " active" : (i < 4 ? " done" : "");
      strip.append(h("div", { class: "gw-node" + cls },
        h("span", { class: "gw-n", text: String(i + 1) }),
        h("span", { class: "gw-label", text: label })));
      if (i < NODES.length - 1) {
        strip.append(h("span", { class: "gw-arrow", "aria-hidden": "true", text: "\u2192" }));
      }
    });
    return h("div", { class: "gate-where" },
      strip,
      h("p", { class: "gate-where-cap" },
        h("b", { text: "When this runs — " }),
        "after the draft and optional AI review, ",
        h("b", { text: "before" }),
        " any ticket or page goes out. Implemented as ordinary Python in ",
        fileLink("src/ledgerlens/verification.py", "verification.py"), "."));
  };

  const buildProofSection = async () => {
    try {
      const g = await fetch(apiBase + "/gate-demo", { credentials: "same-origin" }).then((r) => r.json());
      if (g && g.demo) {
        return h("section", { class: "sec", id: "gate-demo", "data-testid": "gate-demo" },
          h("p", { class: "sec-eyebrow", text: "LIVE PROOF" }),
          h("h2", { class: "sec-title", text: "If the plan changes after review, nothing runs" }),
          gateWhere(),
          gateCard(g.demo));
      }
    } catch (_e) { /* best-effort */ }
    return null;
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
      h("p", { class: "sec-eyebrow", text: "WHY NOT JUST USE CHATGPT" }),
      h("h2", { class: "sec-title", text: "Same problem, three different outcomes" }),
      h("div", { class: "cmp-wrap" },
        h("table", { class: "cmp-table cmp3" },
          h("thead", {}, h("tr", {},
            h("th", { text: "Situation" }),
            h("th", { text: "Fixed catalog rule" }),
            h("th", { text: "Chat-style AI that self-approves" }),
            h("th", { class: "us", text: "LedgerLens" }))),
          tbody)),
      h("p", { class: "sec-foot" },
        "We once ran a carefully limited live rehearsal (GitHub ",
        h("a", { href: "https://github.com/tomyimkc/ledgerlens/issues/29", target: "_blank", rel: "noopener", text: "#29" }),
        ", Slack, PagerDuty, Jira) — ",
        h("a", { href: EVIDENCE, target: "_blank", rel: "noopener", text: "evidence E-16" }),
        ". That shows adapters work; it does not mean every incident is solved."));
  };

  const buildSetup = () => {
    const cards = [
      { n: "1", t: "Try the safe demo (this page)",
        code: [
          "git clone https://github.com/tomyimkc/ledgerlens.git",
          "cd ledgerlens && make setup && make incident-demo",
          "# opens a local copy of this walkthrough",
        ],
        note: "No real tickets, no real pages, no paid model required for the fixture path." },
      { n: "2", t: "Connect your own DataHub later",
        code: [
          "export DATAHUB_GMS_URL=…   # your catalog",
          "export DATAHUB_TOKEN=…",
          "# plus only the tools you allow (GitHub, Slack, …)",
          "# plus your LLM key if you want live drafting",
        ],
        note: "You choose the allowlist. The safety lock still has the final yes/no." },
    ];
    const grid = h("div", { class: "setup-grid" });
    for (const s of cards) {
      grid.append(h("article", { class: "setup-card" },
        h("div", { class: "setup-hd" }, h("span", { class: "setup-n", text: s.n }), h("h3", { text: s.t })),
        h("pre", { class: "code-block setup-code", text: s.code.join("\n") }),
        h("p", { class: "setup-note", text: s.note })));
    }
    return h("section", { class: "sec", id: "get-started" },
      h("p", { class: "sec-eyebrow", text: "TRY IT" }),
      h("h2", { class: "sec-title", text: "Start safe, connect later" }),
      grid,
      h("p", { class: "sec-foot" },
        h("a", { href: REPO + "#readme", target: "_blank", rel: "noopener", text: "README" }),
        " · ",
        h("a", { href: EVIDENCE, target: "_blank", rel: "noopener", text: "Evidence" }),
        " · ",
        h("a", { href: BLOB + "ARCHITECTURE.md", target: "_blank", rel: "noopener", text: "Architecture (technical)" })));
  };

  const scrollToId = (id) => {
    if (!id) return false;
    const el = document.getElementById(id);
    if (!el) return false;
    const header = document.querySelector(".command-header");
    const topbar = document.querySelector(".topbar");
    const offset = (header ? header.offsetHeight : 0) + (topbar ? topbar.offsetHeight : 0) + 12;
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
        "Plain English: DataHub is the company data map. LedgerLens reads that map, may use AI to draft a short to-do list, then uses hard rules (not the AI) to decide what may run — and leaves a receipt." }));
    }
    const orient = root.querySelector(".orient");
    if (orient && !orient.querySelector(".toc-links")) {
      orient.append(h("nav", { class: "toc-links", "aria-label": "On this page" },
        h("a", { href: "#ai-or-not", text: "Does it use AI?" }),
        h("a", { href: "#unique", text: "What is unique?" }),
        h("a", { href: "#alternate-plan", text: "Disagree with AI?" }),
        h("a", { href: "#how-repo-works", text: "Step by step" }),
        h("a", { href: "#real-code", text: "Real code" }),
        h("a", { href: "#gate-demo", text: "Live proof" }),
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
    try {
      proof = await buildProofSection();
    } catch (_e) {
      proof = null;
    }
    detailEl.replaceChildren(
      buildWhat(),
      buildAiSplit(),
      buildUnique(),
      buildAlternatePlan(),
      buildRepoHow(),
      buildRealCode(),
      buildMcpIo(),
      buildPipe(),
      buildCode(),
      ...(proof ? [proof] : []),
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
