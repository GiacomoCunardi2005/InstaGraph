/* Popup state is deliberately ephemeral: only the injected page holds a draft. */
(function setupPopup() {
  "use strict";

  const extension = globalThis.browser || globalThis.chrome;
  const core = globalThis.InstaGraphCaptureCore;
  const scope = "instagraph-visible-capture-v1";
  const form = document.querySelector("#context-form");
  const direction = document.querySelector("#direction");
  const directionSummary = document.querySelector("#direction-summary");
  const consent = document.querySelector("#consent");
  const startButton = document.querySelector("#start");
  const status = document.querySelector("#status");
  const active = document.querySelector("#active");
  const activeSummary = document.querySelector("#active-summary");
  const review = document.querySelector("#review");
  const reviewSummary = document.querySelector("#review-summary");
  const draftPreview = document.querySelector("#draft");

  function rawContext() {
    return {
      direction: direction.value,
      consent: consent.checked,
    };
  }

  function showStatus(text, isError) {
    status.innerText = text;
    status.classList.toggle("error", Boolean(isError));
  }

  function updateStartAvailability() {
    startButton.disabled = !core.validateCaptureOptions(rawContext()).ok;
  }

  async function activeTabId() {
    const tabs = await extension.tabs.query({ active: true, currentWindow: true });
    if (!tabs[0]?.id) {
      throw new Error("active tab unavailable");
    }
    return tabs[0].id;
  }

  async function send(type, extra, tabId) {
    return extension.tabs.sendMessage(tabId ?? await activeTabId(), { scope, type, ...extra });
  }

  async function injectController(tabId) {
    await extension.scripting.executeScript({
      target: { tabId, frameIds: [0] },
      files: ["capture-core.js", "instagram-adapter.js", "content.js"],
    });
  }

  function render(reply) {
    const state = reply?.state || "idle";
    const failed = state === "failed";
    form.hidden = state === "active" || state === "review";
    active.hidden = state !== "active";
    review.hidden = state !== "review";
    if (state !== "review") {
      reviewSummary.innerText = "";
      draftPreview.innerText = "";
    }

    if (state === "active") {
      activeSummary.innerText = `${reply.count} username · ${reply.context.direction} di @${reply.context.owner}. Scorri manualmente la lista.`;
      showStatus("Cattura attiva nella tab scelta.", false);
    } else if (state === "review") {
      reviewSummary.innerText = `${reply.context.direction} di @${reply.context.owner}`;
      draftPreview.innerText = JSON.stringify(reply.draft, null, 2);
      showStatus(`Cattura fermata: ${reply.count} username.`, false);
    } else if (failed) {
      showStatus(`Cattura rifiutata: ${reply.reason}. Bozza cancellata.`, true);
    } else if (reply?.ok === false) {
      showStatus(reply.reason || "Operazione non riuscita.", true);
    } else {
      showStatus("Cattura disattivata.", false);
    }
  }

  async function refreshStatus() {
    try {
      const reply = await send("STATUS");
      render(reply);
      return reply;
    } catch (_) {
      const reply = { ok: true, state: "idle" };
      render(reply);
      return reply;
    }
  }

  async function prefillDirection() {
    direction.value = "";
    directionSummary.innerText = "Direzione: in attesa di rilevamento.";
    try {
      const tabId = await activeTabId();
      await injectController(tabId);
      const detected = await send("DETECT_DIRECTION", undefined, tabId);
      if (!detected.ok) {
        directionSummary.innerText = "Direzione non rilevata.";
        showStatus("Apri una lista Instagram riconosciuta per rilevare la direzione.", true);
        return;
      }
      direction.value = detected.direction;
      directionSummary.innerText = `Direzione rilevata: ${detected.direction === "followers" ? "Follower" : "Chi segui"}.`;
      showStatus("Lista rilevata. Conferma e avvia la cattura.", false);
    } catch (_) {
      directionSummary.innerText = "Direzione non rilevata.";
      showStatus("Apri una lista Instagram nella tab attiva per rilevare la direzione.", true);
    } finally {
      updateStartAvailability();
    }
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const checked = core.validateCaptureOptions(rawContext());
    if (!checked.ok) {
      render({ ok: false, reason: checked.reason });
      return;
    }
    try {
      const tabId = await activeTabId();
      await injectController(tabId);
      render(await send("START", { context: rawContext() }, tabId));
    } catch (_) {
      render({ ok: false, reason: "la cattura è disponibile solo nella tab attiva supportata" });
    }
  });

  document.querySelector("#stop").addEventListener("click", async () => {
    try {
      render(await send("STOP"));
    } catch (_) {
      render({ ok: false, reason: "nessuna cattura attiva nella tab scelta" });
    }
  });

  document.querySelector("#discard").addEventListener("click", async () => {
    try {
      render(await send("DISCARD"));
    } catch (_) {
      render({ ok: true, state: "idle" });
    }
  });

  document.querySelector("#export").addEventListener("click", async () => {
    let reply;
    try {
      reply = await send("STATUS");
    } catch (_) {
      render({ ok: true, state: "idle" });
      showStatus("La bozza non è più disponibile nella tab selezionata.", true);
      return;
    }
    if (reply?.state !== "review" || !reply.draft) {
      render(reply || { ok: true, state: "idle" });
      showStatus("Ferma e rivedi una cattura prima dell'esportazione.", true);
      return;
    }
    const link = document.createElement("a");
    const url = URL.createObjectURL(new Blob([JSON.stringify(reply.draft, null, 2)], {
      type: "application/json",
    }));
    link.href = url;
    link.download = "manual-visible-ui.json";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });

  for (const field of [consent]) {
    field.addEventListener("input", updateStartAvailability);
    field.addEventListener("change", updateStartAvailability);
  }
  updateStartAvailability();
  refreshStatus().then((reply) => {
    if (reply.state !== "active" && reply.state !== "review") {
      return prefillDirection();
    }
    return undefined;
  });
}());
