const graphElement = document.querySelector("#graph");
const statusElement = document.querySelector("#status");
const nodeSize = 6;
const labelSize = 11;
const labelOutline = 2;
let currentElements = "";
let cy;

// ponytail: skip high-degree hubs; add a scalable similarity index if hub similarity matters.
const MAX_COMMON_NEIGHBORS = 24;
const MAX_SIMILARITY_EDGES = 500;
// ponytail: cap shared-neighbor force at three; add a tuned force model if dense clusters need finer separation.
const MAX_SIMILARITY_WEIGHT = 3;
// ponytail: skip derived similarity springs above these caps; add a worker layout if CoSE becomes slow.
const MAX_SIMILARITY_LAYOUT_NODES = 300;
const MAX_SIMILARITY_LAYOUT_EDGES = 1000;
const LEAF_MARGIN = 320;
const LEAF_SPACING = 96;

const style = [
  {
    selector: "node",
    style: {
      "background-color": "#4f8cff",
      color: "#e9edf5",
      label: "data(label)",
      width: nodeSize,
      height: nodeSize,
      "font-size": labelSize,
      "min-zoomed-font-size": 8,
      "text-outline-color": "#101217",
      "text-outline-width": labelOutline,
    },
  },
  { selector: 'node[status = "partial"]', style: { "background-color": "#e5a436" } },
  { selector: 'node[status = "rejected"]', style: { "background-color": "#d85757" } },
  {
    selector: 'edge[bond_type = "single"]',
    style: {
      "curve-style": "bezier",
      "line-color": "#7b8ba3",
      "target-arrow-color": "#7b8ba3",
      "target-arrow-shape": "triangle",
      opacity: 0.3,
      width: 1.5,
    },
  },
  {
    selector: 'edge[bond_type = "double"]',
    style: { "line-color": "#64d39a", "target-arrow-shape": "none", opacity: 0.3, width: 3 },
  },
  {
    selector: 'edge[layout_only = "true"]',
    style: { opacity: 0, events: "no", "target-arrow-shape": "none" },
  },
];

function keepNodeScreenSize() {
  const zoom = cy.zoom();
  const nodeScale = 1 / zoom;
  const labelScale = 1 / Math.max(1, zoom);
  cy.nodes().style({
    width: nodeSize * nodeScale,
    height: nodeSize * nodeScale,
    "font-size": labelSize * labelScale,
    "text-outline-width": labelOutline * labelScale,
  });
}

function bondDegrees(elements) {
  const degree = new Map(elements.nodes.map(({ data }) => [data.id, 0]));
  for (const { data } of elements.edges) {
    degree.set(data.source, degree.get(data.source) + 1);
    degree.set(data.target, degree.get(data.target) + 1);
  }
  return degree;
}

function singleBondLeaves(elements, degree = bondDegrees(elements)) {
  const leaves = new Set();
  for (const { data } of elements.edges) {
    if (data.bond_type !== "single") continue;
    if (degree.get(data.source) === 1) leaves.add(data.source);
    if (degree.get(data.target) === 1) leaves.add(data.target);
  }
  return leaves;
}

function leafMarginPosition(index, bounds) {
  const left = bounds.x1 - LEAF_MARGIN;
  const right = bounds.x2 + LEAF_MARGIN;
  const top = bounds.y1 - LEAF_MARGIN;
  const bottom = bounds.y2 + LEAF_MARGIN;
  const horizontalSlots = Math.max(1, Math.floor((right - left) / LEAF_SPACING));
  const verticalSlots = Math.max(1, Math.floor((bottom - top) / LEAF_SPACING));
  const slotsPerLayer = 2 * (horizontalSlots + verticalSlots);
  const layer = Math.floor(index / slotsPerLayer);
  let slot = index % slotsPerLayer;
  const offset = layer * LEAF_SPACING;

  if (slot < horizontalSlots) {
    return { x: left + (slot + 0.5) * LEAF_SPACING, y: top - offset };
  }
  slot -= horizontalSlots;
  if (slot < verticalSlots) {
    return { x: right + offset, y: top + (slot + 0.5) * LEAF_SPACING };
  }
  slot -= verticalSlots;
  if (slot < horizontalSlots) {
    return { x: right - (slot + 0.5) * LEAF_SPACING, y: bottom + offset };
  }
  return {
    x: left - offset,
    y: bottom - (slot - horizontalSlots + 0.5) * LEAF_SPACING,
  };
}

