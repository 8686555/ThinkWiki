#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from html import escape
from pathlib import Path

from build_graph import node_metrics
from utils import append_log, file_uri, find_repo_root, today_str, write_output_home, write_text


def _load_graph(root: Path) -> dict[str, object]:
    graph_path = root / "output" / "graph" / "graph.json"
    if not graph_path.exists():
        raise SystemExit("Graph data not found. Run `python scripts/thinkwiki graph --root <wiki-root>` first.")
    try:
        return json.loads(graph_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise SystemExit(f"Invalid graph data: {graph_path} ({exc})") from exc


def _page_nodes(nodes: list[dict[str, object]]) -> list[dict[str, object]]:
    return [node for node in nodes if str(node.get("type") or "page") not in {"raw", "file"}]


def _summary_length(node: dict[str, object]) -> int:
    return len(str(node.get("summary", "") or "").strip())


def _connected_components(node_ids: set[str], edges: list[dict[str, str]]) -> list[list[str]]:
    adjacency: dict[str, set[str]] = {node_id: set() for node_id in node_ids}
    for edge in edges:
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        if source not in adjacency or target not in adjacency:
            continue
        adjacency[source].add(target)
        adjacency[target].add(source)

    components: list[list[str]] = []
    seen: set[str] = set()
    for node_id in sorted(node_ids):
        if node_id in seen:
            continue
        stack = [node_id]
        component: list[str] = []
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            component.append(current)
            stack.extend(sorted(adjacency[current] - seen))
        components.append(sorted(component))
    return sorted(components, key=lambda item: (-len(item), item[0] if item else ""))


def _hub_stub_candidates(
    page_nodes: list[dict[str, object]],
    metrics: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    if not page_nodes:
        return []
    degrees = [int(metrics[str(node["id"])]["degree"]) for node in page_nodes]
    average_degree = sum(degrees) / len(degrees)
    threshold = max(3, int(round(average_degree + 1)))
    items: list[dict[str, object]] = []
    for node in page_nodes:
        node_id = str(node["id"])
        degree = int(metrics[node_id]["degree"])
        summary_length = _summary_length(node)
        if degree < threshold or summary_length >= 80:
            continue
        items.append({
            "id": node_id,
            "title": str(node.get("label") or node_id),
            "type": str(node.get("type") or "page"),
            "degree": degree,
            "summaryLength": summary_length,
            "reason": f"关系数 {degree} 较高，但摘要只有 {summary_length} 个字符",
        })
    return sorted(items, key=lambda item: (-int(item["degree"]), int(item["summaryLength"]), str(item["title"]).lower()))[:6]


def _fragile_bridge_candidates(
    page_nodes: list[dict[str, object]],
    metrics: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for node in page_nodes:
        node_id = str(node["id"])
        info = metrics[node_id]
        degree = int(info["degree"])
        neighbor_types = {str(item) for item in info["neighbor_types"]}
        if degree > 0 and degree <= 2 and len(neighbor_types) >= 2:
            items.append({
                "id": node_id,
                "title": str(node.get("label") or node_id),
                "type": str(node.get("type") or "page"),
                "degree": degree,
                "neighborTypes": sorted(neighbor_types),
                "reason": f"只靠 {degree} 条关系连接 {len(neighbor_types)} 类页面，结构较脆弱",
            })
    return sorted(items, key=lambda item: (int(item["degree"]), -len(item["neighborTypes"]), str(item["title"]).lower()))[:6]


def _page_health_candidates(
    page_nodes: list[dict[str, object]],
    metrics: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for node in page_nodes:
        node_id = str(node["id"])
        degree = int(metrics[node_id]["degree"])
        if degree == 0:
            items.append({
                "id": node_id,
                "title": str(node.get("label") or node_id),
                "type": str(node.get("type") or "page"),
                "severity": "isolated",
                "degree": degree,
                "reason": "还没有和其他页面建立任何页面级关系",
            })
        elif degree == 1:
            items.append({
                "id": node_id,
                "title": str(node.get("label") or node_id),
                "type": str(node.get("type") or "page"),
                "severity": "weak",
                "degree": degree,
                "reason": "目前只有 1 条页面级关系，建议继续补链",
            })
    return sorted(
        items,
        key=lambda item: (
            0 if str(item["severity"]) == "isolated" else 1,
            str(item["title"]).lower(),
        ),
    )[:8]


def _isolated_cluster_candidates(
    page_nodes: list[dict[str, object]],
    edges: list[dict[str, str]],
    node_by_id: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    page_node_ids = {str(node["id"]) for node in page_nodes}
    components = _connected_components(page_node_ids, edges)
    if len(components) <= 1:
        return []
    items: list[dict[str, object]] = []
    for component in components[1:]:
        if len(component) < 2:
            continue
        labels = [str(node_by_id[node_id].get("label") or node_id) for node_id in component if node_id in node_by_id]
        items.append({
            "size": len(component),
            "nodeIds": component,
            "titles": labels[:4],
            "reason": f"该子图与主图断开，包含 {len(component)} 个页面",
        })
    return sorted(items, key=lambda item: (-int(item["size"]), ",".join(item["titles"]).lower()))[:4]


def _top_actions(report: dict[str, object]) -> list[str]:
    stats = report["stats"]
    assert isinstance(stats, dict)
    actions: list[str] = []
    if int(stats.get("isolatedPageCount", 0) or 0):
        actions.append("优先处理孤立页面，先补 `links_to` 或来源引用。")
    if int(stats.get("hubStubCount", 0) or 0):
        actions.append("检查高连接但内容薄弱的页面，补摘要、上下文和来源。")
    if int(stats.get("fragileBridgeCount", 0) or 0):
        actions.append("加强脆弱桥接页面，避免主题之间只靠单点连接。")
    if int(stats.get("isolatedClusterCount", 0) or 0):
        actions.append("把孤立子图连接回主图，提升整体可导航性。")
    if int(stats.get("suggestedLinkCount", 0) or 0):
        actions.append("复核建议补链，把高置信度关系转成显式页面链接。")
    return actions[:4] or ["当前图谱结构总体稳定，可继续扩充高价值页面。"]


def build_report(graph: dict[str, object]) -> dict[str, object]:
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    insights = graph.get("insights", {})
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise SystemExit("Invalid graph payload: nodes/edges are missing.")
    if not isinstance(insights, dict):
        insights = {}

    page_nodes = _page_nodes(nodes)
    page_node_ids = {str(node["id"]) for node in page_nodes}
    filtered_edges = [
        edge for edge in edges
        if str(edge.get("source") or "") in page_node_ids and str(edge.get("target") or "") in page_node_ids
    ]
    metrics = node_metrics(page_nodes, filtered_edges)
    node_by_id = {str(node["id"]): node for node in page_nodes}

    isolated_pages = _page_health_candidates(page_nodes, metrics)
    hub_stubs = _hub_stub_candidates(page_nodes, metrics)
    fragile_bridges = _fragile_bridge_candidates(page_nodes, metrics)
    isolated_clusters = _isolated_cluster_candidates(page_nodes, filtered_edges, node_by_id)
    suggested_links = [
        item for item in insights.get("suggestedLinks", [])
        if isinstance(item, dict)
    ]

    stats = {
        "nodeCount": len(page_nodes),
        "edgeCount": len(filtered_edges),
        "isolatedPageCount": sum(1 for item in isolated_pages if str(item.get("severity", "")) == "isolated"),
        "weakPageCount": sum(1 for item in isolated_pages if str(item.get("severity", "")) == "weak"),
        "bridgePageCount": len([item for item in insights.get("bridgeNodes", []) if isinstance(item, dict)]),
        "suggestedLinkCount": len(suggested_links),
        "hubStubCount": len(hub_stubs),
        "fragileBridgeCount": len(fragile_bridges),
        "isolatedClusterCount": len(isolated_clusters),
        "componentCount": len(_connected_components(page_node_ids, filtered_edges)) if page_node_ids else 0,
        "averageDegree": round((len(filtered_edges) * 2 / len(page_nodes)) if page_nodes else 0, 2),
    }

    top_node = next((item for item in insights.get("topNodes", []) if isinstance(item, dict)), None)
    summary_parts = []
    if top_node:
        summary_parts.append(f"当前关键页面是 {top_node.get('title', 'n/a')}。")
    if stats["isolatedPageCount"]:
        summary_parts.append(f"有 {stats['isolatedPageCount']} 个孤立页面需要补链接。")
    elif stats["weakPageCount"]:
        summary_parts.append(f"有 {stats['weakPageCount']} 个弱连接页面需要继续整理。")
    else:
        summary_parts.append("主要页面已经形成基础连接。")
    if stats["hubStubCount"]:
        summary_parts.append(f"有 {stats['hubStubCount']} 个高连接薄内容页面值得优先补强。")
    if stats["isolatedClusterCount"]:
        summary_parts.append(f"当前存在 {stats['isolatedClusterCount']} 个与主图断开的子图。")
    if stats["suggestedLinkCount"]:
        summary_parts.append(f"当前可复核 {stats['suggestedLinkCount']} 条建议补链。")

    report = {
        "generated_at": today_str(),
        "summary": " ".join(summary_parts),
        "stats": stats,
        "topActions": _top_actions({"stats": stats}),
        "topNodes": insights.get("topNodes", []),
        "bridgeNodes": insights.get("bridgeNodes", []),
        "isolatedPages": isolated_pages,
        "hubStubs": hub_stubs,
        "fragileBridges": fragile_bridges,
        "isolatedClusters": isolated_clusters,
        "suggestedLinks": suggested_links,
    }
    return report


def render_report_markdown(report: dict[str, object]) -> str:
    stats = report["stats"]
    assert isinstance(stats, dict)
    lines = [
        "# ThinkWiki Graph Report",
        "",
        f"- Generated: {report['generated_at']}",
        f"- Summary: {report['summary']}",
        "",
        "## Health Summary",
        "",
        f"- Pages: {stats['nodeCount']}",
        f"- Relations: {stats['edgeCount']}",
        f"- Average Degree: {stats['averageDegree']}",
        f"- Isolated Pages: {stats['isolatedPageCount']}",
        f"- Weak Pages: {stats['weakPageCount']}",
        f"- Bridge Pages: {stats['bridgePageCount']}",
        f"- Suggested Links: {stats['suggestedLinkCount']}",
        f"- Hub Stubs: {stats['hubStubCount']}",
        f"- Fragile Bridges: {stats['fragileBridgeCount']}",
        f"- Isolated Clusters: {stats['isolatedClusterCount']}",
        "",
        "## Top Actions",
        "",
    ]
    lines.extend(f"- {item}" for item in report["topActions"])
    lines.extend(["", "## Hub Stubs", ""])
    if report["hubStubs"]:
        lines.extend(
            f"- {item['title']} ({item['type']}) | degree={item['degree']} | {item['reason']}"
            for item in report["hubStubs"]
        )
    else:
        lines.append("- No hub stubs")
    lines.extend(["", "## Fragile Bridges", ""])
    if report["fragileBridges"]:
        lines.extend(
            f"- {item['title']} ({item['type']}) | degree={item['degree']} | {item['reason']}"
            for item in report["fragileBridges"]
        )
    else:
        lines.append("- No fragile bridges")
    lines.extend(["", "## Isolated Clusters", ""])
    if report["isolatedClusters"]:
        lines.extend(
            f"- size={item['size']} | {', '.join(item['titles'])} | {item['reason']}"
            for item in report["isolatedClusters"]
        )
    else:
        lines.append("- No isolated clusters")
    lines.extend(["", "## Suggested Links", ""])
    if report["suggestedLinks"]:
        lines.extend(
            f"- {item['source']} <-> {item['target']} | score={item['score']}"
            for item in report["suggestedLinks"]
        )
    else:
        lines.append("- No suggested links")
    return "\n".join(lines)


def _render_html_list(items: list[str]) -> str:
    if not items:
        return "<div class='empty'>Nothing here yet.</div>"
    return "<ul class='bullet-list'>{}</ul>".format(
        "".join(f"<li>{escape(item)}</li>" for item in items)
    )


def _render_html_metric_cards(stats: dict[str, object]) -> str:
    cards = []
    for label, key in [
        ("Pages", "nodeCount"),
        ("Relations", "edgeCount"),
        ("Average Degree", "averageDegree"),
        ("Isolated Pages", "isolatedPageCount"),
        ("Weak Pages", "weakPageCount"),
        ("Bridge Pages", "bridgePageCount"),
        ("Suggested Links", "suggestedLinkCount"),
        ("Hub Stubs", "hubStubCount"),
        ("Fragile Bridges", "fragileBridgeCount"),
        ("Isolated Clusters", "isolatedClusterCount"),
    ]:
        cards.append(
            "<div class='stat'><strong>{}</strong><span>{}</span></div>".format(
                escape(str(stats.get(key, 0) or 0)),
                escape(label),
            )
        )
    return "\n".join(cards)


def _render_html_record_cards(items: list[dict[str, object]], empty_text: str, formatter) -> str:
    if not items:
        return "<div class='empty'>{}</div>".format(escape(empty_text))
    rows = []
    for item in items:
        title, meta, reason = formatter(item)
        rows.append(
            "<div class='record-card'>"
            "<strong>{}</strong>"
            "<div class='record-meta'>{}</div>"
            "<p>{}</p>"
            "</div>".format(
                escape(title),
                escape(meta),
                escape(reason),
            )
        )
    return "\n".join(rows)


def render_report_html(report: dict[str, object]) -> str:
    stats = report["stats"]
    assert isinstance(stats, dict)
    top_actions = report.get("topActions", [])
    hub_stubs = report.get("hubStubs", [])
    fragile_bridges = report.get("fragileBridges", [])
    isolated_clusters = report.get("isolatedClusters", [])
    suggested_links = report.get("suggestedLinks", [])
    isolated_pages = report.get("isolatedPages", [])
    top_nodes = report.get("topNodes", [])
    bridge_nodes = report.get("bridgeNodes", [])

    isolated_cards = _render_html_record_cards(
        isolated_pages if isinstance(isolated_pages, list) else [],
        "No isolated or weak pages.",
        lambda item: (
            str(item.get("title") or item.get("id") or "Untitled"),
            "{} | degree={}".format(str(item.get("severity") or "page"), int(item.get("degree", 0) or 0)),
            str(item.get("reason") or ""),
        ),
    )
    hub_cards = _render_html_record_cards(
        hub_stubs if isinstance(hub_stubs, list) else [],
        "No hub stubs.",
        lambda item: (
            str(item.get("title") or item.get("id") or "Untitled"),
            "{} | degree={}".format(str(item.get("type") or "page"), int(item.get("degree", 0) or 0)),
            str(item.get("reason") or ""),
        ),
    )
    bridge_cards = _render_html_record_cards(
        fragile_bridges if isinstance(fragile_bridges, list) else [],
        "No fragile bridges.",
        lambda item: (
            str(item.get("title") or item.get("id") or "Untitled"),
            "{} | degree={}".format(str(item.get("type") or "page"), int(item.get("degree", 0) or 0)),
            str(item.get("reason") or ""),
        ),
    )
    cluster_cards = _render_html_record_cards(
        isolated_clusters if isinstance(isolated_clusters, list) else [],
        "No isolated clusters.",
        lambda item: (
            ", ".join(str(title) for title in item.get("titles", [])[:3]) or "Untitled cluster",
            "cluster | size={}".format(int(item.get("size", 0) or 0)),
            str(item.get("reason") or ""),
        ),
    )
    suggestion_cards = _render_html_record_cards(
        suggested_links if isinstance(suggested_links, list) else [],
        "No suggested links.",
        lambda item: (
            "{} <-> {}".format(str(item.get("source") or "n/a"), str(item.get("target") or "n/a")),
            "suggested link | score={}".format(item.get("score", "n/a")),
            str(item.get("reason") or "High-confidence structural suggestion."),
        ),
    )
    top_node_cards = _render_html_record_cards(
        top_nodes if isinstance(top_nodes, list) else [],
        "No key pages yet.",
        lambda item: (
            str(item.get("title") or item.get("id") or "Untitled"),
            "{} | score={}".format(str(item.get("type") or "page"), int(item.get("score", 0) or 0)),
            str(item.get("reason") or ""),
        ),
    )
    bridge_node_cards = _render_html_record_cards(
        bridge_nodes if isinstance(bridge_nodes, list) else [],
        "No bridge pages yet.",
        lambda item: (
            str(item.get("title") or item.get("id") or "Untitled"),
            "{} | score={}".format(str(item.get("type") or "page"), int(item.get("score", 0) or 0)),
            str(item.get("reason") or ""),
        ),
    )

    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ThinkWiki Graph Report</title>
  <style>
    :root {{
      --bg: #0b1020;
      --panel: #121935;
      --text: #edf2ff;
      --muted: #a8b3cf;
      --border: rgba(255,255,255,0.1);
      --accent: #8ab4ff;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: linear-gradient(180deg, #0b1020 0%, #10172f 100%);
      color: var(--text);
      padding: 24px;
    }}
    .shell {{
      width: min(1180px, 100%);
      margin: 0 auto;
      background: rgba(9, 13, 28, 0.86);
      border: 1px solid var(--border);
      border-radius: 24px;
      padding: 28px;
    }}
    h1, h2, p {{ margin-top: 0; }}
    .lead {{
      color: var(--muted);
      line-height: 1.6;
    }}
    .meta {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin: 16px 0 24px;
    }}
    .badge {{
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 6px 12px;
      color: var(--muted);
      background: rgba(255,255,255,0.03);
      font-size: 0.92rem;
    }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: 12px;
      margin: 24px 0;
    }}
    .stat {{
      border: 1px solid var(--border);
      background: var(--panel);
      border-radius: 18px;
      padding: 16px;
    }}
    .stat strong {{
      display: block;
      font-size: 1.4rem;
      margin-bottom: 6px;
    }}
    .stat span {{
      color: var(--muted);
    }}
    .layout {{
      display: grid;
      gap: 14px;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      margin-top: 18px;
    }}
    .panel {{
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.02);
      border-radius: 18px;
      padding: 18px;
    }}
    .panel p {{
      color: var(--muted);
      line-height: 1.55;
    }}
    .bullet-list {{
      margin: 0;
      padding-left: 18px;
      color: var(--muted);
      display: grid;
      gap: 10px;
      line-height: 1.5;
    }}
    .records {{
      display: grid;
      gap: 10px;
    }}
    .record-card {{
      border: 1px solid var(--border);
      background: var(--panel);
      border-radius: 16px;
      padding: 14px;
    }}
    .record-card strong {{
      display: block;
      margin-bottom: 6px;
    }}
    .record-meta {{
      color: var(--accent);
      font-size: 0.88rem;
      margin-bottom: 8px;
    }}
    .record-card p {{
      margin-bottom: 0;
    }}
    .empty {{
      border: 1px dashed var(--border);
      border-radius: 16px;
      padding: 14px;
      color: var(--muted);
    }}
    a {{
      color: var(--accent);
    }}
    @media (max-width: 860px) {{
      .layout {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <main class="shell">
    <h1>ThinkWiki Graph Report</h1>
    <p class="lead">{summary}</p>
    <div class="meta">
      <span class="badge">Generated {generated_at}</span>
      <span class="badge">Pages {page_count}</span>
      <span class="badge">Relations {edge_count}</span>
      <span class="badge"><a href="index.html">Open Graph</a></span>
      <span class="badge"><a href="../index.html">Open Workspace Home</a></span>
    </div>

    <section>
      <h2>Health Summary</h2>
      <div class="stats">
        {metric_cards}
      </div>
    </section>

    <div class="layout">
      <section class="panel">
        <h2>Top Actions</h2>
        <p>先处理最影响导航性和可维护性的图谱问题。</p>
        {top_actions}
      </section>
      <section class="panel">
        <h2>Key Pages</h2>
        <p>优先阅读或补强这些页面，它们对当前图谱结构最关键。</p>
        <div class="records">{top_nodes}</div>
      </section>
      <section class="panel">
        <h2>Bridge Pages</h2>
        <p>这些页面连接了不同类型或不同主题的区域。</p>
        <div class="records">{bridge_nodes}</div>
      </section>
      <section class="panel">
        <h2>Pages That Need Links</h2>
        <p>这里展示孤立页面和弱连接页面，适合优先补链。</p>
        <div class="records">{isolated_pages}</div>
      </section>
      <section class="panel">
        <h2>Hub Stubs</h2>
        <p>关系很多但内容偏薄的页面，补摘要和上下文通常收益最高。</p>
        <div class="records">{hub_stubs}</div>
      </section>
      <section class="panel">
        <h2>Fragile Bridges</h2>
        <p>只靠少量页面维持跨主题连接的结构点，容易成为单点脆弱处。</p>
        <div class="records">{fragile_bridges}</div>
      </section>
      <section class="panel">
        <h2>Isolated Clusters</h2>
        <p>这些页面已经形成小片区，但还没有接回主图。</p>
        <div class="records">{isolated_clusters}</div>
      </section>
      <section class="panel">
        <h2>Suggested Links</h2>
        <p>高置信度的候选关系，适合人工复核后转成显式链接。</p>
        <div class="records">{suggested_links}</div>
      </section>
    </div>
  </main>
</body>
</html>
""".format(
        summary=escape(str(report.get("summary") or "")),
        generated_at=escape(str(report.get("generated_at") or "")),
        page_count=escape(str(stats.get("nodeCount", 0) or 0)),
        edge_count=escape(str(stats.get("edgeCount", 0) or 0)),
        metric_cards=_render_html_metric_cards(stats),
        top_actions=_render_html_list([str(item) for item in top_actions] if isinstance(top_actions, list) else []),
        top_nodes=top_node_cards,
        bridge_nodes=bridge_node_cards,
        isolated_pages=isolated_cards,
        hub_stubs=hub_cards,
        fragile_bridges=bridge_cards,
        isolated_clusters=cluster_cards,
        suggested_links=suggestion_cards,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a deterministic graph health report from the current ThinkWiki graph data.")
    parser.add_argument("--root", default=".", help="Wiki root path")
    args = parser.parse_args()

    root = find_repo_root(Path(args.root))
    graph = _load_graph(root)
    report = build_report(graph)

    report_dir = root / "output" / "graph"
    report_json_path = report_dir / "report.json"
    report_md_path = report_dir / "report.md"
    report_html_path = report_dir / "report.html"
    write_text(report_json_path, json.dumps(report, ensure_ascii=False, indent=2))
    write_text(report_md_path, render_report_markdown(report))
    write_text(report_html_path, render_report_html(report))
    output_home = write_output_home(root)

    append_log(root, f"[{today_str()}] graph-report | {report['stats']['nodeCount']} pages", [
        "- report html: output/graph/report.html",
        "- report: output/graph/report.md",
        "- data: output/graph/report.json",
        "- hub: output/index.html",
    ])
    print("# ThinkWiki Graph Report")
    print("")
    print(f"- Root: {root}")
    print(f"- Summary: {report['summary']}")
    print(f"- Isolated Pages: {report['stats']['isolatedPageCount']}")
    print(f"- Hub Stubs: {report['stats']['hubStubCount']}")
    print(f"- Fragile Bridges: {report['stats']['fragileBridgeCount']}")
    print(f"- Suggested Links: {report['stats']['suggestedLinkCount']}")
    print("")
    print("Top Actions:")
    for item in report["topActions"]:
        print(f"- {item}")
    print("")
    print("Graph report: output/graph/report.html")
    print(f"Graph report URI: {file_uri(report_html_path)}")
    print("Graph report markdown: output/graph/report.md")
    print("Graph report data: output/graph/report.json")
    print("Output hub: output/index.html")
    print(f"Output hub URI: {file_uri(output_home)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
