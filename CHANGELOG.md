# Changelog

## v1.5.0
### Added
- Added a deterministic `health` command so users can check workspace structure, inbox consistency, and stale outputs without invoking heavier content workflows.
- Added a compact `status` command so users can quickly inspect page counts, inbox readiness, and the current viewer/graph/inbox output state from the terminal.
- Added a `batch-clip` command so users can collect a whole directory or a manifest of `source / url / text` items into the inbox in one run.
- Added a `batch-ingest` command so users can promote `ready` inbox items into the wiki in batches, with `--dry-run`, `--limit`, and quality-based filtering.
- Added a deterministic `graph-report` command so users can turn the current graph into a governance report with isolated pages, hub stubs, fragile bridges, isolated clusters, and top graph fixes.

### Changed
- Updated `output/inbox/index.html` so the `Ready To Ingest` section now recommends `batch-ingest` dry-run and execution commands before the per-item ingest commands.
- Updated `status`, `health`, and `output/index.html` so the new graph governance report is surfaced in terminal summaries and the HTML workspace home.
- Updated `graph-report` to also write `output/graph/report.html`, making the governance report directly browsable like the rest of ThinkWiki outputs.
- Updated demo generation and committed demo outputs so repository-facing pages no longer expose local absolute paths, and removed internal competitive research notes from `docs/`.

## v1.4.0
### Added
- Added structured sidecar metadata for web clips in `normalized/inbox/*.json`, including adapter, site name, author, publish date, and source URL.
- Added explicit `clip --adapter auto|wechat|generic` selection so the inbox capture flow can evolve toward adapter-based web extraction.
- Added inbox extraction quality states (`ready`, `review`, `weak`) so the review page can highlight which clips are safe to ingest and which still need manual checking.
- Added `clip --mode auto|wait` so webpage capture can retry for a short window before writing inbox artifacts, and record whether the wait completed or timed out.
- Added `clip --media ask|always|never` so webpage images can stay remote, be marked for later review, or be localized into `normalized/assets/inbox/...` during capture.
- Added structured capture reasons such as `loading_placeholder`, `body_too_short`, and `metadata_sparse`, so inbox review can explain why a web clip still needs attention.

### Changed
- Updated `output/inbox/index.html` and the workspace inbox cards so clipped webpages now surface adapter, source, author, publish date, and metadata links during review.
- Updated the WeChat extraction path so common embedded code blocks are normalized before Markdown conversion, making technical articles easier to preserve.
- Updated `output/inbox/index.html` into a grouped review console with `Ready To Ingest`, `Needs Review`, and `Weak Captures` sections, plus priority commands for the next ingest steps.
- Updated `output/index.html` so the workspace home now highlights ready inbox items first and links directly to the ready review section.

## v1.3.0
### Added
- Added a new `clip` command and `inbox` storage flow so webpages, pasted text, and local files can be collected first and ingested into the wiki later.
- Added an `output/inbox/index.html` review page so users can browse pending inbox items and copy the next `ingest` command without leaving the browser.

### Changed
- Updated `output/index.html` so the workspace home now shows an `Inbox Queue`, inbox counts, clip-driven next actions, and a direct entry to the inbox review page.
- Updated `clip` so it backfills missing `raw/inbox` and `normalized/inbox` directories for older wikis, regenerates `output/inbox/index.html`, and refreshes the output home after each capture.

## v1.2.0
### Added
- Added a workspace-style `output/index.html` home that surfaces `What Changed`, `Next Actions`, `Needs Attention`, `Graph Snapshot`, and `Featured Pages`.
- Added homepage recommendations that reuse graph insight data so users can move from the output hub into the right next action faster.

## v1.1.0
### Added
- Added `Graph Insights` to `output/graph/index.html` so the graph page now surfaces key pages, bridge pages, weakly connected pages, and suggested links.
- Added structured graph insight data to `output/graph/graph.json` and `output/graph/graph.md` for downstream analysis and richer summaries.
- Added graph-side interactions for insight-driven exploration, including clickable insight cards and suggested-link highlighting in the SVG graph.

### Changed
- Updated the graph explorer README copy and demo screenshot so the new insight panel is visible in the repository front page.

## v1.0.1
### Fixed
- Fixed GitHub Actions regression tests so spawned test scripts now prefer the repository runtime in `.venv` after `bootstrap`, instead of falling back to the system Python.
- Fixed CI failures in `ingest.py` regression coverage caused by running document and directory ingest tests outside the bootstrapped ThinkWiki runtime.

## v1.0.0
### Released as ThinkWiki
- First standalone release under the `ThinkWiki` brand.
- Removed the legacy `scripts/llm-wiki` compatibility entry and standardized on `scripts/thinkwiki`.
- Standardized runtime environment variables on `THINKWIKI_*`.
- Renamed the regression test suite to `tests/test_thinkwiki.py`.
- Refreshed demo outputs, page titles, and repository-facing docs to consistently use `ThinkWiki`.

### Added
- Added an offline graph viewer at `output/graph/index.html` so graph generation now produces a directly browsable HTML artifact.
- Added richer graph node metadata including summary, confidence, status, updated date, path, and sources.
- Added a shared `output/index.html` hub so users can open the graph page and viewer page from one place.
- Added repository-hosted PNG screenshots for the viewer page and graph page so README can show real product output immediately.
- Added a repository-hosted PNG screenshot for `output/index.html` so README now shows the entry hub alongside viewer and graph pages.
- Added a reusable `scripts/build_demo_wiki.py` script to regenerate the demo wiki behind the README screenshots.
- Added release notes tracking for `ThinkWiki`.

### Changed
- Updated `README.md` to better explain the single-skill installation model, quick start flow, and viewer/graph outputs.
- Updated `SKILL.md` to treat graph and viewer tasks as HTML-first deliverables instead of raw data outputs.
- Updated graph layout generation to use a denser, degree-aware column layout and auto-center selected nodes in the graph stage.
- Updated graph edge rendering so `references`, `links_to`, `includes`, and `cites` now use distinct colors and line styles.
- Updated graph exploration so users can switch between `1-hop`, `2-hop`, and full-graph visibility around the selected node.
- Updated graph exploration so users can toggle individual edge types on and off when reading dense relationship maps.
- Updated graph exploration so users can jump to `all`, `concept`, `decision`, and `source` views with one-click focus presets.
- Updated graph node details so the side panel now summarizes per-edge-type relationship counts for the selected node.
- Updated graph and viewer pages so they can jump to each other through URL hashes and printed file URIs.
- Updated `ask`, `query`, `digest`, and `crystallize` so they mention the shared `output/index.html` hub whenever viewer or graph outputs already exist.
- Updated `output/index.html` so it now acts like a lightweight product homepage with wiki title, generated date, page count, node count, edge count, recent pages, featured concept/decision pages, and a recommended next step.

### Fixed
- Kept wiki-backed graph nodes from losing their richer metadata when placeholder nodes are merged during graph construction.