function placeLeaves(cy, leafIds) {
  const leaves = cy.nodes().filter((node) => leafIds.has(node.id()));
  if (!leaves.length) return;
  const core = cy.nodes().filter((node) => !leafIds.has(node.id()));
  const bounds = core.length
    ? core.boundingBox()
    : { x1: -LEAF_MARGIN, x2: LEAF_MARGIN, y1: -LEAF_MARGIN, y2: LEAF_MARGIN };
  cy.batch(() => {
    leaves.forEach((node, index) => node.position(leafMarginPosition(index, bounds)));
  });
}

function similarityEdges(elements, excludedNodes = new Set()) {
  const neighbors = new Map(elements.nodes.map(({ data }) => [data.id, []]));
  for (const { data } of elements.edges) {
    neighbors.get(data.source).push(data.target);
    neighbors.get(data.target).push(data.source);
  }

  const edges = new Map();
  for (const accounts of neighbors.values()) {
    if (accounts.length > MAX_COMMON_NEIGHBORS) continue;
    for (let left = 0; left < accounts.length; left += 1) {
      for (let right = left + 1; right < accounts.length; right += 1) {
        const [source, target] =
          accounts[left] < accounts[right]
            ? [accounts[left], accounts[right]]
            : [accounts[right], accounts[left]];
        if (excludedNodes.has(source) || excludedNodes.has(target)) continue;
        const id = `similarity--${source}--${target}`;
        const similarity = edges.get(id);
        if (similarity) {
          similarity.data.weight = Math.min(
            MAX_SIMILARITY_WEIGHT,
            similarity.data.weight + 1
          );
          continue;
        }
        // ponytail: cap virtual edges to keep browser layouts responsive; add a scalable index if this limit matters.
        if (edges.size === MAX_SIMILARITY_EDGES) continue;
        edges.set(id, {
          data: {
            id,
            source,
            target,
            weight: 1,
            layout_only: "true",
          },
        });
        if (edges.size === MAX_SIMILARITY_EDGES) return [...edges.values()];
      }
    }
  }
  return [...edges.values()];
}

function skipsSimilarityEdges(elements) {
  return (
    elements.nodes.length > MAX_SIMILARITY_LAYOUT_NODES ||
    elements.edges.length > MAX_SIMILARITY_LAYOUT_EDGES
  );
}

function draw(graph) {
  const elements = JSON.stringify(graph.elements);
  if (elements === currentElements) return;
  currentElements = elements;

  const skipSimilarity = skipsSimilarityEdges(graph.elements);
  const degrees = bondDegrees(graph.elements);
  const distantLeaves = singleBondLeaves(graph.elements, degrees);
  const layoutElements = {
    nodes: graph.elements.nodes,
    edges: skipSimilarity
      ? graph.elements.edges
      : [...graph.elements.edges, ...similarityEdges(graph.elements, distantLeaves)],
  };

  if (!cy) {
    cy = cytoscape({ container: graphElement, elements: layoutElements, style });
    cy.on("zoom", keepNodeScreenSize);
  } else {
    cy.elements().remove();
    cy.add(layoutElements);
  }
  const layout = {
    name: "cose",
    animate: false,
    fit: false,
    padding: 32,
    componentSpacing: 112,
    gravity: 0.1,
    nodeRepulsion: (node) => 4096 / Math.sqrt(Math.max(1, degrees.get(node.id()))),
    idealEdgeLength: (edge) => 160 / edge.data("weight"),
    edgeElasticity: (edge) => 32 / edge.data("weight"),
    numIter: skipSimilarity ? 100 : 250,
  };
  const forceElements = cy.elements().filter((element) =>
    element.isNode()
      ? !distantLeaves.has(element.id())
      : !distantLeaves.has(element.source().id()) &&
        !distantLeaves.has(element.target().id())
  );
  if (forceElements.nodes().length) forceElements.layout(layout).run();
  placeLeaves(cy, distantLeaves);
  keepNodeScreenSize();
  statusElement.textContent = `${graph.elements.nodes.length} account · ${graph.elements.edges.length} legami · layout a forze`;
}

async function refresh() {
  try {
    const response = await fetch("graph.json", { cache: "no-store" });
    if (!response.ok) throw new Error(response.status);
    const graph = await response.json();
    if (graph.version !== 1 || !graph.elements) throw new Error("formato non valido");
    draw(graph);
  } catch (error) {
    statusElement.textContent = `In attesa di graph.json (${error.message})`;
  }
}

if (window.location.protocol === "file:") {
  statusElement.textContent = "Avvia un server locale: python -m http.server --bind 127.0.0.1 8000";
} else {
  refresh();
  setInterval(refresh, 2000);
}
