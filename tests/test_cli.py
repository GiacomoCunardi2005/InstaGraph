import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from instagraph import GraphStore
from instagraph.__main__ import import_folder, viewer_directory


class CommandTests(unittest.TestCase):
    def test_import_folder_uses_only_immediate_json_files(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            exports = root / "exports"
            exports.mkdir()
            (exports / "a.json").write_text(
                json.dumps(
                    {
                        "version": 1,
                        "accounts": ["root"],
                        "follows": [{"source": "root", "target": "alice"}],
                    }
                ),
                encoding="utf-8",
            )
            (exports / "b.json").write_text("not JSON", encoding="utf-8")
            (exports / "ignored.txt").write_text("not an export", encoding="utf-8")
            nested = exports / "nested"
            nested.mkdir()
            (nested / "ignored.json").write_text("{}", encoding="utf-8")

            with patch.dict("os.environ", {"XDG_DATA_HOME": str(root / "data")}):
                viewer, reports = import_folder(exports)
                self.assertEqual([report.run.status for report in reports], ["completed", "rejected"])
                self.assertEqual(viewer_directory(), viewer)
                self.assertTrue((viewer / "graph.json").is_file())
                with GraphStore(viewer.parent / "instagraph.sqlite3") as store:
                    self.assertEqual(store.usernames(), {"root", "alice"})


if __name__ == "__main__":
    unittest.main()
