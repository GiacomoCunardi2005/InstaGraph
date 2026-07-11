/* Runs only after the user presses Start in the extension popup. */
(function installVisibleCapture() {
  "use strict";

  const extension = globalThis.browser || globalThis.chrome;
  const core = globalThis.InstaGraphCaptureCore;
  const adapter = globalThis.InstaGraphInstagramAdapter;
  const controllerKey = "__instagraphVisibleCaptureControllerV1";
  const messageScope = "instagraph-visible-capture-v1";

  if (!extension || !core || !adapter || typeof adapter.resolve !== "function" || globalThis[controllerKey]) {
    return;
  }

  function supportedPage() {
    return window.top === window
      && location.protocol === "https:"
      && (location.hostname === "instagram.com" || location.hostname === "www.instagram.com");
  }

  function createController() {
    let session = null;
    let indicator = null;
    let observer = null;
    let captureFrame = null;

    function currentDraft() {
      if (!session || !session.context || session.state !== "review") {
        return null;
      }
      return core.buildDraft(session.context, session.usernames);
    }

    function summary() {
      if (!session) {
        return { state: "idle" };
      }
      return {
        state: session.state,
        count: session.usernames ? session.usernames.size : 0,
        context: session.context || null,
        reason: session.reason || null,
        draft: currentDraft(),
      };
    }

    function removeIndicator() {
      indicator?.remove();
      indicator = null;
    }

    function removeListeners() {
      document.removeEventListener("scroll", onScroll, true);
      document.removeEventListener("visibilitychange", onVisibilityChange);
      window.removeEventListener("pagehide", onPageHide);
      if (captureFrame !== null) {
        window.cancelAnimationFrame(captureFrame);
        captureFrame = null;
      }
      observer?.disconnect();
      observer = null;
    }

    function updateIndicator() {
      if (!indicator || !session?.context) {
        return;
      }
      indicator.querySelector("span").innerText = [
        "InstaGraph capture attiva",
        `${session.context.direction} di @${session.context.owner}`,
        `${session.usernames.size} username`,
        "scorri manualmente la lista",
      ].join(" · ");
    }

    function installIndicator() {
      indicator = document.createElement("aside");
      indicator.setAttribute("data-instagraph-capture-indicator", "v1");
      Object.assign(indicator.style, {
        all: "initial",
        position: "fixed",
        right: "16px",
        bottom: "16px",
        zIndex: "2147483647",
        display: "flex",
        gap: "8px",
        alignItems: "center",
        padding: "10px 12px",
        border: "1px solid #8c1d18",
        borderRadius: "8px",
        background: "#fff7f6",
        color: "#35110e",
        font: "13px system-ui, sans-serif",
      });
      const label = document.createElement("span");
      const stopButton = document.createElement("button");
      stopButton.type = "button";
      stopButton.innerText = "Stop";
      Object.assign(stopButton.style, {
        all: "initial",
        cursor: "pointer",
        padding: "4px 8px",
        border: "1px solid #35110e",
        borderRadius: "4px",
        font: "13px system-ui, sans-serif",
      });
      stopButton.addEventListener("click", () => stop("stopped by user", true));
      indicator.append(label, stopButton);
      document.documentElement.append(indicator);
      updateIndicator();
    }

    function fail(reason) {
      removeListeners();
      removeIndicator();
      session = { state: "failed", reason };
      return { ok: false, ...summary() };
    }

    function stop(reason, keepDraft) {
      if (!session || session.state !== "active") {
        return { ok: false, reason: "no active capture" };
      }
      removeListeners();
      removeIndicator();
      if (!keepDraft) {
        return fail(reason);
      }
      session.state = "review";
      session.reason = reason;
      return { ok: true, ...summary() };
    }

    function visibleUsernames() {
      return core.visibleUsernames(
        document,
        (element) => core.isInViewport(element, window),
        adapter.resolve,
      );
    }

    function validateStructure() {
      return core.validateStructure(document, adapter.resolve);
    }

    function captureVisibleRows() {
      if (!session || session.state !== "active") {
        return;
      }
      const snapshot = visibleUsernames();
      if (!snapshot.ok) {
        fail(snapshot.reason);
        return;
      }
      const entering = snapshot.usernames.filter(
        (username) => !session.visibleUsernames.has(username),
      );
      session.visibleUsernames = new Set(snapshot.usernames);
      for (const username of entering) {
        if (username !== session.context.owner) {
          session.usernames.add(username);
        }
      }
      updateIndicator();
    }

    function onScroll(event) {
      // Ignore dispatched events. The browser does not reveal whether a trusted scroll was human.
      if (!event.isTrusted || captureFrame !== null) {
        return;
      }
      captureFrame = window.requestAnimationFrame(() => {
        // The page may queue its own render from the same scroll handler.
        captureFrame = window.requestAnimationFrame(() => {
          captureFrame = null;
          captureVisibleRows();
        });
      });
    }

    function onVisibilityChange() {
      if (document.visibilityState !== "visible") {
        stop("tab hidden", true);
      }
    }

    function onPageHide() {
      stop("page left", true);
    }

    function observeStructure() {
      observer = new MutationObserver(() => {
        if (!session || session.state !== "active") {
          return;
        }
        const structure = validateStructure();
        if (!structure.ok) {
          fail(structure.reason);
        }
      });
      observer.observe(document.documentElement, { childList: true, subtree: true });
    }

    function start(rawContext) {
      if (!supportedPage()) {
        return fail("unsupported page");
      }
      if (session?.state === "failed") {
        session = null;
      }
      if (session) {
        return { ok: false, reason: "discard the current draft before starting again" };
      }
      const checked = core.validateContext(rawContext);
      if (!checked.ok) {
        return { ok: false, reason: checked.reason };
      }
      const structure = validateStructure();
      if (!structure.ok) {
        return fail(structure.reason);
      }
      const initial = visibleUsernames();
      if (!initial.ok) {
        return fail(initial.reason);
      }
      session = {
        state: "active",
        context: checked.context,
        usernames: new Set(),
        visibleUsernames: new Set(initial.usernames),
        reason: null,
      };
      document.addEventListener("scroll", onScroll, { capture: true, passive: true });
      observeStructure();
      document.addEventListener("visibilitychange", onVisibilityChange);
      window.addEventListener("pagehide", onPageHide);
      installIndicator();
      return { ok: true, ...summary() };
    }

    function discard() {
      removeListeners();
      removeIndicator();
      session = null;
      return { ok: true, ...summary() };
    }

    return {
      handle(message) {
        switch (message.type) {
          case "START":
            return start(message.context);
          case "STOP":
            return stop("stopped by user", true);
          case "STATUS":
            return { ok: true, ...summary() };
          case "DISCARD":
            return discard();
          default:
            return { ok: false, reason: "unknown command" };
        }
      },
    };
  }

  const controller = createController();
  globalThis[controllerKey] = controller;
  extension.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (!message || message.scope !== messageScope) {
      return undefined;
    }
    sendResponse(controller.handle(message));
    return false;
  });
}());
