import json
import tempfile
import unittest
from importlib import resources
from pathlib import Path
from unittest.mock import patch

from instagraph import GraphStore
from instagraph.__main__ import ViewerRequestHandler, import_folder, viewer_directory


class CommandTests(unittest.TestCase):
    def test_viewer_disables_browser_cache(self):
        handler = object.__new__(ViewerRequestHandler)
        headers = []
        handler.request_version = "HTTP/1.1"
        handler._headers_buffer = []
        handler.send_header = lambda name, value: headers.append((name, value))
        handler.flush_headers = lambda: None

        handler.end_headers()

        self.assertEqual(headers, [("Cache-Control", "no-store")])

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
                (viewer / "app.js").write_text("stale", encoding="utf-8")
                self.assertEqual(viewer_directory(), viewer)
                self.assertEqual(
                    (viewer / "app.js").read_text(encoding="utf-8"),
                    resources.files("instagraph.web").joinpath("app.js").read_text(encoding="utf-8"),
                )
                self.assertTrue((viewer / "graph.json").is_file())
                with GraphStore(viewer.parent / "instagraph.sqlite3") as store:
                    self.assertEqual(store.usernames(), {"root", "alice"})


if __name__ == "__main__":
    unittest.main()
