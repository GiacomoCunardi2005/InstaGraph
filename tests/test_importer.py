import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from instagraph import Bond, DirectedEdge, GraphStore, import_edges, import_json_file


class ImporterTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def make_store(self):
        return GraphStore(self.directory / "graph.sqlite3")

    def test_normalizes_deduplicates_and_derives_bonds(self):
        accounts = [" @Root ", "isolated", "@@broken", "x" * 31]
        entries = [
            {"source": " @Root ", "target": "Alice"},
            {"source": "alice", "target": "root"},
            {"source": "root", "target": "alice"},
            {"source": "root", "target": "root"},
            {"source": "with space", "target": "nobody"},
            {"source": "missing-target"},
        ]

        with self.make_store() as store:
            report = import_edges(
                store,
                "my authorized export",
                entries,
                accounts=accounts,
            )

            self.assertEqual(report.run.status, "partial")
            self.assertEqual(report.run.added_accounts, 3)
            self.assertEqual(report.added_edges, 2)
            self.assertEqual(report.run.duplicate_edges, 1)
            self.assertEqual(report.run.rejected_entries, 5)
            self.assertTrue(report.run.started_at)
            self.assertEqual(store.usernames(), {"root", "alice", "isolated"})
            self.assertEqual(
                store.edges(),
                [DirectedEdge("alice", "root"), DirectedEdge("root", "alice")],
            )
            self.assertEqual(
                store.bonds(),
                [Bond("alice", "root", True, True, "double")],
            )
            self.assertEqual(
                [(item.kind, item.index) for item in report.rejected],
                [
                    ("account", 2),
                    ("account", 3),
                    ("follow", 3),
                    ("follow", 4),
                    ("follow", 5),
                ],
            )
            self.assertFalse(hasattr(report.rejected[0], "value"))

    def test_reimport_is_repeatable_without_new_data(self):
        entries = [{"source": "root", "target": "alice"}]

        with self.make_store() as store:
            first = import_edges(store, "export", entries, accounts=["isolated"])
            second = import_edges(store, "export", entries, accounts=["isolated"])

            self.assertEqual(first.run.added_accounts, 3)
            self.assertEqual(first.added_edges, 1)
            self.assertEqual(second.run.added_accounts, 0)
            self.assertEqual(second.run.duplicate_accounts, 3)
            self.assertEqual(second.added_edges, 0)
            self.assertEqual(second.run.duplicate_edges, 1)
            self.assertEqual(store.edges(), [DirectedEdge("root", "alice")])
            self.assertEqual([run.status for run in store.import_runs()], ["completed", "completed"])

    def test_duplicate_account_declarations_are_audited(self):
        with self.make_store() as store:
            report = import_edges(store, "export", [], accounts=["alice", "@Alice"])

            self.assertEqual(report.run.added_accounts, 1)
            self.assertEqual(report.run.duplicate_accounts, 1)
            self.assertEqual(store.usernames(), {"alice"})

    def test_node_limit_rejection_keeps_the_graph_unchanged_and_is_audited(self):
        entries = [
            {"source": "root", "target": "alice"},
            {"source": "alice", "target": "bob"},
        ]

        with self.make_store() as store:
            report = import_edges(store, "export", entries, max_nodes=2)

            self.assertEqual(report.run.status, "rejected")
            self.assertEqual(report.added_edges, 0)
            self.assertEqual(store.edges(), [])
            self.assertEqual(store.usernames(), set())
            self.assertIn("2 node limit", report.run.stop_reason)
            self.assertEqual(report.run.rejected_entries, len(report.rejected))
            self.assertEqual(store.import_runs(), [report.run])

    def test_edge_limit_rejection_does_not_change_existing_graph(self):
        with self.make_store() as store:
            import_edges(store, "first export", [{"source": "root", "target": "alice"}])
            report = import_edges(
                store,
                "second export",
                [{"source": "alice", "target": "bob"}],
                max_edges=1,
            )

            self.assertEqual(report.run.status, "rejected")
            self.assertEqual(store.edges(), [DirectedEdge("root", "alice")])
            self.assertIn("1 edge limit", report.run.stop_reason)

    def test_imports_the_strict_local_json_shape_and_isolated_accounts(self):
        path = self.directory / "export.json"
        path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "accounts": ["root", "isolated"],
                    "follows": [{"source": "root", "target": "alice"}],
                }
            ),
            encoding="utf-8",
        )

        with self.make_store() as store:
            report = import_json_file(store, path, source="selected local export")

            self.assertEqual(report.run.source, "selected local export")
            self.assertEqual(report.run.added_accounts, 3)
            self.assertEqual(report.added_edges, 1)
            self.assertEqual(store.usernames(), {"root", "alice", "isolated"})
            graph_path = Path(store.database_path).parent / "web" / "graph.json"
            self.assertTrue(graph_path.is_file())
            self.assertEqual(graph_path.stat().st_mode & 0o777, 0o600)

    def test_malformed_document_is_audited_without_graph_mutation(self):
        path = self.directory / "broken.json"
        path.write_text("not JSON", encoding="utf-8")

        with self.make_store() as store:
            report = import_json_file(store, path)

            self.assertEqual(report.run.status, "rejected")
            self.assertEqual(report.run.source, "file:broken.json")
            self.assertEqual(report.run.rejected_entries, 1)
            self.assertEqual(store.edges(), [])
            self.assertEqual(store.import_runs(), [report.run])

    def test_unknown_json_schema_is_rejected_without_graph_mutation(self):
        path = self.directory / "wrong-schema.json"
        path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "accounts": [],
                    "follows": [],
                    "untrusted_metadata": "ignore me",
                }
            ),
            encoding="utf-8",
        )

        with self.make_store() as store:
            report = import_json_file(store, path)

            self.assertEqual(report.run.status, "rejected")
            self.assertIn("exactly version", report.run.stop_reason)
            self.assertEqual(store.usernames(), set())

    def test_file_and_input_entry_limits_are_rejected_before_import(self):
        path = self.directory / "too-large.json"
        path.write_text("{}", encoding="utf-8")

        with self.make_store() as store:
            file_report = import_json_file(store, path, max_file_bytes=1)
            input_report = import_edges(
                store,
                "export",
                [
                    {"source": "root", "target": "alice"},
                    {"source": "alice", "target": "bob"},
                ],
                max_input_entries=1,
            )

            self.assertEqual(file_report.run.status, "rejected")
            self.assertIn("byte limit", file_report.run.stop_reason)
            self.assertEqual(input_report.run.status, "rejected")
            self.assertIn("input-entry limit", input_report.run.stop_reason)
            self.assertEqual(store.edges(), [])

    def test_explicit_database_file_is_owner_only(self):
        path = self.directory / "private.sqlite3"

        with GraphStore(path):
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_default_database_uses_a_private_user_data_directory(self):
        data_home = self.directory / "data"

        with patch.dict("os.environ", {"XDG_DATA_HOME": str(data_home)}):
            with GraphStore() as store:
                path = Path(store.database_path)
                self.assertEqual(path, data_home / "instagraph" / "instagraph.sqlite3")
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)


if __name__ == "__main__":
    unittest.main()
