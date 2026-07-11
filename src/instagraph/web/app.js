const graphElement = document.querySelector("#graph");
const statusElement = document.querySelector("#status");
let currentElements = "";
let cy;

const style = [
  {
    selector: "node",
    style: {
      "background-color": "#4f8cff",
      color: "#e9edf5",
      label: "data(label)",
      "font-size": 11,
      "text-outline-color": "#101217",
      "text-outline-width": 2,
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
];

function draw(graph) {
  const elements = JSON.stringify(graph.elements);
  if (elements === currentElements) return;
  currentElements = elements;

  if (!cy) {
    cy = cytoscape({ container: graphElement, elements: graph.elements, style });
  } else {
    cy.elements().remove();
    cy.add(graph.elements);
  }
  cy.layout({ name: "cose", animate: false, padding: 32 }).run();
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
