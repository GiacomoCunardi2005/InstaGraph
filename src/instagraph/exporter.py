"""Stable, local Cytoscape JSON export."""

from __future__ import annotations

from importlib import resources
import json
import os
from pathlib import Path
import shutil
import tempfile

from .store import Bond, GraphStore


def export_graph(store: GraphStore, path: str | Path) -> Path:
    """Atomically write a private Cytoscape graph derived from ``store``."""
    destination = Path(path).expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "elements": {
            "nodes": [
                {"data": {"id": username, "label": username, "status": "imported"}}
                for username in sorted(store.usernames())
            ],
            "edges": [
                {"data": _edge_data(bond)}
                for bond in sorted(
                    store.bonds(), key=lambda bond: (bond.account_a, bond.account_b)
                )
            ],
        },
    }
    descriptor, temporary_name = tempfile.mkstemp(
        dir=destination.parent, prefix=f".{destination.name}.", suffix=".tmp"
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            os.fchmod(output.fileno(), 0o600)
            json.dump(payload, output, ensure_ascii=False, indent=2, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary_path, destination)
        os.chmod(destination, 0o600)
    finally:
        temporary_path.unlink(missing_ok=True)
    _install_viewer(destination.parent)
    return destination


def _edge_data(bond: Bond) -> dict[str, str | int]:
    if bond.bond_type == "double" or bond.a_follows_b:
        source, target = bond.account_a, bond.account_b
    else:
        source, target = bond.account_b, bond.account_a
    return {
        "id": f"{bond.account_a}--{bond.account_b}",
        "source": source,
        "target": target,
        "bond_type": bond.bond_type,
        "weight": 2 if bond.bond_type == "double" else 1,
    }


def _install_viewer(directory: Path) -> None:
    assets = resources.files("instagraph.web")
    for relative_path in (
        "index.html",
        "app.js",
        "vendor/cytoscape.min.js",
        "vendor/CYTOSCAPE-LICENSE",
    ):
        source = assets.joinpath(*relative_path.split("/"))
        destination = directory.joinpath(*relative_path.split("/"))
        destination.parent.mkdir(parents=True, exist_ok=True)
        with resources.as_file(source) as source_path:
            shutil.copyfile(source_path, destination)
        os.chmod(destination, 0o644)
