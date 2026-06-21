#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from utils import find_repo_root
from workspace_status import collect_health_issues, collect_workspace_snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic health checks for the current ThinkWiki workspace.")
    parser.add_argument("--root", default=".", help="Wiki root path")
    args = parser.parse_args()

    root = find_repo_root(Path(args.root))
    snapshot = collect_workspace_snapshot(root)
    errors, warnings = collect_health_issues(root, snapshot)

    lines = [
        "# ThinkWiki Health Report",
        "",
        f"- Root: {snapshot['root']}",
        f"- Title: {snapshot['title']}",
        f"- Errors: {len(errors)}",
        f"- Warnings: {len(warnings)}",
        "",
        "## Summary",
        "",
    ]
    pages = snapshot["pages"]
    inbox = snapshot["inbox"]
    outputs = snapshot["outputs"]
    page_counts = pages.get("counts", {}) if isinstance(pages, dict) else {}
    inbox_counts = inbox.get("quality_counts", {}) if isinstance(inbox, dict) else {}
    viewer = outputs.get("viewer", {}) if isinstance(outputs, dict) else {}
    graph = outputs.get("graph", {}) if isinstance(outputs, dict) else {}
    inbox_output = outputs.get("inbox", {}) if isinstance(outputs, dict) else {}
    lines.extend([
        "- Pages: total={total}, types={types}".format(
            total=pages.get("total", 0) if isinstance(pages, dict) else 0,
            types=", ".join(f"{key}={value}" for key, value in sorted(page_counts.items())) or "none",
        ),
        "- Inbox: total={total}, ready={ready}, review={review}, weak={weak}".format(
            total=inbox.get("total", 0) if isinstance(inbox, dict) else 0,
            ready=inbox_counts.get("ready", 0) if isinstance(inbox_counts, dict) else 0,
            review=inbox_counts.get("review", 0) if isinstance(inbox_counts, dict) else 0,
            weak=inbox_counts.get("weak", 0) if isinstance(inbox_counts, dict) else 0,
        ),
        "- Outputs: hub={hub}, viewer={viewer}, graph={graph}, inbox={inbox}".format(
            hub="ready" if bool(outputs.get("hub", {}).get("exists")) else "missing",
            viewer="ready" if bool(viewer.get("html_exists")) else "missing",
            graph="ready" if bool(graph.get("html_exists")) else "missing",
            inbox="ready" if bool(inbox_output.get("html_exists")) else "missing",
        ),
        "- Graph Report: {state}, isolatedPages={isolated}, hubStubs={hub_stubs}, fragileBridges={fragile}, clusters={clusters}".format(
            state="ready" if bool(graph.get("report_html_exists")) else "missing",
            isolated=int(graph.get("report_isolated_pages", 0) or 0),
            hub_stubs=int(graph.get("report_hub_stubs", 0) or 0),
            fragile=int(graph.get("report_fragile_bridges", 0) or 0),
            clusters=int(graph.get("report_isolated_clusters", 0) or 0),
        ),
        "",
    ])
    if errors:
        lines.extend(["## Errors", ""])
        lines.extend(f"- {item}" for item in errors)
        lines.append("")
    if warnings:
        lines.extend(["## Warnings", ""])
        lines.extend(f"- {item}" for item in warnings)
        lines.append("")
    if not errors and not warnings:
        lines.extend(["## Result", "", "- All checks passed", ""])

    print("\n".join(lines).rstrip())
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
