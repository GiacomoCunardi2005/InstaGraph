const graphElement = document.querySelector("#graph");
const statusElement = document.querySelector("#status");
const nodeSize = 30;
const labelSize = 11;
const labelOutline = 2;
let currentElements = "";
let cy;

// ponytail: skip high-degree hubs; add a scalable similarity index if hub similarity matters.
const MAX_COMMON_NEIGHBORS = 24;
const MAX_SIMILARITY_EDGES = 2000;
// ponytail: cap shared-neighbor force at three; add a tuned force model if dense clusters need finer separation.
const MAX_SIMILARITY_WEIGHT = 3;

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
      width: 1.5,
    },
  },
  {
    selector: 'edge[bond_type = "double"]',
    style: { "line-color": "#64d39a", "target-arrow-shape": "none", width: 3 },
  },
  {
    selector: 'edge[layout_only = "true"]',
    style: { opacity: 0, events: "no", "target-arrow-shape": "none" },
  },
];

function keepNodeScreenSize() {
  const scale = 1 / cy.zoom();
  cy.nodes().style({
    width: nodeSize * scale,
    height: nodeSize * scale,
    "font-size": labelSize * scale,
    "text-outline-width": labelOutline * scale,
  });
}

function similarityEdges(elements) {
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
      }
    }
  }
  return [...edges.values()];
}

function draw(graph) {
  const elements = JSON.stringify(graph.elements);
  if (elements === currentElements) return;
  currentElements = elements;

  const layoutElements = {
    nodes: graph.elements.nodes,
    edges: [...graph.elements.edges, ...similarityEdges(graph.elements)],
  };

  if (!cy) {
    cy = cytoscape({ container: graphElement, elements: layoutElements, style });
    cy.on("zoom", keepNodeScreenSize);
  } else {
    cy.elements().remove();
    cy.add(layoutElements);
  }
  cy.layout({
    name: "cose",
    animate: false,
    padding: 32,
    gravity: 1.2,
    idealEdgeLength: (edge) => 96 / edge.data("weight"),
    edgeElasticity: (edge) => 32 / edge.data("weight"),
  }).run();
  keepNodeScreenSize();
  statusElement.textContent = `${graph.elements.nodes.length} account · ${graph.elements.edges.length} legami`;
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
