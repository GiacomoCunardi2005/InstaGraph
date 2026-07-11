/* Open this extension page locally; it uses no server, account, or network request. */
(async function runFixtures() {
  "use strict";

  const core = globalThis.InstaGraphCaptureCore;
  const instagram = globalThis.InstaGraphInstagramAdapter;
  const frame = document.querySelector("#fixture");
  const results = document.querySelector("#results");
  let failures = 0;

  function report(ok, label) {
    const item = document.createElement("li");
    item.className = ok ? "pass" : "fail";
    item.innerText = `${ok ? "PASS" : "FAIL"} — ${label}`;
    results.append(item);
    failures += ok ? 0 : 1;
  }

  function assert(condition, label) {
    report(Boolean(condition), label);
  }

  async function loadFixture(name) {
    const loaded = new Promise((resolve) => frame.addEventListener("load", resolve, { once: true }));
    frame.src = `fixtures/${name}`;
    await loaded;
    return [frame.contentDocument, frame.contentWindow];
  }

  let documentInFrame;
  [documentInFrame] = await loadFixture("recognized-list.html");
  const recognized = core.visibleUsernames(documentInFrame, () => true);
  assert(recognized.ok && recognized.usernames.join(",") === "alice,bob", "legge solo username dichiarati");
  const following = core.buildDraft(
    core.validateContext({ owner: "@marco", direction: "following", consent: true }).context,
    recognized.usernames,
  );
  assert(following.follows[0].source === "marco" && following.follows[0].target === "alice", "direzione following");

  let fixtureWindow;
  [documentInFrame, fixtureWindow] = await loadFixture("row-added-on-scroll.html");
  const before = core.visibleUsernames(documentInFrame, () => true);
  fixtureWindow.appendVisibleRow();
  const after = core.visibleUsernames(documentInFrame, () => true);
  const entered = after.usernames.filter((username) => !before.usernames.includes(username));
  assert(before.ok && after.ok && entered.join(",") === "charlie", "riga aggiunta durante lo scroll simulato");

  [documentInFrame] = await loadFixture("no-list.html");
  assert(!core.validateStructure(documentInFrame).ok, "nessuna lista: fail-closed");

  [documentInFrame] = await loadFixture("ambiguous-list.html");
  assert(!core.validateStructure(documentInFrame).ok, "due liste: fail-closed");

  [documentInFrame] = await loadFixture("malformed-row.html");
  assert(!core.validateStructure(documentInFrame).ok, "figlio inatteso: fail-closed");

  [documentInFrame] = await loadFixture("instagram-recognized-list.html");
  const instagramList = core.visibleUsernames(documentInFrame, () => true, instagram.resolve);
  assert(instagramList.ok && instagramList.usernames.join(",") === "alice,bob", "adapter legge solo testo username verificato");

  [documentInFrame, fixtureWindow] = await loadFixture("instagram-row-added-on-scroll.html");
  const instagramBefore = core.visibleUsernames(documentInFrame, () => true, instagram.resolve);
  fixtureWindow.appendVisibleRow();
  const instagramAfter = core.visibleUsernames(documentInFrame, () => true, instagram.resolve);
  assert(
    instagramBefore.ok && instagramAfter.ok && instagramAfter.usernames.join(",") === "alice,charlie",
    "adapter riconosce una riga sintetica aggiunta",
  );

  [documentInFrame] = await loadFixture("instagram-ambiguous-list.html");
  assert(!core.validateStructure(documentInFrame, instagram.resolve).ok, "adapter rifiuta username ambiguo");

  [documentInFrame] = await loadFixture("instagram-extra-anchor.html");
  assert(!core.validateStructure(documentInFrame, instagram.resolve).ok, "adapter rifiuta link extra non verificati");

  [documentInFrame] = await loadFixture("instagram-cross-origin-base.html");
  assert(!core.validateStructure(documentInFrame, instagram.resolve).ok, "adapter rifiuta base con origine diversa");

  [documentInFrame] = await loadFixture("instagram-offscreen-row.html");
  const onlyVisible = core.visibleUsernames(
    documentInFrame,
    (element) => !element.closest("[data-test-offscreen]"),
    instagram.resolve,
  );
  assert(onlyVisible.ok && onlyVisible.usernames.join(",") === "alice", "adapter non legge testo fuori viewport");

  const followers = core.buildDraft(
    core.validateContext({ owner: "marco", direction: "followers", consent: true }).context,
    ["alice"],
  );
  assert(followers.follows[0].source === "alice" && followers.follows[0].target === "marco", "direzione followers");

  document.querySelector("#summary").innerText = failures
    ? `${failures} fixture non superate.`
    : "Tutte le fixture locali sono superate.";
}());
