(() => {
  "use strict";

  const body = document.body;
  const apiBase = body.dataset.apiBase;
  const autonomousExecution = body.dataset.autonomousExecution === "true";
  const toast = document.querySelector("[data-command-toast]");
  let toastTimer;

  const showToast = (message, isError = false) => {
    if (!toast) return;
    window.clearTimeout(toastTimer);
    toast.textContent = message;
    toast.classList.toggle("error", isError);
    toast.classList.add("visible");
    toastTimer = window.setTimeout(() => {
      toast.classList.remove("visible");
    }, 3200);
  };

  const command = async (path, payload = {}) => {
    const response = await fetch(`${apiBase}${path}`, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-Requested-With": "LedgerLens-Incident-Commander",
      },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!response.ok || !result.ok) {
      const failures = result.authorization?.failures;
      const suffix = Array.isArray(failures) && failures.length ? ` ${failures.join("; ")}.` : "";
      throw new Error(`${result.detail || "Command failed."}${suffix}`);
    }
    return result;
  };

  const setBusy = (element, busy, label) => {
    if (!element) return;
    if (busy) {
      element.dataset.originalLabel = element.textContent;
      element.textContent = label;
      element.disabled = true;
      element.setAttribute("aria-busy", "true");
    } else {
      element.textContent = element.dataset.originalLabel || element.textContent;
      element.disabled = false;
      element.removeAttribute("aria-busy");
    }
  };

  document.querySelectorAll("[data-copy]").forEach((button) => {
    button.addEventListener("click", async () => {
      const value = button.dataset.copy;
      if (!value || !navigator.clipboard) {
        showToast("Clipboard access is unavailable.", true);
        return;
      }
      try {
        await navigator.clipboard.writeText(value);
        showToast("Plan fingerprint copied.");
      } catch {
        showToast("Could not copy the plan fingerprint.", true);
      }
    });
  });

  const trigger = document.querySelector("[data-trigger-incident]");
  trigger?.addEventListener("click", async () => {
    setBusy(trigger, true, "Refreshing context…");
    try {
      await command("/trigger", { source: body.dataset.mode });
      showToast(
        autonomousExecution
          ? "AI verification, deterministic authorization, and fanout completed."
          : "Incident trigger accepted. Authorization was reset.",
      );
      window.location.reload();
    } catch (error) {
      setBusy(trigger, false);
      showToast(error.message, true);
    }
  });

  const authorizationForm = document.querySelector("[data-authorization-form]");
  authorizationForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const submit = authorizationForm.querySelector("button[type='submit']");
    const form = new FormData(authorizationForm);
    const feedback = document.querySelector("[data-gate-feedback]");
    const payload = {
      actor: form.get("actor"),
      confirmation: form.get("confirmation"),
      plan_hash: form.get("plan_hash"),
      acknowledge_claim_boundary: form.get("acknowledge_claim_boundary") === "on",
    };
    setBusy(submit, true, "Evaluating deterministic gate…");
    if (feedback) feedback.textContent = "";
    try {
      await command("/authorize", payload);
      showToast("Authorization grant recorded for the exact plan.");
      window.location.reload();
    } catch (error) {
      setBusy(submit, false);
      if (feedback) feedback.textContent = error.message;
      showToast("Authorization denied. Review the failed checks.", true);
    }
  });

  const execute = document.querySelector("[data-execute-fanout]");
  execute?.addEventListener("click", async () => {
    setBusy(execute, true, "Executing bounded fanout…");
    try {
      await command("/execute");
      showToast("Fanout completed. Receipts and inherited memory are ready.");
      window.location.reload();
    } catch (error) {
      setBusy(execute, false);
      showToast(error.message, true);
    }
  });
})();
