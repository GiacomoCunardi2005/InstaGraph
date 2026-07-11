"""Small, read-only graph queries for the optional chat layer."""

from __future__ import annotations

from collections import deque

from .store import GraphStore


__all__ = [
    "find_path",
    "get_account",
    "get_community",
    "get_neighbors",
    "graph_summary",
]


def get_account(store: GraphStore, username: str) -> dict[str, object]:
    """Return aggregate account data without exposing its neighbor lists."""
    username = GraphStore.normalize_username(username)
    if username not in store.usernames():
        return {"username": username, "found": False}

    edges = store.edges()
    return {
        "username": username,
        "found": True,
        "following_count": sum(edge.source == username for edge in edges),
        "followers_count": sum(edge.target == username for edge in edges),
    }


def get_neighbors(store: GraphStore, username: str, direction: str) -> dict[str, object]:
    """Return deterministically ordered neighbors in the requested direction."""
    username = GraphStore.normalize_username(username)
    if direction not in {"following", "followers", "both"}:
        raise ValueError("direction must be 'following', 'followers', or 'both'")

    result: dict[str, object] = {
        "username": username,
        "direction": direction,
        "found": username in store.usernames(),
    }
    if not result["found"]:
        if direction in {"following", "both"}:
            result["following"] = []
        if direction in {"followers", "both"}:
            result["followers"] = []
        return result

    edges = store.edges()
    if direction in {"following", "both"}:
        result["following"] = sorted(
            edge.target for edge in edges if edge.source == username
        )
    if direction in {"followers", "both"}:
        result["followers"] = sorted(
            edge.source for edge in edges if edge.target == username
        )
    return result


def find_path(store: GraphStore, start: str, target: str) -> dict[str, object]:
    """Find a shortest undirected social path of at most six edges."""
    start = GraphStore.normalize_username(start)
    target = GraphStore.normalize_username(target)
    accounts = store.usernames()
    if start not in accounts or target not in accounts:
        return {"start": start, "target": target, "found": False, "path": []}
    if start == target:
        return {"start": start, "target": target, "found": True, "path": [start]}

    neighbors: dict[str, set[str]] = {account: set() for account in accounts}
    # ponytail: in-memory BFS scans every edge; add indexed store reads only if it becomes slow.
    for edge in store.edges():
        neighbors[edge.source].add(edge.target)
        neighbors[edge.target].add(edge.source)

    queue = deque([(start, [start])])
    visited = {start}
    while queue:
        current, path = queue.popleft()
        if len(path) == 7:
            continue
        for neighbor in sorted(neighbors[current]):
            if neighbor in visited:
                continue
            next_path = [*path, neighbor]
            if neighbor == target:
                return {
                    "start": start,
                    "target": target,
                    "found": True,
                    "path": next_path,
                }
            visited.add(neighbor)
            queue.append((neighbor, next_path))

    return {"start": start, "target": target, "found": False, "path": []}


def get_community(store: GraphStore, username: str) -> dict[str, object]:
    """Return the account's local connected component, not an inferred community."""
    username = GraphStore.normalize_username(username)
    accounts = store.usernames()
    if username not in accounts:
        return {"username": username, "found": False}

    neighbors: dict[str, set[str]] = {account: set() for account in accounts}
    for edge in store.edges():
        neighbors[edge.source].add(edge.target)
        neighbors[edge.target].add(edge.source)

    community = {username}
    queue = deque([username])
    while queue:
        current = queue.popleft()
        for neighbor in neighbors[current]:
            if neighbor not in community:
                community.add(neighbor)
                queue.append(neighbor)

    members = sorted(community)
    return {
        "username": username,
        "found": True,
        "method": "connected_component",
        "member_count": len(members),
        "members": members[:100],
        "truncated": len(members) > 100,
    }


def graph_summary(store: GraphStore) -> dict[str, object]:
    """Return aggregate graph and import information without account lists."""
    bonds = store.bonds()
    runs = store.import_runs()
    return {
        "account_count": len(store.usernames()),
        "directed_edge_count": len(store.edges()),
        "single_bond_count": sum(bond.bond_type == "single" for bond in bonds),
        "double_bond_count": sum(bond.bond_type == "double" for bond in bonds),
        "latest_import_status": runs[-1].status if runs else None,
    }
