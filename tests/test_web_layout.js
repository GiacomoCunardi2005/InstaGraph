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

function leafLayout(elements) {
  const context = vm.createContext({
    document: { querySelector: () => ({ textContent: "" }) },
    window: { location: { protocol: "file:" } },
  });
  vm.runInContext(source, context);
  return JSON.parse(
    vm.runInContext(
      `(() => {
        const elements = ${JSON.stringify(elements)};
        const degrees = bondDegrees(elements);
        const leaves = singleBondLeaves(elements, degrees);
        return JSON.stringify({
          leaves: [...leaves],
          degrees: [...degrees],
          edges: similarityEdges(elements, leaves),
        });
      })()`,
      context
    )
  );
}

function marginPositions(bounds, indexes) {
  const context = vm.createContext({
    document: { querySelector: () => ({ textContent: "" }) },
    window: { location: { protocol: "file:" } },
  });
  vm.runInContext(source, context);
  return JSON.parse(
    vm.runInContext(
      `JSON.stringify(${JSON.stringify(indexes)}.map((index) => leafMarginPosition(index, ${JSON.stringify(bounds)})))`,
      context
    )
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

test("single-bond leaves stay outside similarity clusters", () => {
  const result = leafLayout({
    nodes: ["hub", "alice", "bob", "carol"].map((id) => ({ data: { id } })),
    edges: [
      { data: { source: "hub", target: "alice", bond_type: "single" } },
      { data: { source: "hub", target: "bob", bond_type: "single" } },
      { data: { source: "hub", target: "carol", bond_type: "double" } },
    ],
  });

  assert.deepEqual(result.leaves.sort(), ["alice", "bob"]);
  assert.deepEqual(Object.fromEntries(result.degrees), {
    hub: 3,
    alice: 1,
    bob: 1,
    carol: 1,
  });
  assert.equal(result.edges.length, 0);
});

test("single-bond leaves occupy distinct margin slots", () => {
  const bounds = { x1: 0, x2: 192, y1: 0, y2: 192 };
  const positions = marginPositions(bounds, [0, 8, 16, 24, 32]);

  assert.equal(new Set(positions.map(({ x, y }) => `${x},${y}`)).size, positions.length);
  assert.ok(positions.every(({ x, y }) => x < bounds.x1 || x > bounds.x2 || y < bounds.y1 || y > bounds.y2));
});

test("large graphs skip only derived similarity edges", () => {
  const context = vm.createContext({
    document: { querySelector: () => ({ textContent: "" }) },
    window: { location: { protocol: "file:" } },
  });
  vm.runInContext(source, context);

  const result = JSON.parse(
    vm.runInContext(
      "JSON.stringify([skipsSimilarityEdges({nodes: Array(301), edges: []}), skipsSimilarityEdges({nodes: [], edges: Array(1001)}), skipsSimilarityEdges({nodes: Array(300), edges: Array(1000)})])",
      context
    )
  );

  assert.deepEqual(result, [true, true, false]);
});
