(() => {
  "use strict";

  // Animated incident-pipeline diagram. A timeline of DataHub-observed incidents
  // feeds one visible pipeline: data flows node -> node along animated arrows,
  // each node tied to the repo module that handles it. Minimal text; click a node
  // for the short detail. The server still renders the full panels as a no-JS
  // fallback (see `.legacy-content`), only hidden once the diagram is ready.
  //
  // Authorization is deterministic: "Evaluating deterministic gate" is shown while
  // the executed fixture state loads — AI cannot open the gate.

  const body = document.body;
  const apiBase = body.dataset.apiBase;
  const root = document.querySelector("[data-flow-root]");
  const timelineEl = document.querySelector("[data-timeline]");
  const pipeEl = document.querySelector("[data-pipe]");
  const detailEl = document.querySelector("[data-detail]");
  const replayBtn = document.querySelector("[data-flow-replay]");
  const GATE = "Evaluating deterministic gate…";
  const STEP_MS = 900;

  if (!root || !timelineEl || !pipeEl || !detailEl) return; // keep server fallback

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
  let timer = null;
  let active = 0;

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
      node.addEventListener("click", () => { stop(); activate(i); });
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
    setTimeout(() => arrow.classList.add("filled"), STEP_MS - 120);
  };

  const activate = (i) => {
    active = Math.max(0, Math.min(NODES.length - 1, i));
    nodes.forEach((node, k) => {
      node.classList.toggle("active", k === active);
      node.classList.toggle("done", k < active);
    });
    renderDetail(active);
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

  const renderDetail = (i) => {
    const n = NODES[i];
    const card = h("div", { class: "dcard" },
      h("div", { class: "dhead" },
        h("span", { class: "dicon", text: n.icon }),
        h("div", null, h("strong", { text: (i + 1).toString().padStart(2, "0") + " · " + n.label }),
          h("code", { class: "dmod", text: n.mod })),
        i === 4 ? h("span", { class: "dtag ok", text: "AI can't authorize" }) : null),
      h("p", { class: "dline", text: n.line(current) }));
    const chips = receiptChips(i);
    if (chips) card.append(chips);
    else if (!current.featured && i >= 5) card.append(h("p", { class: "dnote", text: "Illustrative pattern — no receipts generated for this scenario." }));
    card.classList.add("in-detail");
    detailEl.replaceChildren(card);
    requestAnimationFrame(() => card.classList.add("shown"));
  };

  const stop = () => { if (timer) { clearTimeout(timer); timer = null; } root.classList.remove("playing"); };

  const play = () => {
    stop();
    arrows.forEach((a) => a.classList.remove("flowing", "filled"));
    root.classList.add("playing");
    activate(0);
    let i = 0;
    const tick = () => {
      if (i >= NODES.length - 1) { stop(); return; }
      flowArrow(i);
      timer = setTimeout(() => { i += 1; activate(i); tick(); }, STEP_MS);
    };
    tick();
  };

  const start = async () => {
    if (replayBtn) replayBtn.disabled = true;
    body.classList.add("js");
    detailEl.replaceChildren(h("div", { class: "dcard" }, h("p", { class: "dline", text: GATE })));
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
      detailEl.replaceChildren();
    } finally {
      if (replayBtn) replayBtn.disabled = false;
    }
  };

  replayBtn?.addEventListener("click", () => play());
  document.addEventListener("keydown", (e) => {
    if (e.key === "ArrowRight") { stop(); activate(active + 1); }
    else if (e.key === "ArrowLeft") { stop(); activate(active - 1); }
  });

  start();
})();
