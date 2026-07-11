const assert = require("node:assert/strict");
const fs = require("node:fs");
const manifest = require("../manifest.json");
const path = require("node:path");
const test = require("node:test");
const core = require("../capture-core.js");

test("context requires owner, direction, and explicit consent", () => {
  assert.equal(core.validateContext({ owner: "marco", direction: "following", consent: false }).ok, false);
  assert.deepEqual(
    core.validateContext({ owner: " @Marco ", direction: "followers", consent: true }).context,
    { owner: "marco", direction: "followers" },
  );
});

test("draft is strict JSON v1 with deduplicated directed edges", () => {
  const context = core.validateContext({ owner: "marco", direction: "following", consent: true }).context;
  assert.deepEqual(core.buildDraft(context, ["alice", "@Alice", "marco", "bob"]), {
    version: 1,
    accounts: ["marco", "alice", "bob"],
    follows: [
      { source: "marco", target: "alice" },
      { source: "marco", target: "bob" },
    ],
  });
});

test("draft reverses edges for a confirmed followers list", () => {
  const context = core.validateContext({ owner: "marco", direction: "followers", consent: true }).context;
  assert.deepEqual(core.buildDraft(context, ["alice"]).follows, [{ source: "alice", target: "marco" }]);
});

test("viewport checks require a foreground connected element", () => {
  const view = {
    innerWidth: 100,
    innerHeight: 100,
    document: { visibilityState: "visible", documentElement: {} },
  };
  const visible = { isConnected: true, getBoundingClientRect: () => ({ top: 1, left: 1, right: 20, bottom: 20 }) };
  assert.equal(core.isInViewport(visible, view), true);
  visible.checkVisibility = () => false;
  assert.equal(core.isInViewport(visible, view), false);
  visible.checkVisibility = () => { throw new Error("older browser"); };
  assert.equal(core.isInViewport(visible, view), true);
  delete visible.checkVisibility;
  view.document.visibilityState = "hidden";
  assert.equal(core.isInViewport(visible, view), false);
  view.document.visibilityState = "visible";
  view.getComputedStyle = () => ({ display: "block", visibility: "hidden", opacity: "1" });
  assert.equal(core.isInViewport(visible, view), false);
  view.getComputedStyle = () => ({ display: "block", visibility: "visible", opacity: "1" });
  const clippedParent = {
    getBoundingClientRect: () => ({ top: 0, left: 0, right: 10, bottom: 10 }),
    parentElement: null,
  };
  const clipped = {
    isConnected: true,
    parentElement: clippedParent,
    getBoundingClientRect: () => ({ top: 30, left: 0, right: 10, bottom: 40 }),
  };
  view.getComputedStyle = (element) => (
    element === clippedParent
      ? { display: "block", visibility: "visible", opacity: "1", overflow: "hidden" }
      : { display: "block", visibility: "visible", opacity: "1" }
  );
  assert.equal(core.isInViewport(clipped, view), false);
  const empty = { isConnected: true, getBoundingClientRect: () => ({ top: 1, left: 1, right: 1, bottom: 1 }) };
  assert.equal(core.isInViewport(empty, view), false);
  const offscreenParent = {
    getBoundingClientRect: () => ({ top: 0, left: -10, right: -1, bottom: 10 }),
    parentElement: null,
  };
  const partlyInViewport = {
    isConnected: true,
    parentElement: offscreenParent,
    getBoundingClientRect: () => ({ top: 0, left: -10, right: 10, bottom: 10 }),
  };
  view.getComputedStyle = (element) => (
    element === offscreenParent
      ? { display: "block", visibility: "visible", opacity: "1", overflow: "hidden" }
      : { display: "block", visibility: "visible", opacity: "1" }
  );
  assert.equal(core.isInViewport(partlyInViewport, view), false);
});

test("automatic capture reads a reused visible row's current username", () => {
  const username = { innerText: "alice" };
  const firstRow = {
    matches: () => true,
    querySelectorAll: () => [username],
    querySelector: () => username,
  };
  const root = { children: [firstRow] };
  const document = { querySelectorAll: () => [root] };

  assert.deepEqual(
    core.visibleUsernames(document, () => true),
    { ok: true, usernames: ["alice"] },
  );
  username.innerText = "bob";
  assert.deepEqual(
    core.visibleUsernames(document, () => true),
    { ok: true, usernames: ["bob"] },
  );
});

test("manifest remains a foreground-only extension", () => {
  assert.deepEqual(manifest.permissions, ["activeTab", "scripting"]);
  assert.equal("host_permissions" in manifest, false);
  assert.equal("background" in manifest, false);
  assert.equal("content_scripts" in manifest, false);
});

test("popup keeps the content script as the draft source of truth", () => {
  const popup = fs.readFileSync(path.join(__dirname, "..", "popup.js"), "utf8");

  assert.doesNotMatch(popup, /\breviewedDraft\b/);
  assert.match(popup, /reply = await send\("STATUS"\)/);
  assert.match(popup, /draftPreview\.innerText = ""/);
});
