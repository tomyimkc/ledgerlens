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
    { icon: "◇", label: "DataHub context", mod: "mcp_client", line: () => "Owner · schema · lineage read over MCP" },
    { icon: "▤", label: "Plan", mod: "agent", line: () => "Bounded, reversible actions proposed" },
    { icon: "◈", label: "Verify", mod: "VerifierPanel", line: () => "AI advisory review — cannot authorize" },
    { icon: "⛨", label: "Policy gate", mod: "PolicyGate", line: () => "Deterministic authorization of the exact plan" },
    { icon: "⇶", label: "Act", mod: "action_adapters", line: () => "GitHub · Slack · PagerDuty · Jira" },
    { icon: "⤴", label: "Write-back", mod: "mcp_mutations", line: () => "Incident receipt saved to DataHub" },
    { icon: "⇉", label: "Handoff", mod: "memory", line: () => "Next agent inherits facts + unknowns" },
  ];

  const SCENARIOS = [
    { id: "freshness", day: "MON", sev: 1, type: "Freshness SLO breach", entity: "analytics.payments_daily", trigger: "Freshness 23m over a 15m SLO", featured: true },
    { id: "schema", day: "TUE", sev: 2, type: "Schema drift", entity: "core.orders_v2", trigger: "Breaking column type change detected" },
    { id: "volume", day: "WED", sev: 2, type: "Volume anomaly", entity: "events.clickstream", trigger: "Row count −62% vs baseline" },
    { id: "access", day: "THU", sev: 1, type: "Access / ACL change", entity: "pii.customers", trigger: "Ownership and ACL changed on PII" },
    { id: "deploy", day: "FRI", sev: 1, type: "Upstream deploy break", entity: "finance.revenue_dashboard", trigger: "dbt deploy invalidated the model" },
    { id: "ingest", day: "SAT", sev: 3, type: "Ingestion failure", entity: "vendor.billing_feed", trigger: "Connector run failed; lineage stale" },
  ];

  let backend = null;
  let current = SCENARIOS[0];
  let nodes = [];
  let arrows = [];
  let cards = {};
  let active = -1;
  let ticking = false;

  // ---- timeline ------------------------------------------------------------
  const buildTimeline = () => {
    timelineEl.replaceChildren();
    for (const s of SCENARIOS) {
      const card = h("button", { class: "tevent", type: "button", "aria-label": s.type },
        h("span", { class: "tday", text: s.day }),
        h("span", { class: "ttype", text: s.type }),
        h("span", { class: "tent", text: s.entity }),
        h("span", { class: "tsev sev" + s.sev, text: "SEV-" + s.sev }),
        s.featured ? h("span", { class: "tstar", text: "★ real receipts" }) : null);
      card.addEventListener("click", () => { current = s; paintTimeline(); buildStory(); scrollToStep(0); });
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
      node.addEventListener("click", () => scrollToStep(i));
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
    const c = (backend && backend.context) || {};
    const e = c.entity || {};
    const b = c.blast_radius || {};
    const g = h("div", { class: "lineage" });
    g.append(h("div", { class: "lin-node src" },
      h("b", { text: current.entity || e.name || "entity" }),
      h("small", { text: (e.tier || "Tier 1") + " · " + (e.owner || "Data Platform") })));
    g.append(h("div", { class: "lin-arrow", "aria-hidden": "true", text: "⇢" }));
    const col = h("div", { class: "lin-col" });
    for (const a of arr(b.assets).slice(0, 4)) {
      col.append(h("div", { class: "lin-node t" + (String(a.criticality || "").includes("1") ? "1" : "2") },
        h("b", { text: a.name }), h("small", { text: a.relationship || "" })));
    }
    if (col.childElementCount) g.append(col);
    return g;
  };

  const receiptChips = (i) => {
    if (!current.featured || !backend) return null;
    if (i === 5) {
      const wrap = h("div", { class: "chips" });
      for (const a of arr(backend.actions)) if (a.receipt) wrap.append(h("code", { class: "chip", text: a.receipt }));
      return wrap.childElementCount ? wrap : null;
    }
    if (i === 6 && backend.writeback?.receipt) return h("div", { class: "chips" }, h("code", { class: "chip", text: backend.writeback.receipt }));
    if (i === 7 && backend.memory?.memory_id) return h("div", { class: "chips" }, h("code", { class: "chip", text: backend.memory.memory_id }));
    return null;
  };

  // ---- story steps (all present; revealed + highlighted by scroll) ---------
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
    if (i === 1 && backend && backend.context) bodyEl.append(lineageGraph());
    if (i === 6) bodyEl.append(h("p", { class: "dhback" }, "↳ writes the incident receipt back to DataHub — ",
      h("a", { href: "https://github.com/acryldata/mcp-server-datahub/pull/160", target: "_blank", rel: "noopener", text: "upstream PR #160" })));
    const chips = receiptChips(i);
    if (chips) bodyEl.append(chips);
    else if (!current.featured && i >= 5) bodyEl.append(h("p", { class: "dnote", text: "Illustrative pattern — no receipts generated for this scenario." }));
    const row = h("div", { class: "logrow", "data-i": String(i) },
      h("div", { class: "logmark" }, h("span", { class: "lognum", text: (i + 1).toString().padStart(2, "0") })),
      bodyEl);
    return row;
  };

  const buildStory = () => {
    logEl.replaceChildren();
    cards = {};
    active = -1;
    for (let i = 0; i < NODES.length; i++) {
      const row = buildStep(i);
      logEl.append(row);
      cards[i] = row;
    }
    requestAnimationFrame(measure);
  };

  const setActive = (i) => {
    i = Math.max(0, Math.min(NODES.length - 1, i));
    if (i === active) return;
    const advancing = i > active;
    for (let k = 0; k <= i; k++) cards[k]?.classList.add("in");
    paintDiagram(i);
    logEl.querySelectorAll(".logrow.active").forEach((r) => r.classList.remove("active"));
    cards[i]?.classList.add("active");
    if (advancing && i > 0) flowArrow(i - 1); // "goes to next phase" animation, on scroll
    active = i;
  };

  // ---- scroll driver -------------------------------------------------------
  const measure = () => {
    const line = window.innerHeight * 0.42;
    let idx = 0;
    for (let k = 0; k < NODES.length; k++) {
      const r = cards[k]?.getBoundingClientRect();
      if (r && r.top <= line) idx = k;
    }
    setActive(idx);
  };
  const onScroll = () => {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(() => { ticking = false; measure(); });
  };

  const scrollToStep = (i) => {
    const el = cards[i];
    if (!el) return;
    const y = el.getBoundingClientRect().top + window.pageYOffset - window.innerHeight * 0.28;
    window.scrollTo({ top: Math.max(0, y), behavior: "smooth" });
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

  const buildProofs = async () => {
    const el = document.querySelector("[data-proofs]");
    if (!el) return;
    el.replaceChildren(
      h("p", { class: "proofs-eyebrow", text: "TWO PROOFS THE GATE IS REAL" }),
      h("h2", { class: "proofs-title", text: "What makes this different from the other DataHub agents" }));
    try {
      const [g, q] = await Promise.all([
        fetch(`${apiBase}/gate-demo`, { credentials: "same-origin" }).then((r) => r.json()),
        fetch(`${apiBase}/quorum-demo`, { credentials: "same-origin" }).then((r) => r.json()),
      ]);
      if (g && g.demo) el.append(gateCard(g.demo));
      if (q && q.demo) el.append(quorumCard(q.demo));
    } catch (error) { /* leave the heading; proofs are best-effort */ }
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
      buildTimeline(); paintTimeline(); buildPipe(); buildStory(); buildProofs();
    } catch (error) {
      body.classList.remove("js");
      logEl.replaceChildren();
    } finally {
      if (replayBtn) replayBtn.disabled = false;
    }
  };

  replayBtn?.addEventListener("click", () => scrollToStep(0));
  window.addEventListener("scroll", onScroll, { passive: true });
  window.addEventListener("resize", onScroll, { passive: true });
  window.addEventListener("scroll", () => hintEl?.classList.add("gone"), { once: true, passive: true });
  document.addEventListener("keydown", (e) => {
    if (e.key === "ArrowRight" || e.key === "ArrowDown") scrollToStep(Math.min(active + 1, NODES.length - 1));
    else if (e.key === "ArrowLeft" || e.key === "ArrowUp") scrollToStep(Math.max(active - 1, 0));
  });

  start();
})();
