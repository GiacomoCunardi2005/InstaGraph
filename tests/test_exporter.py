import json
import tempfile
import unittest
from pathlib import Path

from instagraph import GraphStore, import_edges
from instagraph.exporter import export_graph


class ExporterTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_export_is_private_stable_and_represents_bonds(self):
        destination = self.directory / "graph.json"
        destination.write_text("stale", encoding="utf-8")
        destination.chmod(0o644)
        with GraphStore(self.directory / "graph.sqlite3") as store:
            import_edges(
                store,
                "authorized export",
                [
                    {"source": "zoe", "target": "root"},
                    {"source": "zoe", "target": "alice"},
                    {"source": "alice", "target": "zoe"},
                ],
                accounts=["isolated"],
            )

            self.assertEqual(export_graph(store, destination), destination)
            first_export = destination.read_text(encoding="utf-8")
            self.assertEqual(export_graph(store, destination), destination)

        graph = json.loads(first_export)
        self.assertEqual(destination.read_text(encoding="utf-8"), first_export)
        self.assertEqual(
            graph,
            {
                "version": 1,
                "elements": {
                    "nodes": [
                        {"data": {"id": "alice", "label": "alice", "status": "imported"}},
                        {"data": {"id": "isolated", "label": "isolated", "status": "imported"}},
                        {"data": {"id": "root", "label": "root", "status": "imported"}},
                        {"data": {"id": "zoe", "label": "zoe", "status": "imported"}},
                    ],
                    "edges": [
                        {
                            "data": {
                                "id": "alice--zoe",
                                "source": "alice",
                                "target": "zoe",
                                "bond_type": "double",
                                "weight": 2,
                            }
                        },
                        {
                            "data": {
                                "id": "root--zoe",
                                "source": "zoe",
                                "target": "root",
                                "bond_type": "single",
                                "weight": 1,
                            }
                        },
                    ],
                },
            },
        )
        self.assertEqual(destination.stat().st_mode & 0o777, 0o600)
        self.assertTrue((self.directory / "index.html").is_file())
        self.assertTrue((self.directory / "app.js").is_file())
        self.assertTrue((self.directory / "vendor" / "cytoscape.min.js").is_file())
        self.assertTrue((self.directory / "vendor" / "CYTOSCAPE-LICENSE").is_file())


if __name__ == "__main__":
    unittest.main()
