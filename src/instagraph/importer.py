"""Deterministic imports from a user-selected, authorized local data source."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import json
from pathlib import Path

from .exporter import export_graph
from .store import DirectedEdge, GraphStore, ImportRun


JSON_IMPORT_VERSION = 1
JSON_IMPORT_KEYS = {"version", "accounts", "follows"}
MAX_IMPORT_BYTES = 10 * 1024 * 1024
MAX_INPUT_ENTRIES = 100_000


@dataclass(frozen=True)
class RejectedEntry:
    """A validation error without retaining the supplied username or relationship."""

    kind: str
    index: int | None
    reason: str


@dataclass(frozen=True)
class ImportReport:
    """The result of one deterministic local import."""

    run: ImportRun
    rejected: tuple[RejectedEntry, ...]

    @property
    def added_edges(self) -> int:
        return self.run.added_edges


def import_edges(
    store: GraphStore,
    source: str,
    entries: Iterable[Mapping[str, object]],
    *,
    accounts: Iterable[str] = (),
    max_nodes: int = 10_000,
    max_edges: int = 50_000,
    max_input_entries: int = MAX_INPUT_ENTRIES,
) -> ImportReport:
    """Validate and import directed ``source`` → ``target`` edge mappings.

    ``source`` identifies the authorized origin chosen by the user. Invalid data
    is reported by position, duplicate edges are ignored, and a limit rejection
    changes no graph data. This module never gathers data from Instagram or a
    browser.
    """
    if min(max_nodes, max_edges, max_input_entries) < 0:
        raise ValueError("import limits must be non-negative")
    if isinstance(entries, (str, bytes)) or isinstance(accounts, (str, bytes)):
        raise TypeError("accounts and entries must be iterables, not strings")

    try:
        (
            normalized_accounts,
            account_rejections,
            input_duplicate_accounts,
            account_entry_count,
        ) = _normalize_accounts(accounts, max_input_entries)
        edge_entries, edge_rejections, input_duplicate_edges = _normalize_edges(
            entries,
            max_input_entries - account_entry_count,
        )
    except _InputLimitExceeded:
        return _document_rejection(
            store,
            source,
            f"import exceeds the {max_input_entries} input-entry limit",
        )
    normalized_edges = [edge for edge, _ in edge_entries]
    rejected = account_rejections + edge_rejections
    accounts_to_write = _accounts_to_write(normalized_accounts, edge_entries)

    existing_edges = store.edge_set()
    new_edges = [edge for edge in normalized_edges if edge not in existing_edges]
    existing_nodes = store.usernames()
    new_nodes = set(accounts_to_write) - existing_nodes

    if len(existing_edges) + len(new_edges) > max_edges:
        return _limit_report(
            store,
            source,
            rejected,
            normalized_accounts,
            edge_entries,
            f"import would exceed the {max_edges} edge limit",
        )
    if len(existing_nodes) + len(new_nodes) > max_nodes:
        return _limit_report(
            store,
            source,
            rejected,
            normalized_accounts,
            edge_entries,
            f"import would exceed the {max_nodes} node limit",
        )

    run = store.record_import(
        source,
        accounts_to_write,
        normalized_edges,
        input_duplicate_accounts=input_duplicate_accounts,
        input_duplicate_edges=input_duplicate_edges,
        rejected_entries=len(rejected),
    )
    if store.database_path != ":memory:":
        export_graph(store, Path(store.database_path).parent / "web" / "graph.json")
    return ImportReport(run=run, rejected=tuple(rejected))


def import_json_file(
    store: GraphStore,
    path: str | Path,
    *,
    source: str | None = None,
    max_nodes: int = 10_000,
    max_edges: int = 50_000,
    max_file_bytes: int = MAX_IMPORT_BYTES,
    max_input_entries: int = MAX_INPUT_ENTRIES,
) -> ImportReport:
    """Import a strict local JSON v1 document selected by the user.

    Its schema is ``{\"version\": 1, \"accounts\": [...], \"follows\": [...]}``.
    The audit source comes from the selected filename or explicit ``source``, not
    from untrusted document contents.
    """
    if max_file_bytes < 0:
        raise ValueError("max_file_bytes must be non-negative")
    selected_path = Path(path)
    audit_source = source or _file_source(selected_path)
    try:
        with selected_path.open("rb") as file:
            contents = file.read(max_file_bytes + 1)
        if len(contents) > max_file_bytes:
            return _document_rejection(
                store,
                audit_source,
                f"file exceeds the {max_file_bytes} byte limit",
            )
        payload = json.loads(contents)
    except (OSError, UnicodeError, json.JSONDecodeError):
        return _document_rejection(store, audit_source, "file is not valid UTF-8 JSON")

    if not isinstance(payload, Mapping) or set(payload) != JSON_IMPORT_KEYS:
        return _document_rejection(
            store,
            audit_source,
            "JSON must contain exactly version, accounts, and follows",
        )
    if type(payload["version"]) is not int or payload["version"] != JSON_IMPORT_VERSION:
        return _document_rejection(store, audit_source, "unsupported JSON import version")
    if not isinstance(payload["accounts"], list) or not isinstance(payload["follows"], list):
        return _document_rejection(store, audit_source, "accounts and follows must be lists")

    return import_edges(
        store,
        audit_source,
        payload["follows"],
        accounts=payload["accounts"],
        max_nodes=max_nodes,
        max_edges=max_edges,
        max_input_entries=max_input_entries,
    )


def _normalize_accounts(
    accounts: Iterable[str],
    max_entries: int,
) -> tuple[list[tuple[str, int]], list[RejectedEntry], int, int]:
    normalized: list[tuple[str, int]] = []
    rejected: list[RejectedEntry] = []
    seen: set[str] = set()
    input_duplicates = 0
    entry_count = 0
    for index, account in enumerate(accounts):
        if entry_count >= max_entries:
            raise _InputLimitExceeded
        entry_count += 1
        try:
            username = GraphStore.normalize_username(account)
        except (TypeError, ValueError):
            rejected.append(RejectedEntry("account", index, "invalid username"))
        else:
            if username not in seen:
                seen.add(username)
                normalized.append((username, index))
            else:
                input_duplicates += 1
    return normalized, rejected, input_duplicates, entry_count


def _normalize_edges(
    entries: Iterable[Mapping[str, object]],
    max_entries: int,
) -> tuple[list[tuple[DirectedEdge, int]], list[RejectedEntry], int]:
    normalized: list[tuple[DirectedEdge, int]] = []
    rejected: list[RejectedEntry] = []
    seen: set[DirectedEdge] = set()
    input_duplicates = 0
    for index, entry in enumerate(entries):
        if index >= max_entries:
            raise _InputLimitExceeded
        edge, reason = _validate_edge(entry)
        if reason is not None:
            rejected.append(RejectedEntry("follow", index, reason))
        elif edge in seen:
            input_duplicates += 1
        else:
            seen.add(edge)
            normalized.append((edge, index))
    return normalized, rejected, input_duplicates


def _accounts_to_write(
    normalized_accounts: list[tuple[str, int]],
    normalized_edges: list[tuple[DirectedEdge, int]],
) -> list[str]:
    accounts: list[str] = []
    seen: set[str] = set()
    for username, _ in normalized_accounts:
        if username not in seen:
            seen.add(username)
            accounts.append(username)
    for edge, _ in normalized_edges:
        for username in (edge.source, edge.target):
            if username not in seen:
                seen.add(username)
                accounts.append(username)
    return accounts


def _validate_edge(entry: object) -> tuple[DirectedEdge | None, str | None]:
    if not isinstance(entry, Mapping) or set(entry) != {"source", "target"}:
        return None, "entry must contain only source and target"
    try:
        source = GraphStore.normalize_username(entry["source"])
        target = GraphStore.normalize_username(entry["target"])
    except (TypeError, ValueError):
        return None, "source and target must be valid usernames"
    if source == target:
        return None, "self-follow edges are not allowed"
    return DirectedEdge(source, target), None


def _limit_report(
    store: GraphStore,
    source: str,
    rejected: list[RejectedEntry],
    normalized_accounts: list[tuple[str, int]],
    normalized_edges: list[tuple[DirectedEdge, int]],
    reason: str,
) -> ImportReport:
    rejected = [*rejected]
    rejected.extend(
        RejectedEntry("account", index, reason) for _, index in normalized_accounts
    )
    rejected.extend(RejectedEntry("follow", index, reason) for _, index in normalized_edges)
    run = store.record_rejected_import(source, len(rejected), reason)
    return ImportReport(run=run, rejected=tuple(rejected))


def _document_rejection(store: GraphStore, source: str, reason: str) -> ImportReport:
    run = store.record_rejected_import(source, 1, reason)
    return ImportReport(
        run=run,
        rejected=(RejectedEntry("document", None, reason),),
    )


def _file_source(path: Path) -> str:
    return f"file:{path.name or 'selected-export'}"


class _InputLimitExceeded(Exception):
    pass
