(() => {
  "use strict";

  // Guided, animated Incident Commander flow. The server still renders the full
  // panels (see `.legacy-content`) as a no-JS fallback and for honest labels;
  // this script layers an interactive one-stage-at-a-time replay on top. It only
  // hides the fallback once the executed fixture state has loaded successfully.
  //
  // Authorization is decided by deterministic policy: "Evaluating deterministic
  // gate" is shown while the executed state is fetched — AI cannot open the gate.

  const body = document.body;
  const apiBase = body.dataset.apiBase;
  const root = document.querySelector("[data-flow-root]");
  const rail = document.querySelector("[data-flow-rail]");
  const view = document.querySelector("[data-flow-view]");
  const replayBtn = document.querySelector("[data-flow-replay]");
  const GATE_EVALUATING = "Evaluating deterministic gate…";
  const AUTO_MS = 1650;

  if (!root || !rail || !view) return; // keep the server fallback if scaffold is missing

  // ---- tiny DOM helper -----------------------------------------------------
  const h = (tag, attrs, ...kids) => {
    const node = document.createElement(tag);
    if (attrs) {
      for (const [key, value] of Object.entries(attrs)) {
        if (value == null) continue;
        if (key === "class") node.className = value;
        else if (key === "text") node.textContent = value;
        else node.setAttribute(key, value);
      }
    }
    for (const kid of kids) {
      if (kid == null) continue;
      node.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
    }
    return node;
  };
  const arr = (value) => (Array.isArray(value) ? value : []);
  const obj = (value) => (value && typeof value === "object" ? value : {});

  const head = (num, eyebrow, title, right) =>
    h("header", { class: "sv-head" },
      h("div", null,
        h("p", { class: "sv-eyebrow" }, h("b", { text: num }), " · " + eyebrow),
        h("h2", { text: title })),
      right || null);

  const receipt = (value) =>
    value
      ? h("code", { class: "sv-receipt" }, value)
      : h("span", { class: "sv-pending", text: "pending authorization" });

  const kv = (pairs) => {
    const dl = h("dl", { class: "sv-kv" });
    for (const [k, v] of pairs) {
      if (v == null || v === "") continue;
      dl.append(h("div", null, h("dt", { text: k }), h("dd", { text: String(v) })));
    }
    return dl;
  };

  const listOf = (items, ordered, cls) => {
    const list = h(ordered ? "ol" : "ul", { class: cls || "sv-list" });
    for (const item of arr(items)) list.append(h("li", { text: String(item) }));
    return list;
  };

  const note = (label, text) =>
    h("p", { class: "sv-note" }, h("b", { text: label + " " }), text);

  // ---- per-stage renderers -------------------------------------------------
  const renderTrigger = (s) => {
    const inc = obj(s.incident);
    const t = obj(inc.trigger);
    const card = h("section", null,
      head("01", "INCIDENT TRIGGER", inc.title || "Incident",
        h("span", { class: "sv-tag sev", text: inc.severity || "SEV" })));
    card.append(h("div", { class: "sv-chips" },
      h("span", { class: "sv-tag", text: (inc.status || "").replace(/_/g, " ") }),
      h("span", { class: "sv-tag ghost", text: inc.service || "" }),
      h("span", { class: "sv-tag ghost", text: "detected " + (inc.detected_at || "") })));
    card.append(h("div", { class: "sv-signal" },
      h("p", { class: "sv-lede", text: t.summary || "" }),
      h("div", { class: "sv-metrics" },
        h("div", null, h("strong", { text: t.observed || "?" }), h("span", { text: "observed" })),
        h("div", { class: "vs", text: "vs" }),
        h("div", null, h("strong", { text: t.threshold || "?" }), h("span", { text: "SLO threshold" })))));
    card.append(kv([["Source", t.source], ["Signal", t.signal], ["Classification", t.classification]]));
    card.append(note("This is a source assertion —", "it is not proof of cause, impact, or recovery."));
    return card;
  };

  const renderContext = (s) => {
    const c = obj(s.context), e = obj(c.entity), b = obj(c.blast_radius);
    const card = h("section", { "data-testid": "datahub-context" },
      head("02", "DATAHUB CONTEXT", "Grounded entity & blast radius",
        h("span", { class: "sv-tag ok", text: c.status || "grounded" })));
    card.append(h("div", { class: "sv-entity" },
      h("span", { class: "sv-mark", text: "DH" }),
      h("div", null,
        h("small", { text: "PRIMARY ENTITY" }),
        h("strong", { text: e.name || "" }),
        h("code", { class: "sv-urn", text: e.urn || "" })),
      kv([["Owner", e.owner], ["Domain", e.domain], ["Tier", e.tier], ["Platform", e.platform]])));
    card.append(h("div", { class: "sv-blast" },
      h("div", { class: "sv-num" }, h("strong", { text: String(b.asset_count ?? "–") }), h("span", { text: "downstream assets" })),
      h("div", { class: "sv-num crit" }, h("strong", { text: String(b.critical_count ?? "–") }), h("span", { text: "Tier 1 dependencies" })),
      h("div", { class: "sv-num" }, h("strong", { text: (b.authorization_boundary || "bounded") }), h("span", { text: "authorization boundary" }))));
    const table = h("div", { class: "sv-table" });
    table.append(h("div", { class: "sv-tr sv-th" },
      h("span", { text: "Asset" }), h("span", { text: "Type" }),
      h("span", { text: "Criticality" }), h("span", { text: "Relationship" })));
    for (const a of arr(b.assets)) {
      table.append(h("div", { class: "sv-tr" },
        h("strong", { text: a.name || "" }), h("span", { text: a.type || "" }),
        h("span", { class: "sv-tier", text: a.criticality || "" }), h("span", { text: a.relationship || "" })));
    }
    card.append(table);
    const ev = h("div", { class: "sv-evidence" }, h("small", { text: "RECORDED EVIDENCE (DataHub metadata)" }));
    for (const item of arr(c.evidence)) {
      ev.append(h("div", { class: "sv-ev" }, h("span", { text: item.label || "" }), receipt(item.receipt)));
    }
    card.append(ev);
    card.append(h("div", { class: "sv-unknown" }, h("b", { text: "Unknowns stay unknown. " }),
      arr(b.unknowns).join(" ")));
    return card;
  };

  const renderPlan = (s) => {
    const p = obj(s.planner);
    const card = h("section", { "data-testid": "planner-output" },
      head("03", "PLAN", "Bounded response plan",
        h("div", { class: "sv-fp" }, h("small", { text: "PLAN FINGERPRINT" }),
          h("code", { text: p.computed_plan_hash || p.plan_hash || "" }))));
    card.append(h("div", { class: "sv-plan-obj" },
      h("strong", { text: p.objective || "" }), h("span", { text: p.scope || "" })));
    const ol = h("ol", { class: "sv-steps" });
    for (const step of arr(p.steps)) {
      ol.append(h("li", null,
        h("span", { class: "sv-order", text: String(step.order).padStart(2, "0") }),
        h("div", null,
          h("div", { class: "sv-step-top" }, h("strong", { text: step.title || "" }),
            step.reversible ? h("span", { class: "sv-rev", text: "reversible" }) : null),
          h("p", { text: step.reason || "" }),
          h("div", { class: "sv-step-meta" }, h("code", { text: step.action || "" }), h("span", { text: "→ " + (step.target || "") })))));
    }
    card.append(ol);
    card.append(h("div", { class: "sv-risk" }, h("b", { text: "Execution boundary. " }), p.risk || ""));
    return card;
  };

  const renderVerify = (s) => {
    const v = obj(s.verifier);
    const card = h("section", { "data-testid": "ai-verifier" },
      head("04", "AI VERIFIER — ADVISORY ONLY", "Independent model review",
        h("span", { class: "sv-tag ok", text: v.verdict || "" })));
    card.append(h("div", { class: "sv-advisory" }, h("span", { class: "sv-ai", text: "AI" }),
      h("p", null, h("strong", { text: (v.label || "AI verifier — advisory only") + " " }), v.authority_note || "")));
    card.append(h("p", { class: "sv-lede", text: v.summary || "" }));
    const ul = h("ul", { class: "sv-checks" });
    for (const check of arr(v.policy_checks)) {
      ul.append(h("li", { class: "ok" }, h("span", { class: "sv-ck", text: "✓" }),
        h("div", null, h("strong", { text: check.name || "" }), h("p", { text: check.detail || "" }))));
    }
    card.append(ul);
    return card;
  };

  const renderAuth = (s) => {
    const a = obj(s.authorization);
    const authorized = a.decision === "authorized";
    const card = h("section", { "data-testid": "authorization-gate" },
      head("05", "DETERMINISTIC GATE", "Authorization",
        h("span", { class: "sv-tag " + (authorized ? "ok" : "hold"), text: a.decision || "pending" })));
    card.append(h("p", { class: "sv-gate-line" },
      h("b", { text: "AI cannot open this gate." }),
      " Authority is " + (a.authority || "deterministic-policy") + "; ai_can_authorize is false."));
    const ul = h("ul", { class: "sv-checks" });
    for (const cond of arr(a.conditions)) {
      const st = cond.status === "pass" ? "ok" : cond.status === "fail" ? "bad" : "hold";
      ul.append(h("li", { class: st },
        h("span", { class: "sv-ck", text: cond.status === "pass" ? "✓" : cond.status === "fail" ? "×" : "·" }),
        h("div", null, h("strong", { text: cond.name || "" }), h("p", { text: cond.detail || "" }))));
    }
    card.append(ul);
    if (authorized) {
      card.append(h("div", { class: "sv-grant" },
        h("small", { text: "AUTHORIZATION RECEIPT" }),
        h("strong", { text: a.grant_id || "" }),
        h("span", { text: (a.actor || "") + " · " + (a.authorized_at || "") }),
        h("code", { text: a.plan_hash || "" })));
    }
    return card;
  };

  const renderAct = (s) => {
    const actions = arr(s.actions);
    const done = actions.filter((x) => x.status === "succeeded").length;
    const card = h("section", { "data-testid": "action-fanout" },
      head("06", "ACTION FANOUT", "One authorized run · four provider receipts",
        h("span", { class: "sv-tag ok", text: done + " / " + actions.length + " receipted" })));
    const grid = h("div", { class: "sv-providers" });
    for (const action of actions) {
      grid.append(h("article", { class: "sv-provider " + (action.status === "succeeded" ? "ok" : "hold") },
        h("div", { class: "sv-provider-top" },
          h("span", { class: "sv-logo", text: action.short || "" }),
          h("span", { class: "sv-tag " + (action.status === "succeeded" ? "ok" : "hold"), text: action.status || "" })),
        h("h3", { text: action.provider || "" }),
        h("strong", { text: action.operation || "" }),
        h("span", { class: "sv-target", text: action.target || "" }),
        receipt(action.receipt)));
    }
    card.append(grid);
    return card;
  };

  const renderWriteback = (s) => {
    const w = obj(s.writeback);
    const card = h("section", { "data-testid": "datahub-writeback" },
      head("07", "DATAHUB WRITE-BACK", "Incident receipt persisted to DataHub",
        h("span", { class: "sv-tag " + (w.status === "recorded" ? "ok" : "hold"), text: w.status || "" })));
    card.append(h("div", { class: "sv-entity" },
      h("span", { class: "sv-mark", text: "DH" }),
      h("div", null,
        h("small", { text: "ENTITY" }), h("strong", { text: w.entity || "" }),
        h("p", { text: w.detail || "" }), receipt(w.receipt)),
      kv([["Operation", w.operation], ["Aspect", w.aspect], ["Recorded", w.recorded_at]])));
    return card;
  };

  const renderMemory = (s) => {
    const m = obj(s.memory);
    const card = h("section", { "data-testid": "agent-memory" },
      head("08", "NEXT-AGENT HANDOFF", "What the next agent receives",
        h("span", { class: "sv-tag " + (m.status === "ready" ? "ok" : "hold"), text: m.status || "" })));
    card.append(h("div", { class: "sv-memory-top" },
      h("div", null, h("small", { text: "NEXT AGENT" }), h("strong", { text: m.next_agent || "" })),
      h("p", { text: m.summary || "" })));
    card.append(h("div", { class: "sv-memory-cols" },
      h("section", null, h("h3", { text: "Known facts" }), listOf(m.known_facts)),
      h("section", null, h("h3", { text: "Still unknown" }), listOf(m.unknowns)),
      h("section", null, h("h3", { text: "Completed" }), listOf(m.completed)),
      h("section", null, h("h3", { text: "Next safe actions" }), listOf(m.next_actions, true))));
    if (m.memory_id) {
      card.append(h("div", { class: "sv-grant" }, h("small", { text: "MEMORY RECEIPT" }), h("code", { text: m.memory_id })));
    }
    return card;
  };

  const STAGES = [
    { n: "01", label: "Trigger", sub: "DataHub assertion", render: renderTrigger },
    { n: "02", label: "Context", sub: "owner · lineage", render: renderContext },
    { n: "03", label: "Plan", sub: "bounded · fingerprinted", render: renderPlan },
    { n: "04", label: "Verify", sub: "AI advisory", render: renderVerify },
    { n: "05", label: "Authorize", sub: "deterministic gate", render: renderAuth },
    { n: "06", label: "Act", sub: "4 receipts", render: renderAct },
    { n: "07", label: "Write-back", sub: "to DataHub", render: renderWriteback },
    { n: "08", label: "Handoff", sub: "next agent", render: renderMemory },
  ];

  let state = null;
  let idx = 0;
  let autoTimer = null;

  const stopAuto = () => {
    if (autoTimer) { clearTimeout(autoTimer); autoTimer = null; }
    root.classList.remove("playing");
  };

  const buildRail = () => {
    rail.replaceChildren();
    STAGES.forEach((stage, i) => {
      const node = h("button", { class: "rail-node", type: "button", "aria-label": stage.label },
        h("span", { class: "rail-num", text: stage.n }),
        h("span", { class: "rail-label", text: stage.label }),
        h("span", { class: "rail-sub", text: stage.sub }));
      node.addEventListener("click", () => { stopAuto(); show(i); });
      rail.append(node);
      if (i < STAGES.length - 1) rail.append(h("span", { class: "rail-link" }));
    });
  };

  const paintRail = () => {
    const nodes = rail.querySelectorAll(".rail-node");
    nodes.forEach((node, i) => {
      node.classList.toggle("active", i === idx);
      node.classList.toggle("done", i < idx);
    });
    rail.querySelectorAll(".rail-link").forEach((link, i) => link.classList.toggle("filled", i < idx));
  };

  const show = (i) => {
    if (!state) return;
    idx = Math.max(0, Math.min(STAGES.length - 1, i));
    paintRail();
    const card = STAGES[idx].render(state);
    card.classList.add("sv-card");
    view.replaceChildren(card);
    requestAnimationFrame(() => card.classList.add("in"));
  };

  const autoStep = () => {
    if (idx < STAGES.length - 1) {
      autoTimer = setTimeout(() => { show(idx + 1); autoStep(); }, AUTO_MS);
    } else {
      stopAuto();
    }
  };

  const replay = async () => {
    stopAuto();
    if (replayBtn) replayBtn.disabled = true;
    body.classList.add("js");
    view.replaceChildren(h("div", { class: "sv-loading" },
      h("span", { class: "sv-spinner", "aria-hidden": "true" }), GATE_EVALUATING));
    try {
      const response = await fetch(`${apiBase}/trigger`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ replay: true }),
      });
      const data = await response.json();
      if (!response.ok || !data.ok || !data.state) {
        throw new Error(data.detail || "Trigger failed.");
      }
      state = data.state;
      buildRail();
      show(0);
      root.classList.add("playing");
      autoStep();
    } catch (error) {
      // Reveal the server-rendered fallback if the interactive replay cannot load.
      body.classList.remove("js");
      view.replaceChildren();
    } finally {
      if (replayBtn) replayBtn.disabled = false;
    }
  };

  replayBtn?.addEventListener("click", replay);
  document.addEventListener("keydown", (event) => {
    if (event.key === "ArrowRight") { stopAuto(); show(idx + 1); }
    else if (event.key === "ArrowLeft") { stopAuto(); show(idx - 1); }
  });

  replay();
})();
