const assert = require("node:assert/strict");
const fs = require("node:fs");
const test = require("node:test");
const vm = require("node:vm");

const source = fs.readFileSync("src/instagraph/web/app.js", "utf8");

function similarityEdges(elements) {
  const context = vm.createContext({
    document: { querySelector: () => ({ textContent: "" }) },
    window: { location: { protocol: "file:" } },
  });
  vm.runInContext(source, context);
  return JSON.parse(
    vm.runInContext(`JSON.stringify(similarityEdges(${JSON.stringify(elements)}))`, context)
  );
}

test("shared neighbors add invisible similarity springs", () => {
  const edges = similarityEdges({
    nodes: ["alice", "bob", "carol", "dave"].map((id) => ({ data: { id } })),
    edges: [
      { data: { source: "alice", target: "carol" } },
      { data: { source: "bob", target: "carol" } },
      { data: { source: "alice", target: "dave" } },
      { data: { source: "bob", target: "dave" } },
    ],
  });

  const aliceAndBob = edges.filter(
    ({ data }) => data.source === "alice" && data.target === "bob"
  );

  assert.equal(aliceAndBob.length, 1);
  assert.equal(aliceAndBob[0].data.weight, 2);
  assert.ok(aliceAndBob.every(({ data }) => data.layout_only === "true"));
});

test("similarity strength has a stable ceiling", () => {
  const commonAccounts = ["carol", "dave", "erin", "frank"];
  const edges = similarityEdges({
    nodes: ["alice", "bob", ...commonAccounts].map((id) => ({ data: { id } })),
    edges: commonAccounts.flatMap((account) => [
      { data: { source: "alice", target: account } },
      { data: { source: "bob", target: account } },
    ]),
  });

  const aliceAndBob = edges.find(
    ({ data }) => data.source === "alice" && data.target === "bob"
  );

  assert.equal(aliceAndBob.data.weight, 3);
});

test("large graphs use the fast overview layout", () => {
  const context = vm.createContext({
    document: { querySelector: () => ({ textContent: "" }) },
    window: { location: { protocol: "file:" } },
  });
  vm.runInContext(source, context);

  const result = JSON.parse(
    vm.runInContext(
      "JSON.stringify([usesFastLayout({nodes: Array(301), edges: []}), usesFastLayout({nodes: [], edges: Array(1001)}), usesFastLayout({nodes: Array(300), edges: Array(1000)})])",
      context
    )
  );

  assert.deepEqual(result, [true, true, false]);
});
