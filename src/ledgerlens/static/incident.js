(() => {
  "use strict";

  // Animated incident-pipeline diagram + an accumulating story log. A timeline of
  // DataHub-observed incidents feeds one visible pipeline: data flows node -> node
  // along animated arrows, and each stage APPENDS a card into a growing vertical
  // story below (never hiding the earlier stages) so the whole progress stays on
  // screen. Each node maps to the repo module that handles it. The server still
  // renders the full panels as a no-JS fallback (see `.legacy-content`), hidden
  // only once the diagram is ready.
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
  const GATE = "Evaluating deterministic gate…";
  const STEP_MS = 950;

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

  // ---- pipeline nodes (mapped to real repo modules) ------------------------
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

  // ---- incident timeline (illustrative scenarios; ★ carries real receipts) -
  const SCENARIOS = [
    { id: "freshness", day: "MON", sev: 1, type: "Freshness SLO breach", entity: "analytics.payments_daily", trigger: "Freshness 23m over a 15m SLO", featured: true },
    { id: "schema", day: "TUE", sev: 2, type: "Schema drift", entity: "core.orders_v2", trigger: "Breaking column type change detected" },
    { id: "volume", day: "WED", sev: 2, type: "Volume anomaly", entity: "events.clickstream", trigger: "Row count −62% vs baseline" },
    { id: "access", day: "THU", sev: 1, type: "Access / ACL change", entity: "pii.customers", trigger: "Ownership and ACL changed on PII" },
    { id: "deploy", day: "FRI", sev: 1, type: "Upstream deploy break", entity: "finance.revenue_dashboard", trigger: "dbt deploy invalidated the model" },
    { id: "ingest", day: "SAT", sev: 3, type: "Ingestion failure", entity: "vendor.billing_feed", trigger: "Connector run failed; lineage stale" },
  ];

  let backend = null;   // executed fixture state (for the featured receipts)
  let current = SCENARIOS[0];
  let nodes = [];
  let arrows = [];
  let cards = {};       // stage index -> appended log row
  let revealed = -1;    // highest stage index revealed in the log
  let timer = null;

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
      card.addEventListener("click", () => { current = s; paintTimeline(); play(); });
      timelineEl.append(card);
    }
  };
  const paintTimeline = () => {
    timelineEl.querySelectorAll(".tevent").forEach((c, i) => c.classList.toggle("on", SCENARIOS[i].id === current.id));
  };

  // ---- pipeline diagram ----------------------------------------------------
  const buildPipe = () => {
    pipeEl.replaceChildren();
    nodes = []; arrows = [];
    NODES.forEach((n, i) => {
      const node = h("button", { class: "pnode", type: "button", "aria-label": n.label },
        h("span", { class: "pnode-icon", text: n.icon }),
        h("span", { class: "pnode-label", text: n.label }),
        h("code", { class: "pnode-mod", text: n.mod }));
      node.addEventListener("click", () => { stop(); revealUpTo(i); });
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
    const arrow = arrows[i];
    if (!arrow) return;
    arrow.classList.remove("flowing");
    void arrow.offsetWidth; // restart the packet animation
    arrow.classList.add("flowing");
    setTimeout(() => arrow.classList.add("filled"), STEP_MS - 150);
  };

  const paintDiagram = (i) => {
    nodes.forEach((node, k) => {
      node.classList.toggle("active", k === i);
      node.classList.toggle("done", k < i);
    });
    arrows.forEach((a, k) => { if (k < i) a.classList.add("filled"); });
  };

  const receiptChips = (i) => {
    if (!current.featured || !backend) return null;
    if (i === 5) {
      const wrap = h("div", { class: "chips" });
      for (const a of (backend.actions || [])) if (a.receipt) wrap.append(h("code", { class: "chip", text: a.receipt }));
      return wrap.childElementCount ? wrap : null;
    }
    if (i === 6 && backend.writeback?.receipt) return h("div", { class: "chips" }, h("code", { class: "chip", text: backend.writeback.receipt }));
    if (i === 7 && backend.memory?.memory_id) return h("div", { class: "chips" }, h("code", { class: "chip", text: backend.memory.memory_id }));
    return null;
  };

  // ---- DataHub-forward extras (make DataHub's role visible) -----------------
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
    for (const a of (b.assets || []).slice(0, 4)) {
      col.append(h("div", { class: "lin-node t" + (String(a.criticality || "").includes("1") ? "1" : "2") },
        h("b", { text: a.name }), h("small", { text: a.relationship || "" })));
    }
    if (col.childElementCount) g.append(col);
    return g;
  };

  // ---- accumulating story log (append, never hide) -------------------------
  const appendStage = (i) => {
    if (cards[i]) return cards[i];
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
    logEl.append(row);
    cards[i] = row;
    requestAnimationFrame(() => row.classList.add("in"));
    return row;
  };

  const markActive = (i) => {
    logEl.querySelectorAll(".logrow.active").forEach((r) => r.classList.remove("active"));
    cards[i]?.classList.add("active");
  };

  const revealUpTo = (i, scrollBlock) => {
    i = Math.max(0, Math.min(NODES.length - 1, i));
    for (let k = revealed + 1; k <= i; k++) appendStage(k);
    revealed = Math.max(revealed, i);
    paintDiagram(i);
    markActive(i);
    cards[i]?.scrollIntoView({ behavior: "smooth", block: scrollBlock || "nearest" });
  };

  const resetLog = () => {
    logEl.replaceChildren();
    cards = {};
    revealed = -1;
    arrows.forEach((a) => a.classList.remove("flowing", "filled"));
  };

  const stop = () => { if (timer) { clearTimeout(timer); timer = null; } root.classList.remove("playing"); };

  const play = () => {
    stop();
    resetLog();
    root.classList.add("playing");
    revealUpTo(0);
    let i = 0;
    const tick = () => {
      if (i >= NODES.length - 1) { stop(); return; }
      flowArrow(i);
      timer = setTimeout(() => { i += 1; revealUpTo(i); tick(); }, STEP_MS);
    };
    tick();
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
      buildTimeline(); paintTimeline(); buildPipe(); play();
    } catch (error) {
      body.classList.remove("js"); // reveal the server-rendered fallback
      logEl.replaceChildren();
    } finally {
      if (replayBtn) replayBtn.disabled = false;
    }
  };

  replayBtn?.addEventListener("click", () => play());
  document.addEventListener("keydown", (e) => {
    if (e.key === "ArrowRight") { stop(); revealUpTo(revealed + 1); }
    else if (e.key === "ArrowLeft" && cards[revealed - 1]) { stop(); paintDiagram(revealed - 1); markActive(revealed - 1); cards[revealed - 1].scrollIntoView({ behavior: "smooth", block: "center" }); revealed -= 1; }
  });

  start();
})();
