import unittest
from importlib import resources


class WebAssetsTests(unittest.TestCase):
    def test_viewer_is_local_and_polls_the_export(self):
        assets = resources.files("instagraph.web")
        app = assets.joinpath("app.js").read_text(encoding="utf-8")
        page = assets.joinpath("index.html").read_text(encoding="utf-8")

        self.assertIn('fetch("graph.json"', app)
        self.assertIn("setInterval(refresh, 2000)", app)
        self.assertIn("vendor/cytoscape.min.js", page)
        self.assertNotIn("http://", app + page)
        self.assertNotIn("https://", app + page)


if __name__ == "__main__":
    unittest.main()
