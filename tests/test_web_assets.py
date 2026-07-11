import unittest
from importlib import resources


class WebAssetsTests(unittest.TestCase):
    def test_viewer_is_local_and_polls_the_export(self):
        assets = resources.files("instagraph.web")
        app = assets.joinpath("app.js").read_text(encoding="utf-8")
        page = assets.joinpath("index.html").read_text(encoding="utf-8")

        self.assertIn('fetch("graph.json"', app)
        self.assertIn("setInterval(refresh, 2000)", app)
        self.assertIn("gravity: 0.1", app)
        self.assertIn("function leafMarginPosition(index, bounds)", app)
        self.assertIn("function singleBondLeaves(elements, degree", app)
        self.assertIn("similarityEdges(graph.elements, distantLeaves)", app)
        self.assertIn("nodeRepulsion: (node) =>", app)
        self.assertIn("placeLeaves(cy, distantLeaves)", app)
        self.assertIn("fit: false", app)
        self.assertIn("layout a forze", app)
        self.assertIn("vendor/cytoscape.min.js", page)
        self.assertNotIn("http://", app + page)
        self.assertNotIn("https://", app + page)

    def test_viewer_keeps_nodes_and_labels_constant_while_zooming(self):
        app = resources.files("instagraph.web").joinpath("app.js").read_text(encoding="utf-8")

        self.assertIn('cy.on("zoom", keepNodeScreenSize)', app)
        self.assertIn("const nodeScale = 1 / zoom", app)
        self.assertIn("const labelScale = 1 / Math.max(1, zoom)", app)
        self.assertIn("width: nodeSize * nodeScale", app)
        self.assertIn("height: nodeSize * nodeScale", app)
        self.assertIn('"font-size": labelSize * labelScale', app)
        self.assertIn('"text-outline-width": labelOutline * labelScale', app)
        self.assertIn("keepNodeScreenSize();", app)

    def test_viewer_keeps_force_layout_for_large_graphs(self):
        app = resources.files("instagraph.web").joinpath("app.js").read_text(encoding="utf-8")

        self.assertIn("const nodeSize = 6", app)
        self.assertIn('"min-zoomed-font-size": 8', app)
        self.assertIn("function skipsSimilarityEdges(elements)", app)
        self.assertIn('name: "cose"', app)
        self.assertNotIn('name: "concentric"', app)
        self.assertIn("numIter: skipSimilarity ? 100 : 250", app)


if __name__ == "__main__":
    unittest.main()
