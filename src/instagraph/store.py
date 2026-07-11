"""SQLite persistence for a locally imported directed social graph."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import sqlite3


USERNAME_PATTERN = re.compile(r"[a-z0-9._]{1,30}\Z")


@dataclass(frozen=True, order=True)
class DirectedEdge:
    """One directed follow relationship supplied by an authorized source."""

    source: str
    target: str


@dataclass(frozen=True)
class Bond:
    """The display-only single/double view derived from directed edges."""

    account_a: str
    account_b: str
    a_follows_b: bool
    b_follows_a: bool
    bond_type: str


@dataclass(frozen=True)
class ImportRun:
    """A compact audit record for one local import attempt."""

    id: int
    source: str
    status: str
    added_accounts: int
    duplicate_accounts: int
    added_edges: int
    duplicate_edges: int
    rejected_entries: int
    started_at: str
    stop_reason: str | None


class GraphStore:
    """Store only usernames, directed edges, and local import audit records."""

    def __init__(self, path: str | Path | None = None) -> None:
        database_path = _default_database_path() if path is None else path
        self.database_path = str(database_path)
        if self.database_path == ":memory:":
            self.connection = sqlite3.connect(":memory:")
        else:
            file_path = Path(database_path).expanduser()
            file_path.parent.mkdir(parents=True, exist_ok=True)
            descriptor = os.open(file_path, os.O_RDWR | os.O_CREAT, 0o600)
            os.close(descriptor)
            os.chmod(file_path, 0o600)
            self.database_path = str(file_path)
            self.connection = sqlite3.connect(file_path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._create_schema()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "GraphStore":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @staticmethod
    def normalize_username(username: str) -> str:
        if not isinstance(username, str):
            raise TypeError("username must be a string")
        normalized = username.strip().casefold()
        if normalized.startswith("@"):
            normalized = normalized[1:]
        if not USERNAME_PATTERN.fullmatch(normalized):
            raise ValueError("username must use 1-30 letters, digits, dots, or underscores")
        return normalized

    def usernames(self) -> set[str]:
        rows = self.connection.execute("SELECT username FROM accounts").fetchall()
        return {str(row["username"]) for row in rows}

    def edges(self) -> list[DirectedEdge]:
        rows = self.connection.execute(
            "SELECT source_username, target_username FROM follow_edges "
            "ORDER BY source_username, target_username"
        ).fetchall()
        return [DirectedEdge(str(row[0]), str(row[1])) for row in rows]

    def edge_set(self) -> set[DirectedEdge]:
        return set(self.edges())

    def bonds(self) -> list[Bond]:
        rows = self.connection.execute(
            """
            WITH canonical AS (
                SELECT
                    CASE WHEN source_username < target_username
                         THEN source_username ELSE target_username END AS account_a,
                    CASE WHEN source_username < target_username
                         THEN target_username ELSE source_username END AS account_b,
                    source_username,
                    target_username
                FROM follow_edges
            )
            SELECT
                account_a,
                account_b,
                MAX(CASE WHEN source_username = account_a
                              AND target_username = account_b
                         THEN 1 ELSE 0 END) AS a_follows_b,
                MAX(CASE WHEN source_username = account_b
                              AND target_username = account_a
                         THEN 1 ELSE 0 END) AS b_follows_a
            FROM canonical
            GROUP BY account_a, account_b
            ORDER BY account_a, account_b
            """
        ).fetchall()
        return [
            Bond(
                account_a=str(row["account_a"]),
                account_b=str(row["account_b"]),
                a_follows_b=bool(row["a_follows_b"]),
                b_follows_a=bool(row["b_follows_a"]),
                bond_type="double"
                if row["a_follows_b"] and row["b_follows_a"]
                else "single",
            )
            for row in rows
        ]

    def record_import(
        self,
        source: str,
        accounts: list[str],
        edges: list[DirectedEdge],
        *,
        input_duplicate_accounts: int,
        input_duplicate_edges: int,
        rejected_entries: int,
    ) -> ImportRun:
        """Atomically write normalized edges and a completed/partial audit row."""
        source = self._normalize_source(source)
        added_accounts = 0
        added_edges = 0
        with self.connection:
            for account in accounts:
                added_accounts += self.connection.execute(
                    "INSERT OR IGNORE INTO accounts(username) VALUES (?)", (account,)
                ).rowcount
            for edge in edges:
                inserted = self.connection.execute(
                    "INSERT OR IGNORE INTO follow_edges(source_username, target_username) "
                    "VALUES (?, ?)",
                    (edge.source, edge.target),
                ).rowcount
                added_edges += inserted

            status = "partial" if rejected_entries else "completed"
            duplicate_accounts = input_duplicate_accounts + len(accounts) - added_accounts
            duplicate_edges = input_duplicate_edges + len(edges) - added_edges
            cursor = self.connection.execute(
                "INSERT INTO import_runs("
                "source, status, added_accounts, duplicate_accounts, added_edges, "
                "duplicate_edges, rejected_entries, stop_reason"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, NULL)",
                (
                    source,
                    status,
                    added_accounts,
                    duplicate_accounts,
                    added_edges,
                    duplicate_edges,
                    rejected_entries,
                ),
            )
            run_id = int(cursor.lastrowid)
            started_at = str(
                self.connection.execute(
                    "SELECT started_at FROM import_runs WHERE id = ?", (run_id,)
                ).fetchone()["started_at"]
            )
        return ImportRun(
            id=run_id,
            source=source,
            status=status,
            added_accounts=added_accounts,
            duplicate_accounts=duplicate_accounts,
            added_edges=added_edges,
            duplicate_edges=duplicate_edges,
            rejected_entries=rejected_entries,
            started_at=started_at,
            stop_reason=None,
        )

    def record_rejected_import(
        self, source: str, rejected_entries: int, reason: str
    ) -> ImportRun:
        """Record a limit or validation failure without changing the graph."""
        source = self._normalize_source(source)
        with self.connection:
            cursor = self.connection.execute(
                "INSERT INTO import_runs("
                "source, status, added_accounts, duplicate_accounts, added_edges, "
                "duplicate_edges, rejected_entries, stop_reason"
                ") VALUES (?, 'rejected', 0, 0, 0, 0, ?, ?)",
                (source, rejected_entries, reason),
            )
            run_id = int(cursor.lastrowid)
            started_at = str(
                self.connection.execute(
                    "SELECT started_at FROM import_runs WHERE id = ?", (run_id,)
                ).fetchone()["started_at"]
            )
        return ImportRun(
            id=run_id,
            source=source,
            status="rejected",
            added_accounts=0,
            duplicate_accounts=0,
            added_edges=0,
            duplicate_edges=0,
            rejected_entries=rejected_entries,
            started_at=started_at,
            stop_reason=reason,
        )

    def import_runs(self) -> list[ImportRun]:
        rows = self.connection.execute(
            "SELECT id, source, status, added_accounts, duplicate_accounts, added_edges, "
            "duplicate_edges, rejected_entries, started_at, stop_reason "
            "FROM import_runs ORDER BY id"
        ).fetchall()
        return [ImportRun(**dict(row)) for row in rows]

    @staticmethod
    def _normalize_source(source: str) -> str:
        if not isinstance(source, str) or not source.strip():
            raise ValueError("source must be a non-empty string")
        return source.strip()

    def _create_schema(self) -> None:
        with self.connection:
            self.connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS accounts (
                    username TEXT PRIMARY KEY,
                    import_status TEXT NOT NULL DEFAULT 'imported'
                        CHECK (import_status IN ('imported'))
                );

                CREATE TABLE IF NOT EXISTS follow_edges (
                    source_username TEXT NOT NULL REFERENCES accounts(username),
                    target_username TEXT NOT NULL REFERENCES accounts(username),
                    PRIMARY KEY (source_username, target_username)
                );

                CREATE TABLE IF NOT EXISTS import_runs (
                    id INTEGER PRIMARY KEY,
                    source TEXT NOT NULL,
                    status TEXT NOT NULL
                        CHECK (status IN ('completed', 'partial', 'rejected')),
                    added_accounts INTEGER NOT NULL CHECK (added_accounts >= 0),
                    duplicate_accounts INTEGER NOT NULL CHECK (duplicate_accounts >= 0),
                    added_edges INTEGER NOT NULL CHECK (added_edges >= 0),
                    duplicate_edges INTEGER NOT NULL CHECK (duplicate_edges >= 0),
                    rejected_entries INTEGER NOT NULL CHECK (rejected_entries >= 0),
                    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    stop_reason TEXT
                );
                """
            )


def _default_database_path() -> Path:
    configured_data_home = os.environ.get("XDG_DATA_HOME")
    if configured_data_home and Path(configured_data_home).expanduser().is_absolute():
        data_home = Path(configured_data_home).expanduser()
    else:
        data_home = Path.home() / ".local" / "share"
    directory = data_home / "instagraph"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(directory, 0o700)
    return directory / "instagraph.sqlite3"
