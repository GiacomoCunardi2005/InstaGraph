import tempfile
import unittest
from pathlib import Path

from instagraph import GraphStore, import_edges
from instagraph.graph_tools import (
    find_path,
    get_account,
    get_community,
    get_neighbors,
    graph_summary,
)


class GraphToolsTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.store = GraphStore(Path(self.temporary_directory.name) / "graph.sqlite3")
        import_edges(
            self.store,
            "authorized export",
            [
                {"source": "root", "target": "alice"},
                {"source": "alice", "target": "root"},
                {"source": "root", "target": "bob"},
                {"source": "carol", "target": "root"},
                {"source": "bob", "target": "carol"},
                {"source": "carol", "target": "dave"},
                {"source": "dave", "target": "erin"},
                {"source": "erin", "target": "frank"},
                {"source": "frank", "target": "grace"},
                {"source": "grace", "target": "heidi"},
                {"source": "heidi", "target": "ivy"},
            ],
            accounts=["isolated"],
        )

    def tearDown(self):
        self.store.close()
        self.temporary_directory.cleanup()

    def test_get_neighbors_obeys_direction_and_sorts(self):
        self.assertEqual(
            get_neighbors(self.store, " @Root ", "following"),
            {
                "username": "root",
                "direction": "following",
                "found": True,
                "following": ["alice", "bob"],
            },
        )
        self.assertEqual(
            get_neighbors(self.store, "root", "followers"),
            {
                "username": "root",
                "direction": "followers",
                "found": True,
                "followers": ["alice", "carol"],
            },
        )
        self.assertEqual(
            get_neighbors(self.store, "root", "both"),
            {
                "username": "root",
                "direction": "both",
                "found": True,
                "following": ["alice", "bob"],
                "followers": ["alice", "carol"],
            },
        )
        with self.assertRaises(ValueError):
            get_neighbors(self.store, "root", "outgoing")

    def test_find_path_handles_cycles_and_six_edge_cap(self):
        self.assertEqual(
            find_path(self.store, "root", "frank"),
            {
                "start": "root",
                "target": "frank",
                "found": True,
                "path": ["root", "carol", "dave", "erin", "frank"],
            },
        )
        self.assertEqual(
            find_path(self.store, "root", "heidi"),
            {
                "start": "root",
                "target": "heidi",
                "found": True,
                "path": ["root", "carol", "dave", "erin", "frank", "grace", "heidi"],
            },
        )
        self.assertEqual(
            find_path(self.store, "root", "ivy"),
            {"start": "root", "target": "ivy", "found": False, "path": []},
        )

    def test_unknowns_are_empty_and_input_is_normalized(self):
        self.assertEqual(
            get_account(self.store, " @missing "),
            {"username": "missing", "found": False},
        )
        self.assertEqual(
            get_neighbors(self.store, "missing", "both"),
            {
                "username": "missing",
                "direction": "both",
                "found": False,
                "following": [],
                "followers": [],
            },
        )
        self.assertEqual(
            find_path(self.store, "root", "missing"),
            {"start": "root", "target": "missing", "found": False, "path": []},
        )
        with self.assertRaises(ValueError):
            get_account(self.store, "not valid")

    def test_community_is_an_explicitly_labeled_connected_component(self):
        community = get_community(self.store, "root")

        self.assertEqual(community["method"], "connected_component")
        self.assertEqual(community["member_count"], 10)
        self.assertEqual(
            community["members"],
            [
                "alice",
                "bob",
                "carol",
                "dave",
                "erin",
                "frank",
                "grace",
                "heidi",
                "ivy",
                "root",
            ],
        )
        self.assertFalse(community["truncated"])
        self.assertEqual(get_community(self.store, "missing"), {"username": "missing", "found": False})

    def test_community_caps_members_without_losing_the_full_count(self):
        import_edges(
            self.store,
            "authorized export",
            [{"source": "root", "target": f"member{index}"} for index in range(100)],
        )

        community = get_community(self.store, "root")

        self.assertEqual(community["member_count"], 110)
        self.assertEqual(len(community["members"]), 100)
        self.assertTrue(community["truncated"])
        self.assertEqual(community["members"], sorted(community["members"]))

    def test_summary_and_queries_do_not_mutate_the_graph(self):
        before = (self.store.usernames(), self.store.edges(), self.store.import_runs())

        self.assertEqual(
            get_account(self.store, "root"),
            {
                "username": "root",
                "found": True,
                "following_count": 2,
                "followers_count": 2,
            },
        )
        get_neighbors(self.store, "root", "both")
        find_path(self.store, "root", "frank")
        get_community(self.store, "root")
        self.assertEqual(
            graph_summary(self.store),
            {
                "account_count": 11,
                "directed_edge_count": 11,
                "single_bond_count": 9,
                "double_bond_count": 1,
                "latest_import_status": "completed",
            },
        )
        with GraphStore(":memory:") as empty:
            self.assertIsNone(graph_summary(empty)["latest_import_status"])
        self.assertEqual(before, (self.store.usernames(), self.store.edges(), self.store.import_runs()))


if __name__ == "__main__":
    unittest.main()
