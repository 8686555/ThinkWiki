from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
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


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")


class ThinkWikiRegressionTest(unittest.TestCase):
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

            result = run_script("build_inbox.py", "--root", str(root))

            inbox_html = (root / "output" / "inbox" / "index.html").read_text(encoding="utf-8")
            self.assertIn("ThinkWiki Inbox Review", inbox_html)
            self.assertIn("Team Note", inbox_html)
            self.assertIn("Review this before ingest.", inbox_html)
            self.assertIn("python scripts/thinkwiki ingest --root", inbox_html)
            self.assertIn("Inbox review: output/inbox/index.html", result.stdout)
            self.assertIn("Output hub: output/index.html", result.stdout)

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
