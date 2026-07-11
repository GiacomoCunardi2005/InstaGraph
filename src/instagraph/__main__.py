"""Small local commands for importing reviewed JSON exports and viewing a graph."""

from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .exporter import _install_viewer
from .importer import ImportReport, import_json_file
from .store import GraphStore


class ViewerRequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def import_folder(directory: str | Path) -> tuple[Path, tuple[ImportReport, ...]]:
    """Import immediate, regular JSON files from one user-selected directory."""
    folder = Path(directory).expanduser()
    if not folder.is_dir():
        raise ValueError("choose an existing export directory")
    try:
        paths = sorted(
            path for path in folder.iterdir()
            if path.is_file() and not path.is_symlink() and path.suffix.lower() == ".json"
        )
    except OSError as error:
        raise ValueError("cannot read the selected export directory") from error
    if not paths:
        raise ValueError("the selected directory has no JSON files")

    with GraphStore() as store:
        reports = tuple(import_json_file(store, path) for path in paths)
        viewer = Path(store.database_path).parent / "web"
    return viewer, reports


def viewer_directory() -> Path:
    """Return the default store's local viewer directory after an import."""
    with GraphStore() as store:
        viewer = Path(store.database_path).parent / "web"
    if not (viewer / "graph.json").is_file():
        raise ValueError("no local graph yet; import a JSON export first")
    _install_viewer(viewer)
    return viewer


def serve_viewer(viewer: Path) -> None:
    """Serve the private viewer only on the local loopback interface."""
    handler = partial(ViewerRequestHandler, directory=str(viewer))
    with ThreadingHTTPServer(("127.0.0.1", 8000), handler) as server:
        print("Open http://127.0.0.1:8000/ and press Ctrl+C when finished.")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m instagraph")
    commands = parser.add_subparsers(dest="command", required=True)
    import_command = commands.add_parser("import-folder", help="import immediate JSON files")
    import_command.add_argument("folder", help="directory containing reviewed JSON exports")
    commands.add_parser("view", help="serve the local graph viewer")
    arguments = parser.parse_args(argv)

    try:
        if arguments.command == "import-folder":
            viewer, reports = import_folder(arguments.folder)
            for report in reports:
                print(
                    f"{report.run.source}: {report.run.status} "
                    f"(+{report.run.added_accounts} accounts, +{report.run.added_edges} edges)"
                )
            if (viewer / "graph.json").is_file():
                print(f"Viewer ready: {viewer}")
            else:
                print("No graph created; review the rejected files above.")
            return 0
        serve_viewer(viewer_directory())
        return 0
    except (OSError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    raise SystemExit(main())
