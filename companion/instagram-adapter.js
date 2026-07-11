/* Narrow adapter for one manually verified, user-visible Instagram list dialog. */
(function attachInstagramAdapter(global) {
  "use strict";

  const DIALOG_SELECTOR = 'div[role="dialog"][aria-modal="true"]';
  const HEADING_SELECTOR = 'h1, h2, h3, h4, h5, h6, [role="heading"]';
  const ROW_CLASSES = new Set([
    "x1ja2u2z",
    "x1n2onr6",
    "x1q0g3np",
    "x1qughib",
    "x2lah0s",
    "x6s0dn4",
  ]);

  function fail(reason) {
    return { ok: false, rows: [], reason };
  }

  function isRow(element) {
    if (element.tagName !== "DIV") {
      return false;
    }
    return Array.from(ROW_CLASSES).every((className) => element.classList.contains(className));
  }

  function routeFor(anchor, document) {
    const href = anchor.getAttribute("href");
    if (!href || !document.baseURI) {
      return null;
    }
    try {
      const page = document.defaultView?.location;
      const target = new URL(href, document.baseURI);
      if (!page || target.origin !== page.origin || target.search || target.hash) {
        return null;
      }
      const match = /^\/([a-z0-9._]{1,30})\/?$/i.exec(target.pathname);
      return match ? `/${match[1].toLowerCase()}/` : null;
    } catch (_) {
      return null;
    }
  }

  function isRenderedLeaf(node, view) {
    if (!node.isConnected || node.children.length !== 0 || !view || typeof view.getComputedStyle !== "function") {
      return false;
    }
    for (let current = node; current; current = current.parentElement) {
      const style = view.getComputedStyle(current);
      if (
        style.display === "none"
        || style.visibility !== "visible"
        || style.contentVisibility === "hidden"
        || Number(style.opacity) === 0
      ) {
        return false;
      }
    }
    return node.getClientRects().length > 0;
  }

  function resolve(document) {
    const dialogs = document?.querySelectorAll?.(DIALOG_SELECTOR);
    if (!dialogs || dialogs.length !== 1) {
      return fail("the Instagram list dialog is not uniquely recognized");
    }

    const dialog = dialogs[0];
    if (!dialog.querySelector(HEADING_SELECTOR) || !dialog.querySelector("input")) {
      return fail("the Instagram list dialog is incomplete");
    }

    const rows = Array.from(dialog.querySelectorAll("div")).filter(isRow);
    if (rows.length === 0) {
      return fail("the Instagram list has no recognized rows");
    }

    const resolved = [];
    const routes = new Set();
    const view = document.defaultView;
    for (const row of rows) {
      if (row.querySelectorAll("img").length !== 1) {
        return fail("an Instagram list row is ambiguous");
      }

      const anchors = Array.from(row.querySelectorAll("a"));
      if (
        anchors.length < 1
        || anchors.length > 2
        || anchors.some((anchor) => anchor.getAttribute("role") !== "link")
      ) {
        return fail("an Instagram list row has an unexpected link count");
      }
      const route = routeFor(anchors[0], document);
      if (!route || anchors.some((anchor) => routeFor(anchor, document) !== route)) {
        return fail("an Instagram list row has an unexpected route");
      }

      const leaves = anchors.flatMap((anchor) => (
        Array.from(anchor.querySelectorAll("span, div"))
          .filter((node) => isRenderedLeaf(node, view))
      ));
      if (leaves.length !== 1 || routes.has(route)) {
        return fail("an Instagram list row has an ambiguous username");
      }

      routes.add(route);
      resolved.push({ row, usernameNode: leaves[0] });
    }
    return { ok: true, rows: resolved };
  }

  const api = Object.freeze({ resolve });
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  }
  global.InstaGraphInstagramAdapter = api;
}(globalThis));
