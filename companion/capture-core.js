/* Shared, dependency-free capture rules for the popup, content script, and fixtures. */
(function attachCaptureCore(global) {
  "use strict";

  const USERNAME_PATTERN = /^[a-z0-9._]{1,30}$/;
  const DOM_CONTRACT = Object.freeze({
    root: '[data-instagraph-list-root="v1"]',
    row: '[data-instagraph-list-row="v1"]',
    username: '[data-instagraph-username="v1"]',
  });

  function normalizeUsername(value) {
    if (typeof value !== "string") {
      throw new TypeError("username must be a string");
    }
    const normalized = value.trim().toLowerCase().replace(/^@/, "");
    if (!USERNAME_PATTERN.test(normalized)) {
      throw new Error("invalid username");
    }
    return normalized;
  }

  function validateContext(value) {
    if (!value || value.consent !== true) {
      return { ok: false, reason: "explicit consent is required" };
    }
    if (value.direction !== "following" && value.direction !== "followers") {
      return { ok: false, reason: "choose following or followers" };
    }
    try {
      return {
        ok: true,
        context: Object.freeze({
          owner: normalizeUsername(value.owner),
          direction: value.direction,
        }),
      };
    } catch (_) {
      return { ok: false, reason: "owner must be a valid username" };
    }
  }

  function isInViewport(element, view) {
    if (!element || !element.isConnected || !view || view.document.visibilityState !== "visible") {
      return false;
    }
    if (typeof element.checkVisibility === "function") {
      try {
        if (!element.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true })) {
          return false;
        }
      } catch (_) {
        // Use the computed-style fallback on browsers with an older implementation.
      }
    }
    const width = view.innerWidth || view.document.documentElement.clientWidth;
    const height = view.innerHeight || view.document.documentElement.clientHeight;
    let visible = element.getBoundingClientRect();
    if (
      visible.right <= visible.left
      || visible.bottom <= visible.top
      || !intersects(visible, { top: 0, right: width, bottom: height, left: 0 })
    ) {
      return false;
    }
    visible = intersection(visible, { top: 0, right: width, bottom: height, left: 0 });
    for (let current = element; current; current = current.parentElement) {
      const style = typeof view.getComputedStyle === "function" && view.getComputedStyle(current);
      if (
        style
        && (style.display === "none"
          || (style.visibility && style.visibility !== "visible")
          || style.contentVisibility === "hidden"
          || (style.opacity !== "" && Number(style.opacity) === 0))
      ) {
        return false;
      }
      const clips = style && [style.overflow, style.overflowX, style.overflowY].some(
        (value) => value && value !== "visible",
      );
      if (current !== element && clips) {
        const bounds = current.getBoundingClientRect();
        if (
          bounds.right <= bounds.left
          || bounds.bottom <= bounds.top
          || !intersects(visible, bounds)
        ) {
          return false;
        }
        visible = intersection(visible, bounds);
      }
    }
    return true;
  }

  function intersects(first, second) {
    return first.bottom > second.top
      && first.right > second.left
      && first.top < second.bottom
      && first.left < second.right;
  }

  function intersection(first, second) {
    return {
      top: Math.max(first.top, second.top),
      right: Math.min(first.right, second.right),
      bottom: Math.min(first.bottom, second.bottom),
      left: Math.max(first.left, second.left),
    };
  }

  function fixtureStructure(document) {
    const roots = document.querySelectorAll(DOM_CONTRACT.root);
    if (roots.length !== 1) {
      return { ok: false, reason: "the visible-list contract is not uniquely recognized" };
    }

    const root = roots[0];
    const rows = Array.from(root.children);
    for (const row of rows) {
      if (!row.matches(DOM_CONTRACT.row)) {
        return { ok: false, reason: "the list contains an unexpected direct child" };
      }
      const usernameNodes = row.querySelectorAll(DOM_CONTRACT.username);
      if (usernameNodes.length !== 1) {
        return { ok: false, reason: "a list row is ambiguous" };
      }
    }
    return { ok: true, rows };
  }

  function validateStructure(document, resolver) {
    if (resolver === undefined || resolver === null) {
      return fixtureStructure(document);
    }
    if (typeof resolver !== "function") {
      return { ok: false, reason: "the list adapter is unavailable" };
    }
    try {
      const resolved = resolver(document);
      if (!resolved || typeof resolved.ok !== "boolean" || !Array.isArray(resolved.rows)) {
        return { ok: false, reason: "the list adapter returned an invalid result" };
      }
      return resolved;
    } catch (_) {
      return { ok: false, reason: "the list adapter rejected the page" };
    }
  }

  function visibleUsernames(document, isVisible, resolver) {
    const structure = validateStructure(document, resolver);
    if (!structure.ok) {
      return structure;
    }
    const usernames = [];
    for (const resolvedRow of structure.rows) {
      const row = resolvedRow.row || resolvedRow;
      if (!isVisible(row)) {
        continue;
      }
      const usernameNode = resolvedRow.usernameNode || row.querySelector(DOM_CONTRACT.username);
      if (!isVisible(usernameNode)) {
        return { ok: false, reason: "a visible username is not rendered" };
      }
      try {
        usernames.push(normalizeUsername(usernameNode.innerText));
      } catch (_) {
        return { ok: false, reason: "a visible list row has an invalid username" };
      }
    }
    return { ok: true, usernames };
  }

  function buildDraft(context, usernames) {
    const unique = [];
    const seen = new Set();
    for (const rawUsername of usernames) {
      const username = normalizeUsername(rawUsername);
      if (username !== context.owner && !seen.has(username)) {
        seen.add(username);
        unique.push(username);
      }
    }
    return {
      version: 1,
      accounts: [context.owner, ...unique],
      follows: unique.map((username) => (
        context.direction === "following"
          ? { source: context.owner, target: username }
          : { source: username, target: context.owner }
      )),
    };
  }

  const api = Object.freeze({
    DOM_CONTRACT,
    buildDraft,
    isInViewport,
    normalizeUsername,
    validateStructure,
    validateContext,
    visibleUsernames,
  });

  if (typeof module === "object" && module.exports) {
    module.exports = api;
  }
  global.InstaGraphCaptureCore = api;
}(globalThis));
