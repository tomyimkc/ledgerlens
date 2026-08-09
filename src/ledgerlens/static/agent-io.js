(() => {
  "use strict";

  const body = document.body;
  const traceUrl = body.dataset.traceUrl;
  const metaEl = document.querySelector("[data-trace-meta]");
  const flowEl = document.querySelector("[data-agent-flow]");
  const callsEl = document.querySelector("[data-llm-calls]");
  const planEl = document.querySelector("[data-plan-out]");
  const gateEl = document.querySelector("[data-gate-out]");

  const h = (tag, attrs, ...kids) => {
    const node = document.createElement(tag);
    if (attrs) {
      for (const [k, v] of Object.entries(attrs)) {
        if (v == null) continue;
        if (k === "class") node.className = v;
        else if (k === "text") node.textContent = v;
        else node.setAttribute(k, v);
      }
    }
    for (const kid of kids) {
      if (kid == null) continue;
      node.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
    }
    return node;
  };

  const pretty = (v) => {
    try {
      return JSON.stringify(v, null, 2);
    } catch (_e) {
      return String(v);
    }
  };

  const renderFlow = (flow, status) => {
    if (!flowEl) return;
    flowEl.replaceChildren();
    const track = h("div", { class: "agent-flow-track" });
    (flow || []).forEach((step, i) => {
      const active =
        (status === "authorized" && step.id === "gate") ||
        (status === "blocked" && step.id === "gate") ||
        step.actor === "llm";
      const card = h(
        "div",
        { class: "agent-flow-node actor-" + (step.actor || "tools") + (active ? " lit" : "") },
        h("span", { class: "afn-id", text: String.fromCharCode(65 + i) }),
        h("strong", { text: step.label || step.id }),
        h("small", { text: step.detail || "" }),
        step.model ? h("code", { text: step.model }) : null,
        step.models ? h("code", { text: (step.models || []).join(", ") }) : null
      );
      track.append(card);
      if (i < flow.length - 1) {
        track.append(h("span", { class: "agent-flow-arrow", "aria-hidden": "true", text: "→" }));
      }
    });
    flowEl.append(track);
  };

  const renderCalls = (calls) => {
    if (!callsEl) return;
    callsEl.replaceChildren();
    if (!calls || !calls.length) {
      callsEl.append(
        h("p", {
          class: "sec-note",
          text: "No LLM calls in this trace yet. Run scripts/run_agent_io_trace.py --force with OPENAI_API_KEY or ANTHROPIC_API_KEY.",
        })
      );
      return;
    }
    for (const call of calls) {
      const out = call.output && call.output.json ? call.output.json : call.output;
      const head = h(
        "button",
        { type: "button", class: "llm-call-hd", "aria-expanded": "false" },
        h("span", { class: "llm-step", text: "Call " + call.step }),
        h("strong", { text: call.role || "model" }),
        h("code", { text: call.model || "?" }),
        h("span", { class: "llm-chev", "aria-hidden": "true", text: "▸" })
      );
      const bodyBox = h(
        "div",
        { class: "llm-call-body", hidden: "hidden" },
        h("h4", { text: "System prompt (input)" }),
        h("pre", { class: "code-block", text: call.input && call.input.system ? call.input.system : "—" }),
        h("h4", { text: "User prompt (input)" }),
        h("pre", {
          class: "code-block",
          text: call.input && call.input.userPrompt ? call.input.userPrompt : "—",
        }),
        h("h4", { text: "Context sent to the model (input)" }),
        h("pre", {
          class: "code-block",
          text: pretty(call.input && call.input.context),
        }),
        h("h4", { text: "Model JSON output" }),
        h("pre", {
          class: "code-block out",
          text: call.error ? "ERROR: " + call.error : pretty(out),
        })
      );
      head.addEventListener("click", () => {
        const open = head.getAttribute("aria-expanded") === "true";
        head.setAttribute("aria-expanded", open ? "false" : "true");
        bodyBox.hidden = open;
        head.querySelector(".llm-chev").textContent = open ? "▸" : "▾";
      });
      callsEl.append(h("article", { class: "llm-call" }, head, bodyBox));
    }
  };

  const start = async () => {
    try {
      const res = await fetch(traceUrl, { credentials: "same-origin" });
      const data = await res.json();
      if (!data || !data.ok || !data.trace) {
        throw new Error((data && data.detail) || "Trace not available");
      }
      const t = data.trace;
      if (metaEl) {
        metaEl.replaceChildren(
          h(
            "span",
            { class: "meta-chip status-" + (t.status || "unknown") },
            "status: " + (t.status || "?")
          ),
          h("span", { class: "meta-chip" }, "planner: " + ((t.models && t.models.planner) || "?")),
          h(
            "span",
            { class: "meta-chip" },
            "verifiers: " + ((t.models && t.models.verifiers) || []).join(", ")
          ),
          h("span", { class: "meta-chip" }, "llm calls: " + ((t.llmCalls && t.llmCalls.length) || 0)),
          h("span", { class: "meta-chip" }, "incident: " + (t.incidentId || "?")),
          h(
            "span",
            { class: "meta-chip" },
            "mutations: " + (t.externalMutations ? "yes" : "none")
          )
        );
      }
      renderFlow(t.flow, t.status);
      renderCalls(t.llmCalls || []);
      if (planEl) {
        planEl.textContent = t.agentPlan
          ? pretty(t.agentPlan)
          : "(no plan — run failed before planning completed)";
      }
      if (gateEl) {
        gateEl.textContent = t.authorization
          ? pretty(t.authorization)
          : t.error
            ? "ERROR: " + t.error
            : "(no authorization object)";
      }
    } catch (err) {
      if (metaEl) {
        metaEl.textContent =
          String(err && err.message ? err.message : err) +
          " — generate with: uv run python scripts/run_agent_io_trace.py --force";
      }
    }
  };

  start();
})();
