# Repository Guidelines

## Project structure

`src/instagraph/` is the product package. It imports a user-selected local graph into
SQLite and provides an optional OpenAI Responses client. The planned browser companion
is separate from this package: after explicit user activation, it turns only
user-visible list entries into a local JSON v1 file for the existing importer.

- `store.py` owns the SQLite schema: `accounts`, `follow_edges`, and `import_runs`.
- `importer.py` validates the local JSON v1 format and performs atomic imports.
- `exporter.py` writes private Cytoscape JSON and deploys the static viewer assets.
- `web/` contains the local Cytoscape.js viewer and its MIT license notice.
- `openai_client.py` is a small, optional direct SDK bridge.
- `graph_tools.py` and `graph_chat.py` expose consent-gated, read-only local graph
  queries to the optional Responses API client.
- `companion/` is a separate Manifest V3 browser companion. It is not part of the
  Python package and keeps capture state only in the selected tab's content script.
- `tests/` contains offline standard-library `unittest` coverage.
- `src/osintgraph/` is legacy reference code only. It is not packaged by the new
  `pyproject.toml`; do not extend or import it from `instagraph`.
- [roadmap.md](roadmap.md) is the source of truth for the remaining product phases.

## Build and test

Use Python 3.11+.

- `python -m pip install -e .` installs the local core.
- `python -m pip install -e '.[ai]'` adds the optional OpenAI SDK.
- `PYTHONPATH=src python -m unittest discover -v` runs every offline test.
- `python -m compileall -q src` checks syntax.
- `python -m pip wheel --no-deps --wheel-dir /tmp/instagraph-wheel .` verifies packaging.
- `python -m http.server --bind 127.0.0.1 --directory web 8000` serves an exported viewer locally.
- `node --test companion/tests/capture-core.test.js` checks the companion's local
  contract and manifest restrictions.

Tests must not call Instagram, Meta, OpenAI, or any other external service. Browser
companion tests use local HTML/JSON fixtures, never a real account or browser profile.

## Coding conventions

Use four-space indentation, `snake_case` functions/modules, and `PascalCase`
classes. Prefer the standard library for the core.

Normalize Instagram usernames only through `GraphStore.normalize_username`; it is
the single canonicalization rule. Keep `follow_edges` directed. Derive a
single/double `Bond` from opposing edges at read time instead of saving another
relationship table.

The documented JSON v1 input has exactly `version`, `accounts`, and `follows`.
Reject unknown schema versions and malformed entries without retaining raw rejected
social data. An import that exceeds its node/edge cap must leave the graph unchanged
and create a rejected `import_run`. Keep the 10 MiB file and 100,000 input-entry caps
unless a documented product requirement changes them.

## Security and scope

Never commit graph databases, exports, API keys, Instagram cookies, browser profiles,
sessions, screenshots, page text, URLs, or raw browser captures. `OPENAI_API_KEY`
belongs in the environment and must never be written to project JSON or SQLite. Sending
graph data to OpenAI requires an explicit user opt-in; keep the API client small until
read-only graph tools exist.

Without an explicit path, `GraphStore` writes under the private XDG user-data directory.
Explicit database files are created with owner-only permissions; do not weaken them.

The browser companion is allowed only as a user-controlled, local capture: the user
opens and scrolls the page, explicitly starts/stops capture, confirms the profile and
list direction, and reviews the JSON v1 export before importing it. It may retain only
the normalized usernames and directed edges needed for that export.

Do not add autonomous browser scraping or crawling. In particular, do not use
Playwright, Selenium, Instaloader, direct Instagram requests, session/cookie/profile
imports, automatic scrolling/clicking/navigation, CAPTCHA handling, proxy rotation,
or other bypass behavior. Do not read browser cookies, storage, credentials, hidden
DOM content, screenshots, posts, messages, media, comments, likes, or analytics.
Fail closed when the page no longer has the expected user-visible list UI.

The product accepts a user-selected authorized export, a reviewed local JSON export
from the manual browser companion, or an official API field that has been verified as
permitted. The Python importer itself must remain offline and browser-independent.

The current companion uses the explicit `data-instagraph-*=v1` contract only for
offline fixtures. Its popup injects one manually verified, narrow Instagram list
adapter; it must continue to fail closed outside that exact dialog/row structure. Do
not add guessed selectors or generic link/text fallbacks.
