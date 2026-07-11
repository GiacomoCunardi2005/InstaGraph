import unittest
from importlib import resources


class WebAssetsTests(unittest.TestCase):
    def test_viewer_is_local_and_polls_the_export(self):
        assets = resources.files("instagraph.web")
        app = assets.joinpath("app.js").read_text(encoding="utf-8")
        page = assets.joinpath("index.html").read_text(encoding="utf-8")

        self.assertIn('fetch("graph.json"', app)
        self.assertIn("setInterval(refresh, 2000)", app)
        self.assertIn("gravity: 1.2", app)
        self.assertIn('idealEdgeLength: (edge) => 96 / edge.data("weight")', app)
        self.assertIn('edgeElasticity: (edge) => 32 / edge.data("weight")', app)
        self.assertIn("vendor/cytoscape.min.js", page)
        self.assertNotIn("http://", app + page)
        self.assertNotIn("https://", app + page)

    def test_viewer_keeps_nodes_and_labels_constant_while_zooming(self):
        app = resources.files("instagraph.web").joinpath("app.js").read_text(encoding="utf-8")

        self.assertIn('cy.on("zoom", keepNodeScreenSize)', app)
        self.assertIn("const scale = 1 / cy.zoom()", app)
        self.assertIn("width: nodeSize * scale", app)
        self.assertIn("height: nodeSize * scale", app)
        self.assertIn('"font-size": labelSize * scale', app)
        self.assertIn('"text-outline-width": labelOutline * scale', app)
        self.assertIn("keepNodeScreenSize();", app)


if __name__ == "__main__":
    unittest.main()
