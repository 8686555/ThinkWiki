from __future__ import annotations

import base64
import contextlib
import http.server
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import threading
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def runtime_python() -> str:
    candidates = [
        REPO_ROOT / ".venv" / "bin" / "python3",
        REPO_ROOT / ".venv" / "bin" / "python",
        REPO_ROOT / ".venv" / "Scripts" / "python.exe",
        REPO_ROOT / ".venv" / "Scripts" / "python",
    ]
    if os.name == "nt":
        candidates = candidates[2:] + candidates[:2]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return sys.executable


def run_script(script_name: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [runtime_python(), str(REPO_ROOT / "scripts" / script_name), *args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def run_thinkwiki(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [runtime_python(), str(REPO_ROOT / "scripts" / "thinkwiki"), *args],
        cwd=REPO_ROOT,
        check=check,
        capture_output=True,
        text=True,
    )


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")


@contextlib.contextmanager
def serve_directory(root: Path):
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

    previous = Path.cwd()
    server = None
    thread = None
    try:
        os.chdir(root)
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address
        yield f"http://{host}:{port}"
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=2)
        os.chdir(previous)


@contextlib.contextmanager
def serve_handler(handler_class: type[http.server.BaseHTTPRequestHandler]):
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler_class)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


class ThinkWikiRegressionTest(unittest.TestCase):
    def test_batch_clip_dry_run_lists_supported_directory_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            import_dir = Path(tmp_dir) / "imports"
            run_script("init_wiki.py", "--root", str(root), "--title", "Batch Clip Wiki")
            write_text(import_dir / "alpha.md", "# Alpha\n\nAlpha note.")
            write_text(import_dir / "nested" / "beta.txt", "Beta note.")
            write_text(import_dir / "ignore.png", "not supported")

            result = run_thinkwiki("batch-clip", "--root", str(root), "--source-dir", str(import_dir), "--dry-run")

            self.assertIn("ThinkWiki Batch Clip", result.stdout)
            self.assertIn("Input: source-dir", result.stdout)
            self.assertIn("Matched Items: 2", result.stdout)
            self.assertIn("alpha.md", result.stdout)
            self.assertIn("beta.txt", result.stdout)
            self.assertNotIn("ignore.png", result.stdout)
            self.assertIn("Dry run complete. No files were changed.", result.stdout)
            self.assertFalse(any((root / "normalized" / "inbox").glob("*.md")))

    def test_batch_clip_manifest_clips_mixed_items_and_refreshes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            import_dir = Path(tmp_dir) / "imports"
            site_root = Path(tmp_dir) / "site"
            manifest = Path(tmp_dir) / "clip-manifest.jsonl"
            run_script("init_wiki.py", "--root", str(root), "--title", "Batch Clip Wiki")
            write_text(import_dir / "alpha.md", "# Alpha\n\nAlpha note from manifest.")
            write_text(
                site_root / "article.html",
                """
                <html>
                  <head>
                    <meta property="og:site_name" content="Manifest Blog">
                    <meta name="author" content="Ada Lovelace">
                    <meta property="article:published_time" content="2026-06-21">
                  </head>
                  <body>
                    <main>
                      <h1>Manifest Article</h1>
                      <p>This article is long enough to be treated as a ready inbox capture during batch clip execution.</p>
                    </main>
                  </body>
                </html>
                """,
            )

            with serve_directory(site_root) as base_url:
                write_text(
                    manifest,
                    f"""
                    {{"source":"./imports/alpha.md","title":"Alpha Manifest"}}
                    {{"url":"{base_url}/article.html","title":"Manifest Article","mode":"wait","waitSeconds":1}}
                    {{"text":"# Quick Note\\n\\nSomething worth saving.","title":"Quick Note"}}
                    """,
                )
                result = run_thinkwiki("batch-clip", "--root", str(root), "--manifest", str(manifest))

            normalized_files = sorted((root / "normalized" / "inbox").glob("*.md"))
            metadata_files = sorted((root / "normalized" / "inbox").glob("*.json"))
            self.assertEqual(len(normalized_files), 3)
            self.assertEqual(len(metadata_files), 1)
            payload = json.loads(metadata_files[0].read_text(encoding="utf-8"))
            self.assertEqual(payload["title"], "Manifest Article")
            self.assertEqual(payload["siteName"], "Manifest Blog")
            self.assertEqual(payload["author"], "Ada Lovelace")
            self.assertEqual(payload["captureMode"], "wait")
            self.assertIn("Matched Items: 3", result.stdout)
            self.assertIn("Clipped: 3", result.stdout)
            self.assertIn("Manifest Article", result.stdout)
            self.assertIn("Quick Note", result.stdout)
            self.assertIn("Inbox review: output/inbox/index.html", result.stdout)
            self.assertIn("Output hub: output/index.html", result.stdout)
            self.assertIn("batch-ingest --root", result.stdout)
            self.assertTrue((root / "output" / "inbox" / "index.html").exists())
            self.assertTrue((root / "output" / "index.html").exists())
            log_text = (root / "log.md").read_text(encoding="utf-8")
            self.assertIn("batch-clip | manifest", log_text)
            self.assertIn("normalized/inbox/", log_text)

    def test_batch_ingest_dry_run_only_lists_ready_items(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            run_script("init_wiki.py", "--root", str(root), "--title", "Batch Wiki")
            write_text(
                root / "normalized" / "inbox" / "2026-06-21-ready-item.md",
                """
                # Ready Item

                This ready inbox item has enough body text to be safely promoted into the wiki during batch ingest.
                """,
            )
            write_text(
                root / "normalized" / "inbox" / "2026-06-21-ready-item.json",
                json.dumps({
                    "kind": "web",
                    "adapter": "generic",
                    "title": "Ready Item",
                    "siteName": "Example Blog",
                    "author": "Ada Lovelace",
                    "publishDate": "2026-06-21",
                    "url": "https://example.com/ready",
                }, ensure_ascii=False, indent=2),
            )
            write_text(
                root / "normalized" / "inbox" / "2026-06-21-weak-item.md",
                """
                # Weak Item

                short
                """,
            )
            write_text(
                root / "normalized" / "inbox" / "2026-06-21-weak-item.json",
                json.dumps({
                    "kind": "web",
                    "adapter": "generic",
                    "title": "Weak Item",
                    "url": "",
                }, ensure_ascii=False, indent=2),
            )

            result = run_thinkwiki("batch-ingest", "--root", str(root), "--dry-run")

            self.assertIn("ThinkWiki Batch Ingest", result.stdout)
            self.assertIn("Quality Filter: ready", result.stdout)
            self.assertIn("Matched Items: 1", result.stdout)
            self.assertIn("Ready Item", result.stdout)
            self.assertNotIn("Weak Item", result.stdout)
            self.assertIn("Dry run complete. No files were changed.", result.stdout)
            self.assertTrue((root / "normalized" / "inbox" / "2026-06-21-ready-item.md").exists())
            self.assertFalse(any((root / "wiki" / "sources").glob("*.md")))

    def test_batch_ingest_respects_limit_and_clears_processed_inbox_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            run_script("init_wiki.py", "--root", str(root), "--title", "Batch Wiki")

            old_md = root / "normalized" / "inbox" / "2026-06-21-old-ready.md"
            old_json = root / "normalized" / "inbox" / "2026-06-21-old-ready.json"
            old_raw = root / "raw" / "inbox" / "2026-06-21-old-ready.html"
            write_text(
                old_md,
                """
                # Old Ready

                This older ready inbox item should remain queued when batch ingest is limited to one item.
                """,
            )
            write_text(
                old_json,
                json.dumps({
                    "kind": "web",
                    "adapter": "generic",
                    "title": "Old Ready",
                    "siteName": "Example Blog",
                    "author": "Grace Hopper",
                    "publishDate": "2026-06-21",
                    "url": "https://example.com/old-ready",
                }, ensure_ascii=False, indent=2),
            )
            write_text(old_raw, "<html><body>old ready</body></html>")

            new_md = root / "normalized" / "inbox" / "2026-06-21-new-ready.md"
            new_json = root / "normalized" / "inbox" / "2026-06-21-new-ready.json"
            new_raw = root / "raw" / "inbox" / "2026-06-21-new-ready.html"
            new_media_dir = root / "normalized" / "assets" / "inbox" / "2026-06-21-new-ready"
            write_text(
                new_md,
                """
                # New Ready

                This newer ready inbox item has the richest metadata and should be the one batch ingest processes first.
                """,
            )
            write_text(
                new_json,
                json.dumps({
                    "kind": "web",
                    "adapter": "generic",
                    "title": "New Ready",
                    "siteName": "Example Blog",
                    "author": "Ada Lovelace",
                    "publishDate": "2026-06-21",
                    "url": "https://example.com/new-ready",
                    "mediaDir": "normalized/assets/inbox/2026-06-21-new-ready",
                }, ensure_ascii=False, indent=2),
            )
            write_text(new_raw, "<html><body>new ready</body></html>")
            write_text(new_media_dir / "pixel.png", "image")

            os.utime(old_md, (1000, 1000))
            os.utime(old_json, (1000, 1000))
            os.utime(old_raw, (1000, 1000))
            os.utime(new_md, (2000, 2000))
            os.utime(new_json, (2000, 2000))
            os.utime(new_raw, (2000, 2000))

            result = run_thinkwiki("batch-ingest", "--root", str(root), "--limit", "1")

            self.assertIn("Ingested: 1", result.stdout)
            self.assertIn("Cleared Inbox Artifacts: 4", result.stdout)
            self.assertIn("New Ready -> wiki/sources/new-ready.md", result.stdout)
            self.assertIn("Output hub: output/index.html", result.stdout)
            self.assertIn("Next: run `python scripts/thinkwiki viewer --root", result.stdout)
            self.assertTrue((root / "wiki" / "sources" / "new-ready.md").exists())
            self.assertFalse(new_md.exists())
            self.assertFalse(new_json.exists())
            self.assertFalse(new_raw.exists())
            self.assertFalse(new_media_dir.exists())
            self.assertTrue(old_md.exists())
            self.assertTrue(old_json.exists())
            self.assertTrue(old_raw.exists())
            self.assertTrue((root / "output" / "inbox" / "index.html").exists())
            self.assertTrue((root / "output" / "index.html").exists())
            log_text = (root / "log.md").read_text(encoding="utf-8")
            self.assertIn("batch-ingest | quality=ready", log_text)
            self.assertIn("wiki/sources/new-ready.md", log_text)

    def test_health_passes_on_fresh_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            run_script("init_wiki.py", "--root", str(root), "--title", "Healthy Wiki")

            result = run_script("health.py", "--root", str(root))

            self.assertIn("ThinkWiki Health Report", result.stdout)
            self.assertIn("- Errors: 0", result.stdout)
            self.assertIn("- Warnings: 0", result.stdout)
            self.assertIn("All checks passed", result.stdout)

    def test_status_command_reports_workspace_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            run_script("init_wiki.py", "--root", str(root), "--title", "Status Wiki")
            write_text(
                root / "wiki" / "concepts" / "ai-native-team.md",
                """
                ---
                title: AI Native Team
                type: concept
                created: 2026-06-21
                updated: 2026-06-21
                summary: A concept page used for status testing.
                sources:
                  - raw/articles/team-note.md
                tags:
                  - concept
                confidence: high
                status: active
                ---

                # AI Native Team

                A concept page used for status testing.
                """,
            )
            write_text(
                root / "normalized" / "inbox" / "2026-06-21-captured-article.md",
                """
                # Captured Article

                This article is complete enough to be treated as ready for ingest.
                """,
            )
            write_text(
                root / "normalized" / "inbox" / "2026-06-21-captured-article.json",
                json.dumps({
                    "kind": "web",
                    "adapter": "generic",
                    "title": "Captured Article",
                    "siteName": "Example Blog",
                    "author": "Ada Lovelace",
                    "publishDate": "2026-06-21",
                    "url": "https://example.com/article",
                }, ensure_ascii=False, indent=2),
            )

            run_script("build_inbox.py", "--root", str(root))
            run_script("build_viewer.py", "--root", str(root))
            run_script("build_graph.py", "--root", str(root))

            result = run_thinkwiki("status", "--root", str(root))

            self.assertIn("ThinkWiki Status", result.stdout)
            self.assertIn("Title: wiki", result.stdout)
            self.assertIn("Pages: 1 (concept=1)", result.stdout)
            self.assertIn("Inbox: total=1, ready=1, review=0, weak=0", result.stdout)
            self.assertIn("Output Home: ready", result.stdout)
            self.assertIn("Viewer: ready", result.stdout)
            self.assertIn("Graph: ready", result.stdout)
            self.assertIn("Inbox Review: ready", result.stdout)

    def test_health_warns_on_invalid_inbox_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            run_script("init_wiki.py", "--root", str(root), "--title", "Warning Wiki")
            write_text(root / "normalized" / "inbox" / "2026-06-21-bad.json", "{not-json")

            result = run_script("health.py", "--root", str(root))

            self.assertIn("- Errors: 0", result.stdout)
            self.assertIn("- Warnings: 1", result.stdout)
            self.assertIn("[invalid-inbox-metadata]", result.stdout)

    def test_init_reports_next_output_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            result = run_script("init_wiki.py", "--root", str(root), "--title", "Test Wiki")

            self.assertIn("Initialized wiki at ", result.stdout)
            self.assertIn(str(root.resolve()), result.stdout)
            self.assertIn("Next: run `python scripts/thinkwiki viewer --root", result.stdout)
            self.assertIn("Next: run `python scripts/thinkwiki graph --root", result.stdout)

    def test_graph_keeps_wiki_source_node_types(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            write_text(root / ".wiki-schema.md", "# marker")
            (root / "raw" / "articles").mkdir(parents=True, exist_ok=True)
            (root / "output" / "graph").mkdir(parents=True, exist_ok=True)
            (root / "wiki" / "sources").mkdir(parents=True, exist_ok=True)
            (root / "wiki" / "topics").mkdir(parents=True, exist_ok=True)
            (root / "raw" / "articles" / "platform.docx").write_text("raw", encoding="utf-8")
            write_text(
                root / "wiki" / "sources" / "platform-spec.md",
                """
                ---
                title: Platform Spec
                type: source
                created: 2026-06-15
                updated: 2026-06-15
                summary: Source summary.
                sources:
                  - raw/articles/platform.docx
                tags:
                  - source
                confidence: extracted
                status: active
                ---

                # Platform Spec

                ## Summary

                Source summary.
                """,
            )
            write_text(
                root / "wiki" / "topics" / "platform.md",
                """
                ---
                title: Platform
                type: topic
                created: 2026-06-15
                updated: 2026-06-15
                summary: Topic summary.
                sources:
                  - wiki/sources/platform-spec.md
                tags:
                  - topic
                confidence: mixed
                status: active
                ---

                # Platform

                ## Included Sources

                - [Platform Spec](../sources/platform-spec.md)
                """,
            )

            run_script("build_graph.py", "--root", str(root))
            graph = json.loads((root / "output" / "graph" / "graph.json").read_text(encoding="utf-8"))
            node_by_id = {node["id"]: node for node in graph["nodes"]}

            self.assertEqual(node_by_id["wiki/sources/platform-spec.md"]["type"], "source")
            self.assertEqual(node_by_id["wiki/sources/platform-spec.md"]["summary"], "Source summary.")
            self.assertEqual(node_by_id["wiki/sources/platform-spec.md"]["confidence"], "extracted")
            self.assertEqual(node_by_id["wiki/sources/platform-spec.md"]["status"], "active")
            self.assertEqual(node_by_id["wiki/sources/platform-spec.md"]["path"], "wiki/sources/platform-spec.md")
            self.assertIn(
                {
                    "source": "wiki/topics/platform.md",
                    "target": "wiki/sources/platform-spec.md",
                    "type": "includes",
                },
                graph["edges"],
            )

    def test_graph_build_writes_html_viewer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            write_text(root / ".wiki-schema.md", "# marker")
            (root / "wiki" / "sources").mkdir(parents=True, exist_ok=True)
            (root / "output" / "graph").mkdir(parents=True, exist_ok=True)
            write_text(
                root / "wiki" / "sources" / "alpha.md",
                """
                ---
                title: Alpha Source
                type: source
                created: 2026-06-19
                updated: 2026-06-19
                summary: Alpha summary.
                sources:
                  - raw/articles/alpha.md
                tags:
                  - source
                confidence: extracted
                status: active
                ---

                # Alpha Source

                ## Summary

                Alpha summary.
                """,
            )

            run_script("build_graph.py", "--root", str(root))

            html_path = root / "output" / "graph" / "index.html"
            self.assertTrue(html_path.exists())
            html_text = html_path.read_text(encoding="utf-8")
            self.assertIn("ThinkWiki Graph", html_text)
            self.assertIn("Alpha Source", html_text)
            self.assertIn("../viewer/index.html#page=", html_text)
            self.assertIn('id="graphStage"', html_text)
            self.assertIn("centerNodeInStage", html_text)
            self.assertIn("关系图例", html_text)
            self.assertIn("edgeStyles", html_text)
            self.assertIn('id="scopeFilter"', html_text)
            self.assertIn("scopeFilterEl", html_text)
            self.assertIn("edgeType-references", html_text)
            self.assertIn("enabledEdgeTypes", html_text)
            self.assertIn("快速聚焦", html_text)
            self.assertIn("syncFocusButtons", html_text)
            self.assertIn('data-focus-type="concept"', html_text)
            self.assertIn("edgeStatsForNode", html_text)
            self.assertIn("Relation Stats", html_text)
            self.assertIn("Graph Insights", html_text)
            self.assertIn("Key Pages", html_text)
            self.assertIn("Bridge Pages", html_text)
            self.assertIn("Suggested Links", html_text)
            self.assertIn("suggestionKey", html_text)
            self.assertIn("renderInsights", html_text)
            self.assertIn("stroke-dasharray", html_text)
            self.assertTrue((root / "output" / "index.html").exists())
            self.assertIn("output/graph/index.html", (root / "log.md").read_text(encoding="utf-8"))

    def test_graph_insights_identify_key_pages_and_link_suggestions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            write_text(root / ".wiki-schema.md", "# marker")
            (root / "wiki" / "sources").mkdir(parents=True, exist_ok=True)
            (root / "wiki" / "topics").mkdir(parents=True, exist_ok=True)
            (root / "wiki" / "concepts").mkdir(parents=True, exist_ok=True)
            (root / "wiki" / "queries").mkdir(parents=True, exist_ok=True)

            write_text(
                root / "wiki" / "sources" / "platform-spec.md",
                """
                ---
                title: Platform Spec
                type: source
                created: 2026-06-19
                updated: 2026-06-19
                summary: Platform foundation and terminology.
                sources:
                  - raw/articles/platform.pdf
                confidence: extracted
                status: active
                ---

                # Platform Spec
                """,
            )
            write_text(
                root / "wiki" / "topics" / "platform.md",
                """
                ---
                title: Platform
                type: topic
                created: 2026-06-19
                updated: 2026-06-19
                summary: Platform topic overview.
                sources:
                  - wiki/sources/platform-spec.md
                confidence: mixed
                status: active
                ---

                # Platform

                - [Platform Spec](../sources/platform-spec.md)
                """,
            )
            write_text(
                root / "wiki" / "concepts" / "platform-principles.md",
                """
                ---
                title: Platform Principles
                type: concept
                created: 2026-06-19
                updated: 2026-06-19
                summary: Platform principles for the current wiki.
                sources:
                  - wiki/sources/platform-spec.md
                confidence: inferred
                status: active
                ---

                # Platform Principles
                """,
            )
            write_text(
                root / "wiki" / "queries" / "orphan-question.md",
                """
                ---
                title: Orphan Question
                type: query
                created: 2026-06-19
                updated: 2026-06-19
                summary: A loose question that still needs links.
                confidence: mixed
                status: active
                ---

                # Orphan Question
                """,
            )

            run_script("build_graph.py", "--root", str(root))
            graph = json.loads((root / "output" / "graph" / "graph.json").read_text(encoding="utf-8"))
            insights = graph["insights"]

            self.assertIn("summary", insights)
            self.assertGreaterEqual(len(insights["topNodes"]), 1)
            self.assertEqual(insights["topNodes"][0]["id"], "wiki/sources/platform-spec.md")
            self.assertTrue(
                any(item["id"] == "wiki/queries/orphan-question.md" and item["severity"] == "isolated" for item in insights["isolatedNodes"])
            )
            self.assertTrue(
                any(
                    {item["source"], item["target"]} == {
                        "wiki/topics/platform.md",
                        "wiki/concepts/platform-principles.md",
                    }
                    for item in insights["suggestedLinks"]
                )
            )

    def test_graph_report_integrates_with_status_health_and_home(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            run_script("init_wiki.py", "--root", str(root), "--title", "Graph Report Wiki")

            write_text(
                root / "wiki" / "sources" / "platform-spec.md",
                """
                ---
                title: Platform Spec
                type: source
                created: 2026-06-21
                updated: 2026-06-21
                summary: Tiny.
                sources:
                  - raw/articles/platform.pdf
                tags:
                  - source
                confidence: extracted
                status: active
                ---

                # Platform Spec
                """,
            )
            write_text(
                root / "wiki" / "topics" / "platform.md",
                """
                ---
                title: Platform
                type: topic
                created: 2026-06-21
                updated: 2026-06-21
                summary: Platform topic overview with enough context to connect to the core source.
                sources:
                  - wiki/sources/platform-spec.md
                tags:
                  - topic
                confidence: mixed
                status: active
                ---

                # Platform
                """,
            )
            write_text(
                root / "wiki" / "concepts" / "platform-principles.md",
                """
                ---
                title: Platform Principles
                type: concept
                created: 2026-06-21
                updated: 2026-06-21
                summary: Platform principles explain how the platform should evolve and how teams should reuse the source material.
                sources:
                  - wiki/sources/platform-spec.md
                tags:
                  - concept
                confidence: inferred
                status: active
                ---

                # Platform Principles
                """,
            )
            write_text(
                root / "wiki" / "decisions" / "platform-decision.md",
                """
                ---
                title: Platform Decision
                type: decision
                created: 2026-06-21
                updated: 2026-06-21
                summary: This decision records why the team keeps building around the platform source page.
                sources:
                  - wiki/sources/platform-spec.md
                tags:
                  - decision
                confidence: high
                status: active
                ---

                # Platform Decision
                """,
            )
            write_text(
                root / "wiki" / "queries" / "bridge-question.md",
                """
                ---
                title: Bridge Question
                type: query
                created: 2026-06-21
                updated: 2026-06-21
                summary: This question connects the central source page with the platform principles page.
                sources:
                  - wiki/sources/platform-spec.md
                tags:
                  - query
                confidence: mixed
                status: active
                ---

                # Bridge Question

                - [Platform Principles](../concepts/platform-principles.md)
                """,
            )
            write_text(
                root / "wiki" / "sources" / "cluster-spec.md",
                """
                ---
                title: Cluster Spec
                type: source
                created: 2026-06-21
                updated: 2026-06-21
                summary: Cluster source summary.
                sources:
                  - raw/articles/cluster.pdf
                tags:
                  - source
                confidence: extracted
                status: active
                ---

                # Cluster Spec
                """,
            )
            write_text(
                root / "wiki" / "topics" / "cluster-topic.md",
                """
                ---
                title: Cluster Topic
                type: topic
                created: 2026-06-21
                updated: 2026-06-21
                summary: This topic is intentionally disconnected from the main platform graph.
                sources:
                  - wiki/sources/cluster-spec.md
                tags:
                  - topic
                confidence: mixed
                status: active
                ---

                # Cluster Topic
                """,
            )
            write_text(
                root / "wiki" / "queries" / "orphan-question.md",
                """
                ---
                title: Orphan Question
                type: query
                created: 2026-06-21
                updated: 2026-06-21
                summary: A page that still needs its first explicit relationship.
                sources:
                  - raw/articles/orphan.txt
                tags:
                  - query
                confidence: low
                status: draft
                ---

                # Orphan Question
                """,
            )

            run_script("build_viewer.py", "--root", str(root))
            run_script("build_graph.py", "--root", str(root))

            result = run_thinkwiki("graph-report", "--root", str(root))

            report_json_path = root / "output" / "graph" / "report.json"
            report_md_path = root / "output" / "graph" / "report.md"
            report_html_path = root / "output" / "graph" / "report.html"
            self.assertTrue(report_json_path.exists())
            self.assertTrue(report_md_path.exists())
            self.assertTrue(report_html_path.exists())
            report = json.loads(report_json_path.read_text(encoding="utf-8"))
            stats = report["stats"]

            self.assertIn("ThinkWiki Graph Report", result.stdout)
            self.assertIn("Graph report: output/graph/report.html", result.stdout)
            self.assertEqual(stats["isolatedPageCount"], 1)
            self.assertEqual(stats["hubStubCount"], 1)
            self.assertEqual(stats["isolatedClusterCount"], 1)
            self.assertGreaterEqual(stats["fragileBridgeCount"], 1)
            self.assertTrue(any("孤立页面" in item for item in report["topActions"]))

            status_result = run_thinkwiki("status", "--root", str(root))
            self.assertIn("Graph Report: ready", status_result.stdout)
            self.assertIn("isolatedPages=1", status_result.stdout)
            self.assertIn("hubStubs=1", status_result.stdout)
            self.assertIn("clusters=1", status_result.stdout)

            health_result = run_thinkwiki("health", "--root", str(root))
            self.assertIn("Graph Report: ready, isolatedPages=1, hubStubs=1", health_result.stdout)
            self.assertIn("- Errors: 0", health_result.stdout)
            self.assertIn("- Warnings: 0", health_result.stdout)

            hub_html = (root / "output" / "index.html").read_text(encoding="utf-8")
            self.assertIn("图谱治理报告", hub_html)
            self.assertIn("graph/report.html", hub_html)
            self.assertIn("Hub Stubs 1 个", hub_html)
            self.assertIn("Isolated Clusters 1 个", hub_html)
            self.assertIn("优先处理孤立页面", hub_html)

            report_html = report_html_path.read_text(encoding="utf-8")
            self.assertIn("ThinkWiki Graph Report", report_html)
            self.assertIn("Pages That Need Links", report_html)
            self.assertIn("Hub Stubs", report_html)
            self.assertIn("Open Workspace Home", report_html)

    def test_output_hub_shows_wiki_stats(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            write_text(root / ".wiki-schema.md", "# marker")
            write_text(root / "index.md", "# Demo Knowledge Base")
            (root / "wiki" / "sources").mkdir(parents=True, exist_ok=True)
            (root / "wiki" / "topics").mkdir(parents=True, exist_ok=True)
            (root / "output" / "viewer").mkdir(parents=True, exist_ok=True)
            (root / "output" / "graph").mkdir(parents=True, exist_ok=True)
            write_text(
                root / "wiki" / "sources" / "alpha.md",
                """
                ---
                title: Alpha Source
                type: source
                created: 2026-06-19
                updated: 2026-06-19
                summary: Alpha summary.
                sources:
                  - raw/articles/alpha.md
                tags:
                  - source
                confidence: extracted
                status: active
                ---

                # Alpha Source

                ## Summary

                Alpha summary.
                """,
            )
            write_text(
                root / "wiki" / "topics" / "beta.md",
                """
                ---
                title: Beta Topic
                type: topic
                created: 2026-06-19
                updated: 2026-06-19
                summary: Beta summary.
                sources:
                  - wiki/sources/alpha.md
                tags:
                  - topic
                confidence: mixed
                status: active
                ---

                # Beta Topic

                ## Included Sources

                - [Alpha Source](../sources/alpha.md)
                """,
            )

            run_script("build_viewer.py", "--root", str(root))
            run_script("build_graph.py", "--root", str(root))

            hub_html = (root / "output" / "index.html").read_text(encoding="utf-8")
            self.assertIn("Demo Knowledge Base", hub_html)
            self.assertIn("知识工作台首页", hub_html)
            self.assertIn(">2</strong><span>页面数</span>", hub_html)
            self.assertIn(">3</strong><span>图节点</span>", hub_html)
            self.assertIn(">3</strong><span>图关系</span>", hub_html)
            self.assertIn("What Changed", hub_html)
            self.assertIn("Next Actions", hub_html)
            self.assertIn("Needs Attention", hub_html)
            self.assertIn("Graph Snapshot", hub_html)
            self.assertIn("Featured Pages", hub_html)
            self.assertIn("Outputs Overview", hub_html)
            self.assertIn("从这里开始", hub_html)
            self.assertIn("Alpha Source", hub_html)
            self.assertIn("Beta Topic", hub_html)
            self.assertIn("viewer/index.html#page=wiki/topics/beta.md", hub_html)
            self.assertIn("当前最关键的页面是", hub_html)

    def test_directory_ingest_updates_topic_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            source_dir = Path(tmp_dir) / "docs"
            write_text(source_dir / "platform" / "a.md", "# A\n\nAlpha summary.")
            write_text(source_dir / "platform" / "b.md", "# B\n\nBeta summary.")

            run_script("init_wiki.py", "--root", str(root), "--title", "Test Wiki")
            run_script("ingest.py", "--root", str(root), "--source", str(source_dir))

            topic_text = (root / "wiki" / "topics" / "platform.md").read_text(encoding="utf-8")
            self.assertIn("wiki/sources/a.md", topic_text)
            self.assertIn("wiki/sources/b.md", topic_text)
            self.assertIn("[a](../sources/a.md)", topic_text)
            self.assertIn("[b](../sources/b.md)", topic_text)

    def test_clip_text_creates_inbox_item_and_next_step(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            run_script("init_wiki.py", "--root", str(root), "--title", "Test Wiki")

            result = run_script(
                "clip.py",
                "--root",
                str(root),
                "--title",
                "Inbox Note",
                "--text",
                "# Inbox Note\n\nThis is a clipped note for later ingest.",
            )

            inbox_files = sorted((root / "normalized" / "inbox").glob("*.md"))
            self.assertEqual(len(inbox_files), 1)
            inbox_text = inbox_files[0].read_text(encoding="utf-8")
            self.assertIn("# Inbox Note", inbox_text)
            self.assertIn("This is a clipped note for later ingest.", inbox_text)
            self.assertIn("Clipped Inbox Note into inbox", result.stdout)
            self.assertIn("Inbox normalized: normalized/inbox/", result.stdout)
            self.assertIn("Inbox review: output/inbox/index.html", result.stdout)
            self.assertIn("Output hub: output/index.html", result.stdout)
            self.assertIn("Next: run `python scripts/thinkwiki ingest --root", result.stdout)
            self.assertIn("normalized/inbox/", (root / "log.md").read_text(encoding="utf-8"))
            self.assertTrue((root / "output" / "inbox" / "index.html").exists())
            self.assertTrue((root / "output" / "index.html").exists())

    def test_clip_refreshes_output_home_and_creates_missing_inbox_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            write_text(root / ".wiki-schema.md", "# marker")
            write_text(root / "index.md", "# Legacy Wiki")
            (root / "output" / "viewer").mkdir(parents=True, exist_ok=True)
            write_text(root / "output" / "viewer" / "index.html", "<html><body>viewer</body></html>")

            result = run_script(
                "clip.py",
                "--root",
                str(root),
                "--title",
                "Fresh Capture",
                "--text",
                "# Fresh Capture\n\nA clipped note for the inbox queue.",
            )

            self.assertTrue((root / "raw" / "inbox").exists())
            self.assertTrue((root / "normalized" / "inbox").exists())
            hub_html = (root / "output" / "index.html").read_text(encoding="utf-8")
            inbox_html = (root / "output" / "inbox" / "index.html").read_text(encoding="utf-8")
            self.assertIn("Inbox Queue", hub_html)
            self.assertIn("Inbox Review", hub_html)
            self.assertIn("Fresh Capture", hub_html)
            self.assertIn("inbox/index.html", hub_html)
            self.assertIn(">1</strong><span>Inbox</span>", hub_html)
            self.assertIn("Next ingest command", inbox_html)
            self.assertIn("python scripts/thinkwiki ingest --root", inbox_html)
            self.assertIn("Fresh Capture", inbox_html)
            self.assertIn("../normalized/inbox/", inbox_html)
            self.assertIn("Inbox review: output/inbox/index.html", result.stdout)
            self.assertIn("Output hub: output/index.html", result.stdout)
            self.assertIn("Output hub URI: file://", result.stdout)

    def test_build_inbox_command_creates_review_page(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            run_script("init_wiki.py", "--root", str(root), "--title", "Inbox Wiki")
            write_text(root / "normalized" / "inbox" / "2026-06-20-team-note.md", "# Team Note\n\nReview this before ingest.")
            write_text(
                root / "normalized" / "inbox" / "2026-06-20-team-note.json",
                json.dumps({
                    "kind": "web",
                    "adapter": "generic",
                    "title": "Team Note",
                    "siteName": "Example Blog",
                    "author": "Ada Lovelace",
                    "publishDate": "2026-06-20",
                    "url": "https://example.com/team-note",
                }, ensure_ascii=False, indent=2),
            )

            result = run_script("build_inbox.py", "--root", str(root))

            inbox_html = (root / "output" / "inbox" / "index.html").read_text(encoding="utf-8")
            self.assertIn("ThinkWiki Inbox Review", inbox_html)
            self.assertIn("Priority Queue", inbox_html)
            self.assertIn("Ready To Ingest", inbox_html)
            self.assertIn("python scripts/thinkwiki batch-ingest --root", inbox_html)
            self.assertIn("Team Note", inbox_html)
            self.assertIn("Review this before ingest.", inbox_html)
            self.assertIn("python scripts/thinkwiki ingest --root", inbox_html)
            self.assertIn("Inbox review: output/inbox/index.html", result.stdout)
            self.assertIn("Output hub: output/index.html", result.stdout)

    def test_clip_url_writes_generic_web_metadata_and_review_details(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            site_root = Path(tmp_dir) / "site"
            run_script("init_wiki.py", "--root", str(root), "--title", "Web Wiki")
            write_text(
                site_root / "article.html",
                """
                <html>
                  <head>
                    <title>Ignored Browser Title</title>
                    <meta property="og:site_name" content="Example Blog">
                    <meta name="author" content="Ada Lovelace">
                    <meta property="article:published_time" content="2026-06-21">
                  </head>
                  <body>
                    <main>
                      <h1>Captured Article</h1>
                      <p>This article should land in ThinkWiki inbox with metadata.</p>
                    </main>
                  </body>
                </html>
                """,
            )

            with serve_directory(site_root) as base_url:
                result = run_script("clip.py", "--root", str(root), "--url", f"{base_url}/article.html")

            metadata_files = sorted((root / "normalized" / "inbox").glob("*.json"))
            self.assertEqual(len(metadata_files), 1)
            payload = json.loads(metadata_files[0].read_text(encoding="utf-8"))
            self.assertEqual(payload["kind"], "web")
            self.assertEqual(payload["adapter"], "generic")
            self.assertEqual(payload["title"], "Captured Article")
            self.assertEqual(payload["siteName"], "Example Blog")
            self.assertEqual(payload["author"], "Ada Lovelace")
            self.assertEqual(payload["publishDate"], "2026-06-21")
            self.assertTrue(payload["url"].endswith("/article.html"))
            self.assertIn("Web adapter: generic", result.stdout)
            self.assertIn("Inbox metadata: normalized/inbox/", result.stdout)
            inbox_html = (root / "output" / "inbox" / "index.html").read_text(encoding="utf-8")
            self.assertIn("Example Blog", inbox_html)
            self.assertIn("Ada Lovelace", inbox_html)
            self.assertIn("2026-06-21", inbox_html)
            self.assertIn("Quality", inbox_html)
            self.assertIn("ready", inbox_html)
            self.assertIn("Open metadata", inbox_html)
            hub_html = (root / "output" / "index.html").read_text(encoding="utf-8")
            self.assertIn("优先处理 Ready Inbox", hub_html)
            self.assertIn("inbox/index.html#ready", hub_html)

    def test_clip_url_auto_detects_wechat_adapter_from_dom(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            site_root = Path(tmp_dir) / "site"
            run_script("init_wiki.py", "--root", str(root), "--title", "WeChat Wiki")
            write_text(
                site_root / "wechat.html",
                """
                <html>
                  <body>
                    <div id="activity-name"><span class="js_title_inner">WeChat Capture</span></div>
                    <div id="js_author_name">Grace Hopper</div>
                    <div id="js_name">ThinkWiki Channel</div>
                    <div id="js_content">
                      <p>This looks like a public WeChat article body.</p>
                    </div>
                    <script>var ct = "1718928000";</script>
                  </body>
                </html>
                """,
            )

            with serve_directory(site_root) as base_url:
                run_script("clip.py", "--root", str(root), "--url", f"{base_url}/wechat.html")

            metadata_files = sorted((root / "normalized" / "inbox").glob("*.json"))
            self.assertEqual(len(metadata_files), 1)
            payload = json.loads(metadata_files[0].read_text(encoding="utf-8"))
            self.assertEqual(payload["adapter"], "wechat")
            self.assertEqual(payload["title"], "WeChat Capture")
            self.assertEqual(payload["siteName"], "ThinkWiki Channel")
            self.assertEqual(payload["author"], "Grace Hopper")
            self.assertTrue(payload["publishDate"].startswith("2024-06-21"))

    def test_clip_url_wechat_code_blocks_are_preserved_for_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            site_root = Path(tmp_dir) / "site"
            run_script("init_wiki.py", "--root", str(root), "--title", "Code Wiki")
            write_text(
                site_root / "wechat-code.html",
                """
                <html>
                  <body>
                    <div id="activity-name"><span class="js_title_inner">WeChat Code Capture</span></div>
                    <div id="js_name">ThinkWiki Channel</div>
                    <div id="js_content">
                      <div class="js_code_area" data-lang="python">
                        <pre>print("hello thinkwiki")</pre>
                      </div>
                    </div>
                    <script>var ct = "1718928000";</script>
                  </body>
                </html>
                """,
            )

            with serve_directory(site_root) as base_url:
                run_script("clip.py", "--root", str(root), "--url", f"{base_url}/wechat-code.html")

            normalized_files = sorted((root / "normalized" / "inbox").glob("*.md"))
            self.assertEqual(len(normalized_files), 1)
            normalized_text = normalized_files[0].read_text(encoding="utf-8")
            self.assertIn('print("hello thinkwiki")', normalized_text)

    def test_build_inbox_marks_low_quality_items_for_manual_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            run_script("init_wiki.py", "--root", str(root), "--title", "Weak Inbox Wiki")
            write_text(root / "normalized" / "inbox" / "2026-06-20-weak-item.md", "# Weak Item\n\nshort")
            write_text(
                root / "normalized" / "inbox" / "2026-06-20-weak-item.json",
                json.dumps({
                    "kind": "web",
                    "adapter": "generic",
                    "title": "Weak Item",
                    "url": "",
                }, ensure_ascii=False, indent=2),
            )

            run_script("build_inbox.py", "--root", str(root))

            inbox_html = (root / "output" / "inbox" / "index.html").read_text(encoding="utf-8")
            self.assertIn("weak", inbox_html)
            self.assertIn("建议优先人工检查正文质量和来源信息", inbox_html)

    def test_clip_url_wait_mode_polls_until_content_is_ready(self) -> None:
        class PollingHandler(http.server.BaseHTTPRequestHandler):
            counter = 0

            def do_GET(self) -> None:
                type(self).counter += 1
                if type(self).counter == 1:
                    body = """
                    <html>
                      <body>
                        <main>
                          <h1>Loading Article</h1>
                          <p>Loading...</p>
                        </main>
                      </body>
                    </html>
                    """
                else:
                    body = """
                    <html>
                      <head>
                        <meta property="og:site_name" content="Polling Blog">
                        <meta name="author" content="Retry Author">
                      </head>
                      <body>
                        <main>
                          <h1>Loaded Article</h1>
                          <p>This is the fully loaded article body after the page finishes rendering and exposes the main content.</p>
                          <p>It should be long enough for ThinkWiki to treat the capture as ready instead of leaving it in a weak or review state.</p>
                        </main>
                      </body>
                    </html>
                    """
                payload = textwrap.dedent(body).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, format: str, *args: object) -> None:
                return

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            run_script("init_wiki.py", "--root", str(root), "--title", "Wait Wiki")

            with serve_handler(PollingHandler) as base_url:
                result = run_script(
                    "clip.py",
                    "--root",
                    str(root),
                    "--url",
                    f"{base_url}/article.html",
                    "--mode",
                    "wait",
                    "--wait-seconds",
                    "2",
                )

            metadata_files = sorted((root / "normalized" / "inbox").glob("*.json"))
            self.assertEqual(len(metadata_files), 1)
            payload = json.loads(metadata_files[0].read_text(encoding="utf-8"))
            self.assertEqual(payload["captureMode"], "wait")
            self.assertEqual(payload["captureState"], "wait_completed")
            self.assertGreaterEqual(payload["captureAttempts"], 2)
            self.assertIn("Capture mode: wait", result.stdout)
            self.assertIn("Capture state: wait_completed", result.stdout)
            inbox_html = (root / "output" / "inbox" / "index.html").read_text(encoding="utf-8")
            self.assertIn("wait_completed", inbox_html)
            self.assertIn("Polling Blog", inbox_html)

    def test_clip_url_loading_placeholder_reason_is_exposed_in_review(self) -> None:
        class LoadingHandler(http.server.BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                body = """
                <html>
                  <body>
                    <main>
                      <h1>Loading Article</h1>
                      <p>Loading...</p>
                    </main>
                  </body>
                </html>
                """
                payload = textwrap.dedent(body).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, format: str, *args: object) -> None:
                return

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            run_script("init_wiki.py", "--root", str(root), "--title", "Reason Wiki")

            with serve_handler(LoadingHandler) as base_url:
                result = run_script(
                    "clip.py",
                    "--root",
                    str(root),
                    "--url",
                    f"{base_url}/loading.html",
                )

            metadata_files = sorted((root / "normalized" / "inbox").glob("*.json"))
            self.assertEqual(len(metadata_files), 1)
            payload = json.loads(metadata_files[0].read_text(encoding="utf-8"))
            self.assertEqual(payload["captureState"], "needs_review")
            self.assertEqual(payload["captureReason"], "loading_placeholder")
            self.assertIn("Capture reason: loading_placeholder", result.stdout)
            inbox_html = (root / "output" / "inbox" / "index.html").read_text(encoding="utf-8")
            self.assertIn("loading_placeholder", inbox_html)
            self.assertIn("页面仍像加载占位", inbox_html)

    def test_clip_url_media_always_downloads_and_rewrites_markdown(self) -> None:
        tiny_png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9WnR0p8AAAAASUVORK5CYII="
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            site_root = Path(tmp_dir) / "site"
            run_script("init_wiki.py", "--root", str(root), "--title", "Media Wiki")
            write_text(
                site_root / "article.html",
                """
                <html>
                  <head>
                    <meta property="og:site_name" content="Image Blog">
                  </head>
                  <body>
                    <main>
                      <h1>Image Article</h1>
                      <p>This article includes an image.</p>
                      <img src="/pixel.png" alt="pixel">
                    </main>
                  </body>
                </html>
                """,
            )
            (site_root / "pixel.png").parent.mkdir(parents=True, exist_ok=True)
            (site_root / "pixel.png").write_bytes(tiny_png)

            with serve_directory(site_root) as base_url:
                result = run_script(
                    "clip.py",
                    "--root",
                    str(root),
                    "--url",
                    f"{base_url}/article.html",
                    "--media",
                    "always",
                )

            metadata_files = sorted((root / "normalized" / "inbox").glob("*.json"))
            self.assertEqual(len(metadata_files), 1)
            payload = json.loads(metadata_files[0].read_text(encoding="utf-8"))
            self.assertEqual(payload["mediaPolicy"], "always")
            self.assertEqual(payload["mediaStatus"], "localized")
            self.assertEqual(payload["mediaCount"], 1)
            self.assertEqual(payload["localizedMediaCount"], 1)
            self.assertIn("Media status: localized (1/1)", result.stdout)
            media_dir = root / str(payload["mediaDir"])
            self.assertTrue(media_dir.exists())
            normalized_files = sorted((root / "normalized" / "inbox").glob("*.md"))
            self.assertEqual(len(normalized_files), 1)
            normalized_text = normalized_files[0].read_text(encoding="utf-8")
            self.assertIn("../assets/inbox/", normalized_text)
            self.assertNotRegex(normalized_text, r"!\[[^\]]*\]\(https?://")
            inbox_html = (root / "output" / "inbox" / "index.html").read_text(encoding="utf-8")
            self.assertIn("localized", inbox_html)
            self.assertIn("Media files", inbox_html)

    def test_viewer_distinguishes_page_links_and_file_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            write_text(root / ".wiki-schema.md", "# marker")
            (root / "raw" / "articles").mkdir(parents=True, exist_ok=True)
            (root / "output" / "viewer").mkdir(parents=True, exist_ok=True)
            (root / "wiki" / "sources").mkdir(parents=True, exist_ok=True)
            (root / "wiki" / "topics").mkdir(parents=True, exist_ok=True)
            (root / "raw" / "articles" / "platform.docx").write_text("raw", encoding="utf-8")

            write_text(
                root / "wiki" / "topics" / "platform.md",
                """
                ---
                title: Platform
                type: topic
                created: 2026-06-15
                updated: 2026-06-15
                summary: Topic summary.
                sources:
                  - wiki/sources/platform-spec.md
                tags:
                  - topic
                confidence: mixed
                status: active
                ---

                # Platform
                """,
            )
            write_text(
                root / "wiki" / "sources" / "platform-spec.md",
                """
                ---
                title: Platform Spec
                type: source
                created: 2026-06-15
                updated: 2026-06-15
                summary: Source summary.
                sources:
                  - raw/articles/platform.docx
                tags:
                  - source
                confidence: extracted
                status: active
                ---

                # Platform Spec

                ## Connections

                - [Platform Topic](../topics/platform.md)
                - [Raw Doc](../../raw/articles/platform.docx)
                """,
            )

            run_script("build_viewer.py", "--root", str(root))
            payload = json.loads((root / "output" / "viewer" / "viewer.json").read_text(encoding="utf-8"))
            page = next(item for item in payload["pages"] if item["id"] == "wiki/sources/platform-spec.md")
            section = next(item for item in page["sections"] if item["title"] == "Connections")

            self.assertIn(
                {
                    "label": "platform.md",
                    "raw": "../topics/platform.md",
                    "targetId": "wiki/topics/platform.md",
                    "href": "",
                },
                section["links"],
            )
            self.assertIn(
                {
                    "label": "platform.docx",
                    "raw": "../../raw/articles/platform.docx",
                    "targetId": "",
                    "href": "../../raw/articles/platform.docx",
                },
                section["links"],
            )
            html_text = (root / "output" / "viewer" / "index.html").read_text(encoding="utf-8")
            self.assertIn("../graph/index.html#node=", html_text)
            self.assertTrue((root / "output" / "index.html").exists())

    def test_query_command_reports_output_hub_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            write_text(root / ".wiki-schema.md", "# marker")
            (root / "output" / "viewer").mkdir(parents=True, exist_ok=True)
            write_text(root / "output" / "viewer" / "index.html", "<html><body>viewer</body></html>")

            result = run_script(
                "query_wiki.py",
                "--root",
                str(root),
                "--question",
                "What is alpha?",
                "--answer",
                "Alpha is the first concept.",
            )

            self.assertIn("Created wiki/queries/what-is-alpha.md", result.stdout)
            self.assertIn("Output hub: output/index.html", result.stdout)
            self.assertIn("Output hub URI: file://", result.stdout)
            self.assertTrue((root / "output" / "index.html").exists())

    def test_ingest_reports_output_hub_when_viewer_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "wiki"
            source = Path(tmp_dir) / "alpha.md"
            write_text(source, "# Alpha\n\nAlpha summary.")
            run_script("init_wiki.py", "--root", str(root), "--title", "Test Wiki")
            (root / "output" / "viewer").mkdir(parents=True, exist_ok=True)
            write_text(root / "output" / "viewer" / "index.html", "<html><body>viewer</body></html>")

            result = run_script("ingest.py", "--root", str(root), "--source", str(source))

            self.assertIn("Ingested Alpha", result.stdout)
            self.assertIn("Output hub: output/index.html", result.stdout)
            self.assertIn("Output hub URI: file://", result.stdout)
            self.assertTrue((root / "output" / "index.html").exists())


if __name__ == "__main__":
    unittest.main()
