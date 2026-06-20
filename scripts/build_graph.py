#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from utils import (
    append_log,
    collect_wiki_pages,
    extract_summary,
    file_uri,
    find_repo_root,
    is_external_link,
    markdown_links,
    parse_frontmatter,
    read_text,
    today_str,
    write_text,
    write_output_home,
)

TYPE_ORDER = {
    "raw": 0,
    "file": 0,
    "source": 1,
    "topic": 2,
    "concept": 2,
    "decision": 3,
    "synthesis": 3,
    "query": 3,
    "page": 2,
}

TYPE_LANE_OFFSET = {
    "raw": 0,
    "file": 0,
    "source": 0,
    "topic": -28,
    "concept": 28,
    "decision": -28,
    "synthesis": 28,
    "query": 28,
    "page": 0,
}

TYPE_COLORS = {
    "raw": "#94a3b8",
    "file": "#94a3b8",
    "source": "#60a5fa",
    "topic": "#34d399",
    "concept": "#a78bfa",
    "decision": "#fb923c",
    "synthesis": "#22d3ee",
    "query": "#cbd5e1",
    "page": "#60a5fa",
}

EDGE_STYLES = {
    "references": {
        "stroke": "rgba(138,180,255,0.38)",
        "highlight": "rgba(138,180,255,0.98)",
        "dash": "",
    },
    "links_to": {
        "stroke": "rgba(255,255,255,0.28)",
        "highlight": "rgba(255,255,255,0.82)",
        "dash": "",
    },
    "includes": {
        "stroke": "rgba(52,211,153,0.42)",
        "highlight": "rgba(52,211,153,0.96)",
        "dash": "6 4",
    },
    "cites": {
        "stroke": "rgba(251,146,60,0.4)",
        "highlight": "rgba(251,146,60,0.96)",
        "dash": "2 6",
    },
}

TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{2,}")
COMMON_TOKENS = {
    "about",
    "after",
    "also",
    "and",
    "are",
    "between",
    "from",
    "have",
    "into",
    "that",
    "their",
    "there",
    "these",
    "this",
    "through",
    "using",
    "with",
    "wiki",
}


def normalize_sources(meta: dict[str, object]) -> list[str]:
    raw = meta.get("sources", [])
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    if raw:
        return [str(raw).strip()]
    return []


def ordered_unique(items: list[str]) -> list[str]:
    results: list[str] = []
    seen: set[str] = set()
    for item in items:
        value = str(item).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        results.append(value)
    return results


def placeholder_node(node_id: str, label: str, node_type: str) -> dict[str, object]:
    return {
        "id": node_id,
        "label": label,
        "type": node_type,
        "summary": "",
        "confidence": "",
        "status": "",
        "updated": "",
        "path": node_id,
        "sources": [],
    }


def node_payload_for_page(root: Path, page: Path, meta: dict[str, object], body: str, page_type: str) -> dict[str, object]:
    node_id = page.relative_to(root).as_posix()
    return {
        "id": node_id,
        "label": str(meta.get("title") or page.stem),
        "type": page_type,
        "summary": extract_summary(meta, body),
        "confidence": str(meta.get("confidence") or "").strip(),
        "status": str(meta.get("status") or "").strip(),
        "updated": str(meta.get("updated") or meta.get("created") or "").strip(),
        "path": node_id,
        "sources": normalize_sources(meta),
    }


def add_node(nodes: dict[str, dict[str, object]], payload: dict[str, object]) -> None:
    node_id = str(payload["id"])
    existing = nodes.get(node_id)
    if existing is None:
        nodes[node_id] = payload
        return

    existing_type = str(existing.get("type") or "")
    new_type = str(payload.get("type") or "")
    if existing_type in {"raw", "file", "page"} and new_type not in {"", existing_type, "raw"}:
        existing["type"] = new_type

    existing_label = str(existing.get("label") or "")
    new_label = str(payload.get("label") or "")
    if new_label and (existing_label == Path(node_id).stem or existing_type == "raw"):
        existing["label"] = new_label

    for key in ("summary", "confidence", "status", "updated", "path"):
        old_value = str(existing.get(key) or "").strip()
        new_value = str(payload.get(key) or "").strip()
        if new_value and not old_value:
            existing[key] = new_value

    merged_sources = ordered_unique([
        *[str(item) for item in existing.get("sources", [])],
        *[str(item) for item in payload.get("sources", [])],
    ])
    existing["sources"] = merged_sources


def add_edge(
    edges: list[dict[str, str]],
    seen_edges: set[tuple[str, str, str]],
    source: str,
    target: str,
    edge_type: str,
) -> None:
    edge_key = (source, target, edge_type)
    if edge_key not in seen_edges:
        seen_edges.add(edge_key)
        edges.append({"source": source, "target": target, "type": edge_type})


def node_type_for_path(node_id: str) -> str:
    if node_id.startswith("raw/"):
        return "raw"
    if node_id.startswith("wiki/"):
        parent_name = Path(node_id).parent.name
        if parent_name.endswith("s"):
            return parent_name[:-1]
        return "page"
    return "file"


def text_tokens(*parts: object) -> set[str]:
    tokens: set[str] = set()
    for part in parts:
        for token in TOKEN_RE.findall(str(part or "").lower()):
            if token in COMMON_TOKENS:
                continue
            tokens.add(token)
    return tokens


def node_metrics(
    nodes: list[dict[str, object]],
    edges: list[dict[str, str]],
) -> dict[str, dict[str, object]]:
    metrics: dict[str, dict[str, object]] = {
        str(node["id"]): {
            "degree": 0,
            "inbound": 0,
            "outbound": 0,
            "neighbor_ids": set(),
            "neighbor_types": set(),
            "edge_types": set(),
        }
        for node in nodes
    }

    node_type_map = {str(node["id"]): str(node.get("type") or "page") for node in nodes}
    for edge in edges:
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        edge_type = str(edge.get("type") or "links_to")
        if source not in metrics or target not in metrics:
            continue
        metrics[source]["degree"] += 1
        metrics[source]["outbound"] += 1
        metrics[source]["neighbor_ids"].add(target)
        metrics[source]["neighbor_types"].add(node_type_map.get(target, "page"))
        metrics[source]["edge_types"].add(edge_type)

        metrics[target]["degree"] += 1
        metrics[target]["inbound"] += 1
        metrics[target]["neighbor_ids"].add(source)
        metrics[target]["neighbor_types"].add(node_type_map.get(source, "page"))
        metrics[target]["edge_types"].add(edge_type)

    return metrics


def compute_link_suggestions(
    nodes: list[dict[str, object]],
    metrics: dict[str, dict[str, object]],
    edges: list[dict[str, str]],
    limit: int = 8,
) -> list[dict[str, object]]:
    undirected_edges = {
        tuple(sorted((str(edge.get("source") or ""), str(edge.get("target") or ""))))
        for edge in edges
    }
    candidates = [
        node for node in nodes if str(node.get("type") or "page") not in {"raw", "file"}
    ]
    candidate_data = {
        str(node["id"]): {
            "label": str(node.get("label") or node["id"]),
            "tokens": text_tokens(node.get("label"), node.get("summary"), node.get("path")),
            "sources": {str(item).strip() for item in node.get("sources", []) if str(item).strip()},
        }
        for node in candidates
    }

    suggestions: list[dict[str, object]] = []
    for index, left in enumerate(candidates):
        left_id = str(left["id"])
        for right in candidates[index + 1 :]:
            right_id = str(right["id"])
            if tuple(sorted((left_id, right_id))) in undirected_edges:
                continue

            left_data = candidate_data[left_id]
            right_data = candidate_data[right_id]
            shared_tokens = sorted(left_data["tokens"] & right_data["tokens"])
            shared_sources = sorted(left_data["sources"] & right_data["sources"])
            shared_neighbors = sorted(
                set(metrics[left_id]["neighbor_ids"]) & set(metrics[right_id]["neighbor_ids"])
            )

            score = 0
            reasons: list[str] = []
            if shared_sources:
                score += 5 + min(2, len(shared_sources))
                reasons.append("shared sources")
            if shared_tokens:
                score += min(4, len(shared_tokens)) * 2
                reasons.append("shared keywords")
            if shared_neighbors:
                score += 2
                reasons.append("shared graph neighbors")
            if str(left.get("type") or "") == str(right.get("type") or ""):
                score += 1

            if score < 5:
                continue

            suggestions.append({
                "source": left_id,
                "sourceLabel": left_data["label"],
                "target": right_id,
                "targetLabel": right_data["label"],
                "score": score,
                "reasons": reasons,
                "sharedTokens": shared_tokens[:4],
                "sharedSources": shared_sources[:3],
            })

    return sorted(
        suggestions,
        key=lambda item: (
            -int(item["score"]),
            str(item["sourceLabel"]).lower(),
            str(item["targetLabel"]).lower(),
        ),
    )[:limit]


def graph_summary_text(insights: dict[str, object]) -> str:
    stats = insights["stats"]
    isolated_count = int(stats["isolatedCount"])
    weak_count = int(stats["weakCount"])
    suggestion_count = len(insights["suggestedLinks"])
    bridge_count = len(insights["bridgeNodes"])
    top_node = next(iter(insights["topNodes"]), None)
    if top_node:
        lead = f"当前最关键的页面是 {top_node['title']}。"
    else:
        lead = "当前图谱还在形成阶段。"

    if isolated_count:
        health = f"有 {isolated_count} 个孤立页面需要优先补链接。"
    elif weak_count:
        health = f"有 {weak_count} 个弱连接页面值得继续整理。"
    else:
        health = "主要页面已经形成基础连接。"

    if suggestion_count:
        next_step = f"当前可优先检查 {suggestion_count} 条建议补链。"
    elif bridge_count:
        next_step = f"可以先从 {bridge_count} 个桥接页面继续扩展结构。"
    else:
        next_step = "下一步可以继续补摘要、来源或跨页面链接。"
    return " ".join([lead, health, next_step])


def compute_graph_insights(
    nodes: list[dict[str, object]],
    edges: list[dict[str, str]],
) -> dict[str, object]:
    metrics = node_metrics(nodes, edges)
    node_items: list[dict[str, object]] = []
    isolated_nodes: list[dict[str, object]] = []
    bridge_nodes: list[dict[str, object]] = []

    for node in nodes:
        node_id = str(node["id"])
        info = metrics[node_id]
        degree = int(info["degree"])
        inbound = int(info["inbound"])
        outbound = int(info["outbound"])
        neighbor_types = sorted(str(item) for item in info["neighbor_types"])
        edge_types = sorted(str(item) for item in info["edge_types"])
        top_score = degree * 3 + inbound * 2 + len(neighbor_types) * 2 + len(edge_types)
        bridge_score = len(neighbor_types) * 3 + len(edge_types) * 2 + max(0, degree - 1)

        node_item = {
            "id": node_id,
            "title": str(node.get("label") or node_id),
            "type": str(node.get("type") or "page"),
            "degree": degree,
            "inbound": inbound,
            "outbound": outbound,
            "neighborTypes": neighbor_types,
            "edgeTypes": edge_types,
            "topScore": top_score,
            "bridgeScore": bridge_score,
        }
        node_items.append(node_item)

        if degree == 0:
            isolated_nodes.append({
                "id": node_id,
                "title": node_item["title"],
                "type": node_item["type"],
                "severity": "isolated",
                "reason": "还没有和其他页面建立任何关系",
            })
        elif degree == 1:
            isolated_nodes.append({
                "id": node_id,
                "title": node_item["title"],
                "type": node_item["type"],
                "severity": "weak",
                "reason": "目前只有 1 条关系，建议继续补链",
            })

        if degree >= 2 and len(neighbor_types) >= 2:
            bridge_nodes.append({
                "id": node_id,
                "title": node_item["title"],
                "type": node_item["type"],
                "score": bridge_score,
                "reason": f"连接了 {len(neighbor_types)} 种页面类型，适合作为结构桥梁",
            })

    top_nodes = sorted(
        node_items,
        key=lambda item: (
            -int(item["topScore"]),
            -int(item["degree"]),
            str(item["title"]).lower(),
        ),
    )[:6]
    bridge_nodes = sorted(
        bridge_nodes,
        key=lambda item: (-int(item["score"]), str(item["title"]).lower()),
    )[:5]
    isolated_nodes = sorted(
        isolated_nodes,
        key=lambda item: (
            0 if str(item["severity"]) == "isolated" else 1,
            str(item["title"]).lower(),
        ),
    )[:8]
    suggested_links = compute_link_suggestions(nodes, metrics, edges)

    insights = {
        "stats": {
            "nodeCount": len(nodes),
            "edgeCount": len(edges),
            "isolatedCount": sum(1 for item in isolated_nodes if item["severity"] == "isolated"),
            "weakCount": sum(1 for item in isolated_nodes if item["severity"] == "weak"),
            "averageDegree": round((len(edges) * 2 / len(nodes)) if nodes else 0, 2),
        },
        "topNodes": [
            {
                "id": item["id"],
                "title": item["title"],
                "type": item["type"],
                "score": item["topScore"],
                "reason": f"总关系 {item['degree']}，入边 {item['inbound']}，覆盖 {len(item['neighborTypes'])} 种邻居类型",
            }
            for item in top_nodes
        ],
        "bridgeNodes": bridge_nodes,
        "isolatedNodes": isolated_nodes,
        "suggestedLinks": suggested_links,
    }
    insights["summary"] = graph_summary_text(insights)
    return insights


def compute_layout(nodes: list[dict[str, object]], edges: list[dict[str, str]]) -> tuple[dict[str, dict[str, int]], int, int]:
    columns: dict[int, list[dict[str, object]]] = {}
    degrees: dict[str, int] = {str(node["id"]): 0 for node in nodes}
    for edge in edges:
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        if source in degrees:
            degrees[source] += 1
        if target in degrees:
            degrees[target] += 1

    for node in nodes:
        column = TYPE_ORDER.get(str(node.get("type") or "page"), 2)
        columns.setdefault(column, []).append(node)

    positions: dict[str, dict[str, int]] = {}
    left_padding = 90
    top_padding = 84
    column_width = 220
    row_gap = 92
    max_rows = 1

    for column_index, items in sorted(columns.items()):
        sorted_items = sorted(
            items,
            key=lambda item: (
                -degrees.get(str(item["id"]), 0),
                TYPE_LANE_OFFSET.get(str(item.get("type") or "page"), 0),
                str(item.get("label") or "").lower(),
            ),
        )
        max_rows = max(max_rows, len(sorted_items))
        start_y = top_padding + max(0, (max_rows - len(sorted_items)) * row_gap // 2)
        for row_index, item in enumerate(sorted_items):
            node_type = str(item.get("type") or "page")
            positions[str(item["id"])] = {
                "x": left_padding + column_index * column_width + TYPE_LANE_OFFSET.get(node_type, 0),
                "y": start_y + row_index * row_gap,
            }

    width = max(960, left_padding * 2 + max(1, max(columns.keys(), default=0) + 1) * column_width + 40)
    height = max(760, top_padding * 2 + max_rows * row_gap)
    return positions, width, height


def html_payload(root: Path, graph: dict[str, object]) -> dict[str, object]:
    nodes = list(graph.get("nodes", []))
    edges = list(graph.get("edges", []))
    insights = graph.get("insights")
    if not isinstance(insights, dict):
        insights = compute_graph_insights(nodes, edges)
    positions, width, height = compute_layout(nodes, edges)

    rendered_nodes: list[dict[str, object]] = []
    for node in nodes:
        node_id = str(node["id"])
        pos = positions.get(node_id, {"x": 0, "y": 0})
        node_type = str(node.get("type") or "page")
        rendered_nodes.append({
            "id": node_id,
            "label": str(node.get("label") or node_id),
            "type": node_type,
            "summary": str(node.get("summary") or ""),
            "confidence": str(node.get("confidence") or ""),
            "status": str(node.get("status") or ""),
            "updated": str(node.get("updated") or ""),
            "path": str(node.get("path") or node_id),
            "sources": [str(item) for item in node.get("sources", [])],
            "x": pos["x"],
            "y": pos["y"],
            "color": TYPE_COLORS.get(node_type, "#60a5fa"),
        })

    return {
        "generatedAt": graph.get("generated_at") or today_str(),
        "rootName": root.name,
        "nodeCount": len(rendered_nodes),
        "edgeCount": len(edges),
        "canvasWidth": width,
        "canvasHeight": height,
        "nodes": rendered_nodes,
        "edges": edges,
        "insights": insights,
        "edgeStyles": EDGE_STYLES,
    }


def safe_json_for_script(payload: dict[str, object]) -> str:
    return (
        json.dumps(payload, ensure_ascii=False)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def render_graph_html(payload: dict[str, object]) -> str:
    data_json = safe_json_for_script(payload)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ThinkWiki Graph</title>
  <style>
    :root {{
      --bg: #0b1020;
      --panel: #121935;
      --panel-soft: #182142;
      --text: #edf2ff;
      --muted: #a8b3cf;
      --border: rgba(255, 255, 255, 0.1);
      --accent: #8ab4ff;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: linear-gradient(180deg, #0b1020 0%, #10172f 100%);
      color: var(--text);
    }}
    .layout {{
      display: grid;
      grid-template-columns: 300px 1fr 340px;
      min-height: 100vh;
    }}
    .panel {{
      padding: 20px;
      overflow: auto;
      background: rgba(9, 13, 28, 0.82);
    }}
    .panel.left {{
      border-right: 1px solid var(--border);
    }}
    .panel.right {{
      border-left: 1px solid var(--border);
    }}
    .stage {{
      overflow: auto;
      padding: 16px;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 16px;
      margin-bottom: 14px;
    }}
    .title {{
      font-size: 1.15rem;
      margin: 0 0 10px;
    }}
    .lead, .muted {{
      color: var(--muted);
      line-height: 1.6;
    }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }}
    .stat {{
      background: var(--panel-soft);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 10px;
    }}
    .stat strong {{
      display: block;
      font-size: 1.15rem;
    }}
    input, select, button {{
      width: 100%;
      border-radius: 12px;
      border: 1px solid var(--border);
      background: var(--panel);
      color: var(--text);
      padding: 10px 12px;
      margin-bottom: 10px;
    }}
    button {{
      cursor: pointer;
    }}
    .legend-item {{
      display: flex;
      gap: 8px;
      align-items: center;
      margin-bottom: 8px;
      color: var(--muted);
      font-size: 0.92rem;
    }}
    .dot {{
      width: 10px;
      height: 10px;
      border-radius: 999px;
      display: inline-block;
    }}
    .edge-swatch {{
      width: 22px;
      height: 0;
      border-top-width: 2px;
      border-top-style: solid;
      display: inline-block;
      opacity: 0.9;
    }}
    .toggle-list {{
      display: grid;
      gap: 10px;
    }}
    .focus-row {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 10px;
    }}
    .focus-chip {{
      border-radius: 999px;
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.03);
      color: var(--muted);
      padding: 9px 12px;
      font-size: 0.92rem;
      text-align: center;
    }}
    .focus-chip.active {{
      border-color: rgba(138,180,255,0.55);
      color: var(--text);
      background: rgba(138,180,255,0.12);
    }}
    .toggle-item {{
      display: flex;
      align-items: center;
      gap: 10px;
      color: var(--muted);
      font-size: 0.92rem;
    }}
    .toggle-item input {{
      width: auto;
      margin: 0;
      accent-color: #8ab4ff;
    }}
    .chip {{
      display: inline-block;
      margin: 0 8px 8px 0;
      padding: 4px 10px;
      border-radius: 999px;
      border: 1px solid var(--border);
      color: var(--muted);
      font-size: 0.85rem;
    }}
    .detail-row {{
      margin-bottom: 12px;
    }}
    .detail-row strong {{
      display: block;
      margin-bottom: 4px;
    }}
    .detail-stats {{
      display: grid;
      gap: 10px;
      margin: 12px 0;
    }}
    .detail-stat-row {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      color: var(--muted);
      font-size: 0.94rem;
      padding: 8px 10px;
      border-radius: 12px;
      background: rgba(255,255,255,0.03);
      border: 1px solid rgba(255,255,255,0.06);
    }}
    .empty {{
      color: var(--muted);
      padding: 16px;
      border: 1px dashed var(--border);
      border-radius: 12px;
    }}
    .sources {{
      max-height: 220px;
      overflow: auto;
      white-space: pre-wrap;
      word-break: break-word;
    }}
    .action {{
      display: inline-block;
      margin-top: 10px;
      color: var(--accent);
      text-decoration: none;
    }}
    .section-title {{
      margin: 18px 0 10px;
      font-size: 0.95rem;
    }}
    .insight-summary {{
      margin: 0;
      color: var(--muted);
      line-height: 1.6;
    }}
    .insight-list {{
      display: grid;
      gap: 10px;
    }}
    .insight-item {{
      width: 100%;
      text-align: left;
      background: rgba(255,255,255,0.03);
      border: 1px solid rgba(255,255,255,0.08);
      border-radius: 14px;
      padding: 12px;
      margin: 0;
    }}
    .insight-item.active {{
      border-color: rgba(138,180,255,0.52);
      background: rgba(138,180,255,0.12);
    }}
    .insight-item strong {{
      display: block;
      margin-bottom: 4px;
      font-size: 0.95rem;
    }}
    .insight-meta {{
      color: var(--muted);
      font-size: 0.88rem;
      line-height: 1.5;
    }}
    .insight-score {{
      display: inline-block;
      margin-top: 8px;
      padding: 2px 8px;
      border-radius: 999px;
      background: rgba(255,255,255,0.05);
      color: var(--muted);
      font-size: 0.82rem;
    }}
    .insight-reasons {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 8px;
    }}
    .insight-reason {{
      display: inline-block;
      padding: 3px 8px;
      border-radius: 999px;
      background: rgba(255,255,255,0.05);
      border: 1px solid rgba(255,255,255,0.08);
      color: var(--muted);
      font-size: 0.8rem;
    }}
    svg {{
      display: block;
      background:
        radial-gradient(circle at center, rgba(255, 255, 255, 0.04) 1px, transparent 1px);
      background-size: 24px 24px;
      border-radius: 16px;
    }}
    @media (max-width: 1100px) {{
      .layout {{
        grid-template-columns: 1fr;
      }}
      .panel.left, .panel.right {{
        border: 0;
        border-bottom: 1px solid var(--border);
      }}
    }}
  </style>
</head>
<body>
  <div class="layout">
    <aside class="panel left">
      <div class="card">
        <h1 class="title">ThinkWiki Graph</h1>
        <p class="lead">离线知识图谱浏览页。搜索、筛选并查看当前 wiki 的页面结构和关联关系。</p>
      </div>
      <div class="card">
        <div class="stats">
          <div class="stat"><strong>{payload["nodeCount"]}</strong><span class="muted">Nodes</span></div>
          <div class="stat"><strong>{payload["edgeCount"]}</strong><span class="muted">Edges</span></div>
        </div>
        <p class="muted">Wiki: {payload["rootName"]}</p>
        <p class="muted">Generated: {payload["generatedAt"]}</p>
      </div>
      <div class="card">
        <h2 class="title">快速聚焦</h2>
        <div class="focus-row">
          <button type="button" class="focus-chip active" data-focus-type="">全部</button>
          <button type="button" class="focus-chip" data-focus-type="concept">concepts</button>
          <button type="button" class="focus-chip" data-focus-type="decision">decisions</button>
          <button type="button" class="focus-chip" data-focus-type="source">sources</button>
        </div>
      </div>
      <div class="card">
        <input id="search" type="search" placeholder="搜索标题、路径、摘要">
        <select id="scopeFilter">
          <option value="all">全图</option>
          <option value="1">1 跳关系</option>
          <option value="2">2 跳关系</option>
        </select>
        <select id="typeFilter">
          <option value="">全部类型</option>
          <option value="source">source</option>
          <option value="topic">topic</option>
          <option value="concept">concept</option>
          <option value="decision">decision</option>
          <option value="synthesis">synthesis</option>
          <option value="query">query</option>
          <option value="raw">raw</option>
          <option value="file">file</option>
        </select>
        <select id="statusFilter">
          <option value="">全部状态</option>
          <option value="active">active</option>
          <option value="stale">stale</option>
          <option value="archived">archived</option>
          <option value="superseded">superseded</option>
        </select>
        <select id="confidenceFilter">
          <option value="">全部置信度</option>
          <option value="verified">verified</option>
          <option value="extracted">extracted</option>
          <option value="mixed">mixed</option>
          <option value="inferred">inferred</option>
        </select>
        <button id="resetBtn">重置视图</button>
      </div>
      <div class="card">
        <h2 class="title">图例</h2>
        <div class="legend-item"><span class="dot" style="background:#60a5fa"></span>source</div>
        <div class="legend-item"><span class="dot" style="background:#34d399"></span>topic</div>
        <div class="legend-item"><span class="dot" style="background:#a78bfa"></span>concept</div>
        <div class="legend-item"><span class="dot" style="background:#fb923c"></span>decision</div>
        <div class="legend-item"><span class="dot" style="background:#22d3ee"></span>synthesis</div>
        <div class="legend-item"><span class="dot" style="background:#cbd5e1"></span>query</div>
        <div class="legend-item"><span class="dot" style="background:#94a3b8"></span>raw / file</div>
      </div>
      <div class="card">
        <h2 class="title">关系图例</h2>
        <div class="legend-item"><span class="edge-swatch" style="border-top-color:rgba(138,180,255,0.85)"></span>references</div>
        <div class="legend-item"><span class="edge-swatch" style="border-top-color:rgba(255,255,255,0.65)"></span>links_to</div>
        <div class="legend-item"><span class="edge-swatch" style="border-top-color:rgba(52,211,153,0.9); border-top-style:dashed;"></span>includes</div>
        <div class="legend-item"><span class="edge-swatch" style="border-top-color:rgba(251,146,60,0.9); border-top-style:dashed;"></span>cites</div>
      </div>
      <div class="card">
        <h2 class="title">关系筛选</h2>
        <div class="toggle-list">
          <label class="toggle-item"><input type="checkbox" id="edgeType-references" checked>references</label>
          <label class="toggle-item"><input type="checkbox" id="edgeType-links_to" checked>links_to</label>
          <label class="toggle-item"><input type="checkbox" id="edgeType-includes" checked>includes</label>
          <label class="toggle-item"><input type="checkbox" id="edgeType-cites" checked>cites</label>
        </div>
      </div>
    </aside>
    <main class="stage" id="graphStage">
      <svg id="graph" viewBox="0 0 {payload["canvasWidth"]} {payload["canvasHeight"]}" width="{payload["canvasWidth"]}" height="{payload["canvasHeight"]}"></svg>
    </main>
    <aside class="panel right">
      <div class="card">
        <h2 class="title">Graph Insights</h2>
        <div id="insightsPanel" class="empty">正在加载图谱洞察...</div>
      </div>
      <div class="card">
        <h2 class="title">节点详情</h2>
        <div id="detailPanel" class="empty">点击图中的节点查看摘要、来源、状态和页面路径。</div>
      </div>
    </aside>
  </div>
  <script>
    const payload = {data_json};
    const searchEl = document.getElementById("search");
    const typeFilterEl = document.getElementById("typeFilter");
    const statusFilterEl = document.getElementById("statusFilter");
    const confidenceFilterEl = document.getElementById("confidenceFilter");
    const scopeFilterEl = document.getElementById("scopeFilter");
    const resetBtn = document.getElementById("resetBtn");
    const insightsPanel = document.getElementById("insightsPanel");
    const detailPanel = document.getElementById("detailPanel");
    const svg = document.getElementById("graph");
    const graphStage = document.getElementById("graphStage");
    const insights = payload.insights || {{
      stats: {{}},
      topNodes: [],
      bridgeNodes: [],
      isolatedNodes: [],
      suggestedLinks: [],
      summary: "",
    }};
    const edgeStyles = payload.edgeStyles || {{}};
    const edgeTypeInputs = Array.from(document.querySelectorAll('input[id^="edgeType-"]'));
    const focusButtons = Array.from(document.querySelectorAll("[data-focus-type]"));

    const nodeMap = new Map(payload.nodes.map((node) => [node.id, node]));
    const neighbors = new Map();
    payload.nodes.forEach((node) => neighbors.set(node.id, new Set()));
    payload.edges.forEach((edge) => {{
      if (neighbors.has(edge.source)) neighbors.get(edge.source).add(edge.target);
      if (neighbors.has(edge.target)) neighbors.get(edge.target).add(edge.source);
    }});

    let activeNodeId = "";
    let activeSuggestionKey = "";

    function readHashNodeId() {{
      const raw = String(window.location.hash || "").replace(/^#/, "");
      const params = new URLSearchParams(raw);
      return params.get("node") || "";
    }}

    function updateHash(nodeId) {{
      const params = new URLSearchParams();
      if (nodeId) params.set("node", nodeId);
      const nextHash = params.toString();
      if ((window.location.hash || "").replace(/^#/, "") !== nextHash) {{
        window.location.hash = nextHash;
      }}
    }}

    function escapeHtml(value) {{
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
    }}

    function suggestionKey(sourceId, targetId) {{
      return [String(sourceId || ""), String(targetId || "")].sort().join("::");
    }}

    function activeSuggestionNodeIds() {{
      return new Set(
        String(activeSuggestionKey || "")
          .split("::")
          .filter(Boolean)
      );
    }}

    function enabledEdgeTypes() {{
      const enabled = new Set(
        edgeTypeInputs
          .filter((input) => input.checked)
          .map((input) => input.id.replace("edgeType-", ""))
      );
      return enabled.size ? enabled : new Set(Object.keys(edgeStyles));
    }}

    function syncFocusButtons() {{
      const activeType = typeFilterEl.value || "";
      focusButtons.forEach((button) => {{
        const buttonType = button.getAttribute("data-focus-type") || "";
        button.classList.toggle("active", buttonType === activeType);
      }});
    }}

    function visibleNodeIds() {{
      const query = searchEl.value.trim().toLowerCase();
      const typeNeedle = typeFilterEl.value.trim().toLowerCase();
      const statusNeedle = statusFilterEl.value.trim().toLowerCase();
      const confidenceNeedle = confidenceFilterEl.value.trim().toLowerCase();
      const enabledTypes = enabledEdgeTypes();
      const filteredIds = new Set();

      payload.nodes.forEach((node) => {{
        const haystack = [
          node.label,
          node.path,
          node.summary,
          node.type,
          ...(node.sources || []),
        ].join(" ").toLowerCase();

        if (typeNeedle && String(node.type || "").toLowerCase() !== typeNeedle) return;
        if (statusNeedle && String(node.status || "").toLowerCase() !== statusNeedle) return;
        if (confidenceNeedle && String(node.confidence || "").toLowerCase() !== confidenceNeedle) return;
        if (query && !haystack.includes(query)) return;

        filteredIds.add(node.id);
      }});

      const scope = scopeFilterEl.value || "all";
      if (!activeNodeId || !filteredIds.has(activeNodeId) || scope === "all") {{
        return filteredIds;
      }}

      const maxDepth = scope === "2" ? 2 : 1;
      const scopedIds = new Set([activeNodeId]);
      let frontier = new Set([activeNodeId]);

      for (let depth = 0; depth < maxDepth; depth += 1) {{
        const nextFrontier = new Set();
        frontier.forEach((nodeId) => {{
          payload.edges.forEach((edge) => {{
            if (!enabledTypes.has(edge.type || "")) return;
            let neighborId = "";
            if (edge.source === nodeId) neighborId = edge.target;
            else if (edge.target === nodeId) neighborId = edge.source;
            else return;
            if (!filteredIds.has(neighborId) || scopedIds.has(neighborId)) return;
            scopedIds.add(neighborId);
            nextFrontier.add(neighborId);
          }});
        }});
        frontier = nextFrontier;
        if (!frontier.size) break;
      }}

      return scopedIds;
    }}

    function createSvgEl(name, attrs = {{}}) {{
      const el = document.createElementNS("http://www.w3.org/2000/svg", name);
      Object.entries(attrs).forEach(([key, value]) => el.setAttribute(key, String(value)));
      return el;
    }}

    function centerNodeInStage(nodeId) {{
      if (!nodeId || !graphStage || !nodeMap.has(nodeId)) return;
      const node = nodeMap.get(nodeId);
      const targetLeft = Math.max(0, node.x - graphStage.clientWidth / 2);
      const targetTop = Math.max(0, node.y - graphStage.clientHeight / 2);
      graphStage.scrollTo({{ left: targetLeft, top: targetTop, behavior: "smooth" }});
    }}

    function edgeStatsForNode(nodeId) {{
      const stats = {{
        total: 0,
        references: 0,
        links_to: 0,
        includes: 0,
        cites: 0,
      }};
      payload.edges.forEach((edge) => {{
        if (edge.source !== nodeId && edge.target !== nodeId) return;
        stats.total += 1;
        const edgeType = edge.type || "links_to";
        if (edgeType in stats) {{
          stats[edgeType] += 1;
        }}
      }});
      return stats;
    }}

    function renderInsightNodeList(title, items, options = {{}}) {{
      const emptyText = options.emptyText || "当前没有可显示的项目。";
      if (!items || !items.length) {{
        return `
          <h3 class="section-title">${{escapeHtml(title)}}</h3>
          <div class="empty">${{escapeHtml(emptyText)}}</div>
        `;
      }}
      const activeSuggestionNodes = activeSuggestionNodeIds();
      const body = items.map((item) => {{
        const isActive = activeNodeId === item.id || activeSuggestionNodes.has(item.id);
        const score = item.score ? `<span class="insight-score">score ${{escapeHtml(item.score)}}</span>` : "";
        return `
          <button
            type="button"
            class="insight-item${{isActive ? " active" : ""}}"
            data-insight-node="${{escapeHtml(item.id)}}"
          >
            <strong>${{escapeHtml(item.title)}}</strong>
            <div class="insight-meta">${{escapeHtml(item.reason || "")}}</div>
            ${{score}}
          </button>
        `;
      }}).join("");
      return `<h3 class="section-title">${{escapeHtml(title)}}</h3><div class="insight-list">${{body}}</div>`;
    }}

    function renderSuggestionList(items) {{
      if (!items || !items.length) {{
        return `
          <h3 class="section-title">Suggested Links</h3>
          <div class="empty">当前没有高置信度的建议补链。</div>
        `;
      }}
      const body = items.map((item) => {{
        const itemKey = suggestionKey(item.source, item.target);
        const isActive = activeSuggestionKey === itemKey;
        const reasons = (item.reasons || []).map((reason) =>
          `<span class="insight-reason">${{escapeHtml(reason)}}</span>`
        ).join("");
        return `
          <button
            type="button"
            class="insight-item${{isActive ? " active" : ""}}"
            data-suggestion-source="${{escapeHtml(item.source)}}"
            data-suggestion-target="${{escapeHtml(item.target)}}"
          >
            <strong>${{escapeHtml(item.sourceLabel)}} → ${{escapeHtml(item.targetLabel)}}</strong>
            <div class="insight-meta">建议补链，帮助用户在图谱里显式建立上下文。</div>
            <span class="insight-score">score ${{escapeHtml(item.score)}}</span>
            <div class="insight-reasons">${{reasons}}</div>
          </button>
        `;
      }}).join("");
      return `<h3 class="section-title">Suggested Links</h3><div class="insight-list">${{body}}</div>`;
    }}

    function renderInsights() {{
      const stats = insights.stats || {{}};
      const overviewStats = `
        <div class="stats">
          <div class="stat"><strong>${{escapeHtml(stats.nodeCount || 0)}}</strong><span class="muted">Nodes</span></div>
          <div class="stat"><strong>${{escapeHtml(stats.edgeCount || 0)}}</strong><span class="muted">Edges</span></div>
          <div class="stat"><strong>${{escapeHtml(stats.isolatedCount || 0)}}</strong><span class="muted">Isolated</span></div>
          <div class="stat"><strong>${{escapeHtml(stats.averageDegree || 0)}}</strong><span class="muted">Avg Degree</span></div>
        </div>
      `;
      const selectionNote = activeSuggestionKey
        ? `<p class="insight-summary">当前高亮的是一条建议补链，图中会用虚线显示推荐连接。</p>`
        : activeNodeId
          ? `<p class="insight-summary">当前已选中节点，洞察列表会同步高亮相关页面。</p>`
          : "";

      insightsPanel.className = "";
      insightsPanel.innerHTML = `
        ${{overviewStats}}
        <p class="insight-summary">${{escapeHtml(insights.summary || "图谱已生成，可以从关键节点开始探索。")}}</p>
        ${{selectionNote}}
        ${{renderInsightNodeList("Key Pages", insights.topNodes || [], {{ emptyText: "还没有足够多的节点来识别关键页面。" }})}}
        ${{renderInsightNodeList("Bridge Pages", insights.bridgeNodes || [], {{ emptyText: "当前还没有明显的桥接页面。" }})}}
        ${{renderInsightNodeList("Pages That Need Links", insights.isolatedNodes || [], {{ emptyText: "当前没有孤立或弱连接页面。" }})}}
        ${{renderSuggestionList(insights.suggestedLinks || [])}}
      `;
    }}

    function renderDetail(node) {{
      if (!node) {{
        detailPanel.className = "empty";
        detailPanel.textContent = "点击图中的节点查看摘要、来源、状态和页面路径。";
        return;
      }}

      detailPanel.className = "";
      const viewerHref = "../viewer/index.html#page=" + encodeURIComponent(node.path || node.id);
      const homeHref = "../index.html";
      const sources = (node.sources && node.sources.length)
        ? node.sources.map((item) => escapeHtml(item)).join("<br>")
        : "n/a";
      const edgeStats = edgeStatsForNode(node.id);
      const edgeStatsHtml = `
        <div class="detail-stats">
          <div class="detail-stat-row"><span>total</span><strong>${{edgeStats.total}}</strong></div>
          <div class="detail-stat-row"><span>references</span><strong>${{edgeStats.references}}</strong></div>
          <div class="detail-stat-row"><span>links_to</span><strong>${{edgeStats.links_to}}</strong></div>
          <div class="detail-stat-row"><span>includes</span><strong>${{edgeStats.includes}}</strong></div>
          <div class="detail-stat-row"><span>cites</span><strong>${{edgeStats.cites}}</strong></div>
        </div>
      `;

      detailPanel.innerHTML = `
        <h3 style="margin-top:0;">${{escapeHtml(node.label)}}</h3>
        <div>
          <span class="chip">${{escapeHtml(node.type || "page")}}</span>
          <span class="chip">${{escapeHtml(node.confidence || "n/a")}}</span>
          <span class="chip">${{escapeHtml(node.status || "n/a")}}</span>
        </div>
        <div class="detail-row"><strong>Path</strong>${{escapeHtml(node.path || node.id)}}</div>
        <div class="detail-row"><strong>Updated</strong>${{escapeHtml(node.updated || "n/a")}}</div>
        <div class="detail-row"><strong>Summary</strong>${{escapeHtml(node.summary || "(no summary)")}}</div>
        <div class="detail-row"><strong>Relation Stats</strong>${{edgeStatsHtml}}</div>
        <div class="detail-row"><strong>Sources</strong><div class="sources">${{sources}}</div></div>
        <a class="action" href="${{viewerHref}}" target="_blank" rel="noopener">打开本地浏览页</a>
        <a class="action" href="${{homeHref}}" target="_blank" rel="noopener">打开成果入口页</a>
      `;
    }}

    function selectNode(nodeId, options = {{}}) {{
      activeNodeId = nodeMap.has(nodeId) ? nodeId : "";
      activeSuggestionKey = options.keepSuggestion ? activeSuggestionKey : "";
      if (options.updateHash !== false) {{
        updateHash(activeNodeId);
      }}
      renderInsights();
      renderDetail(activeNodeId ? nodeMap.get(activeNodeId) : null);
      renderGraph();
      centerNodeInStage(activeNodeId);
    }}

    function selectSuggestedLink(sourceId, targetId) {{
      activeSuggestionKey = suggestionKey(sourceId, targetId);
      activeNodeId = nodeMap.has(sourceId) ? sourceId : "";
      updateHash(activeNodeId);
      renderInsights();
      renderDetail(activeNodeId ? nodeMap.get(activeNodeId) : null);
      renderGraph();
      centerNodeInStage(activeNodeId);
    }}

    function renderGraph() {{
      svg.innerHTML = "";
      const visibleIds = visibleNodeIds();
      const enabledTypes = enabledEdgeTypes();
      const suggestedNodes = activeSuggestionNodeIds();

      payload.edges.forEach((edge) => {{
        if (!enabledTypes.has(edge.type || "")) return;
        if (!visibleIds.has(edge.source) || !visibleIds.has(edge.target)) return;
        const sourceNode = nodeMap.get(edge.source);
        const targetNode = nodeMap.get(edge.target);
        if (!sourceNode || !targetNode) return;

        const related = activeNodeId && (edge.source === activeNodeId || edge.target === activeNodeId);
        const edgeStyle = edgeStyles[edge.type] || edgeStyles.links_to || {{
          stroke: "rgba(255,255,255,0.28)",
          highlight: "rgba(255,255,255,0.82)",
          dash: "",
        }};
        const line = createSvgEl("line", {{
          x1: sourceNode.x,
          y1: sourceNode.y,
          x2: targetNode.x,
          y2: targetNode.y,
          stroke: related ? edgeStyle.highlight : edgeStyle.stroke,
          "stroke-width": related ? 2.4 : 1.35,
          opacity: activeNodeId ? (related ? 1 : 0.42) : 0.92,
        }});
        if (edgeStyle.dash) {{
          line.setAttribute("stroke-dasharray", edgeStyle.dash);
        }}
        line.setAttribute("data-edge-type", edge.type || "");
        svg.appendChild(line);
      }});

      if (suggestedNodes.size === 2) {{
        const [sourceId, targetId] = Array.from(suggestedNodes.values());
        if (visibleIds.has(sourceId) && visibleIds.has(targetId)) {{
          const sourceNode = nodeMap.get(sourceId);
          const targetNode = nodeMap.get(targetId);
          if (sourceNode && targetNode) {{
            const suggestionLine = createSvgEl("line", {{
              x1: sourceNode.x,
              y1: sourceNode.y,
              x2: targetNode.x,
              y2: targetNode.y,
              stroke: "rgba(138,180,255,0.96)",
              "stroke-width": 2.6,
              opacity: 0.96,
            }});
            suggestionLine.setAttribute("stroke-dasharray", "10 6");
            suggestionLine.setAttribute("data-suggested-link", activeSuggestionKey);
            svg.appendChild(suggestionLine);
          }}
        }}
      }}

      payload.nodes.forEach((node) => {{
        if (!visibleIds.has(node.id)) return;
        const isNeighbor = activeNodeId && (neighbors.get(activeNodeId) || new Set()).has(node.id);
        const isActive = activeNodeId === node.id;
        const isSuggested = suggestedNodes.has(node.id);
        const faded = activeNodeId && !isActive && !isNeighbor && !isSuggested;

        const group = createSvgEl("g", {{
          transform: `translate(${{node.x}}, ${{node.y}})`,
          style: "cursor:pointer;",
        }});
        const circle = createSvgEl("circle", {{
          r: isActive ? 16 : isSuggested ? 14 : 12,
          fill: node.color || "#60a5fa",
          stroke: isActive ? "#ffffff" : isSuggested ? "#8ab4ff" : "rgba(255,255,255,0.25)",
          "stroke-width": isActive ? 2.4 : isSuggested ? 2 : 1.2,
          opacity: faded ? 0.62 : 1,
        }});
        const label = createSvgEl("text", {{
          x: 18,
          y: 5,
          fill: "#edf2ff",
          "font-size": 12,
          opacity: faded ? 0.7 : 0.94,
        }});
        label.textContent = node.label;

        group.appendChild(circle);
        group.appendChild(label);
        group.addEventListener("click", () => {{
          selectNode(node.id);
        }});
        svg.appendChild(group);
      }});
    }}

    function resetView() {{
      activeNodeId = "";
      activeSuggestionKey = "";
      updateHash("");
      renderInsights();
      renderDetail(null);
      renderGraph();
    }}

    insightsPanel.addEventListener("click", (event) => {{
      const target = event.target.closest("button");
      if (!target) return;
      const nodeId = target.getAttribute("data-insight-node") || "";
      if (nodeId) {{
        selectNode(nodeId, {{ updateHash: true, keepSuggestion: false }});
        return;
      }}
      const sourceId = target.getAttribute("data-suggestion-source") || "";
      const targetId = target.getAttribute("data-suggestion-target") || "";
      if (sourceId && targetId) {{
        selectSuggestedLink(sourceId, targetId);
      }}
    }});

    searchEl.addEventListener("input", () => {{
      renderInsights();
      renderGraph();
    }});
    scopeFilterEl.addEventListener("change", () => {{
      renderInsights();
      renderGraph();
    }});
    typeFilterEl.addEventListener("change", () => {{
      syncFocusButtons();
      renderInsights();
      renderGraph();
    }});
    statusFilterEl.addEventListener("change", () => {{
      renderInsights();
      renderGraph();
    }});
    confidenceFilterEl.addEventListener("change", () => {{
      renderInsights();
      renderGraph();
    }});
    edgeTypeInputs.forEach((input) => input.addEventListener("change", () => {{
      renderInsights();
      renderGraph();
    }}));
    focusButtons.forEach((button) => button.addEventListener("click", () => {{
      typeFilterEl.value = button.getAttribute("data-focus-type") || "";
      syncFocusButtons();
      renderInsights();
      renderGraph();
    }}));
    resetBtn.addEventListener("click", resetView);
    window.addEventListener("hashchange", () => {{
      const nextNodeId = readHashNodeId();
      selectNode(nextNodeId, {{ updateHash: false }});
    }});

    const initialNodeId = readHashNodeId();
    activeNodeId = nodeMap.has(initialNodeId) ? initialNodeId : "";
    syncFocusButtons();
    renderInsights();
    renderDetail(activeNodeId ? nodeMap.get(activeNodeId) : null);
    renderGraph();
    centerNodeInStage(activeNodeId);
  </script>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Build graph data from wiki pages.")
    parser.add_argument("--root", default=".", help="Wiki root path")
    args = parser.parse_args()

    root = find_repo_root(Path(args.root))
    pages = collect_wiki_pages(root)
    page_ids = {page.resolve(): page.relative_to(root).as_posix() for page in pages}
    nodes: dict[str, dict[str, object]] = {}
    edges: list[dict[str, str]] = []
    seen_edges: set[tuple[str, str, str]] = set()

    for page in pages:
        meta, body = parse_frontmatter(read_text(page))
        node_id = page.relative_to(root).as_posix()
        page_type = str(meta.get("type") or page.parent.name[:-1])
        add_node(nodes, node_payload_for_page(root, page, meta, body, page_type))

        for source in normalize_sources(meta):
            source_path = (root / source).resolve()
            source_id = source_path.relative_to(root).as_posix() if source_path.is_relative_to(root) else source
            source_type = node_type_for_path(source_id)
            add_node(nodes, placeholder_node(source_id, Path(source_id).stem, source_type))
            edge_type = "cites" if source_type == "raw" else "includes" if page_type == "topic" else "references"
            add_edge(edges, seen_edges, node_id, source_id, edge_type)

        for link in markdown_links(body):
            if is_external_link(link):
                continue
            target = (page.parent / link).resolve()
            target_id = page_ids.get(target)
            if target_id:
                add_edge(edges, seen_edges, node_id, target_id, "links_to")

    graph_nodes = sorted(nodes.values(), key=lambda node: str(node["id"]))
    graph_edges = sorted(edges, key=lambda edge: (edge["source"], edge["type"], edge["target"]))
    insights = compute_graph_insights(graph_nodes, graph_edges)
    graph = {
        "generated_at": today_str(),
        "nodes": graph_nodes,
        "edges": graph_edges,
        "insights": insights,
    }
    graph_dir = root / "output" / "graph"
    graph_json_path = graph_dir / "graph.json"
    graph_md_path = graph_dir / "graph.md"
    graph_html_path = graph_dir / "index.html"
    write_text(graph_json_path, json.dumps(graph, ensure_ascii=False, indent=2))

    lines = [
        "# Knowledge Graph",
        "",
        f"- Nodes: {len(graph_nodes)}",
        f"- Edges: {len(graph_edges)}",
        f"- Summary: {insights['summary']}",
        "",
        "## Key Pages",
    ]
    lines.extend(
        f"- {item['title']} ({item['type']}) | score={item['score']} | {item['reason']}"
        for item in insights["topNodes"]
    )
    lines.extend(["", "## Suggested Links"])
    if insights["suggestedLinks"]:
        lines.extend(
            f"- {item['source']} <-> {item['target']} | score={item['score']} | {', '.join(item['reasons'])}"
            for item in insights["suggestedLinks"]
        )
    else:
        lines.append("- No suggested links")
    lines.extend(["", "## Nodes"])
    lines.extend(f"- {node['type']}: {node['label']} ({node['id']})" for node in graph_nodes)
    lines.extend(["", "## Edges"])
    lines.extend(f"- {edge['source']} --{edge['type']}--> {edge['target']}" for edge in graph_edges)
    write_text(graph_md_path, "\n".join(lines))
    write_text(graph_html_path, render_graph_html(html_payload(root, graph)))
    output_home = write_output_home(root)

    append_log(root, f"[{today_str()}] graph | {len(graph_nodes)} nodes, {len(graph_edges)} edges", [
        "- data: output/graph/graph.json",
        "- summary: output/graph/graph.md",
        "- viewer: output/graph/index.html",
        "- hub: output/index.html",
    ])
    print(f"Built graph with {len(graph_nodes)} nodes and {len(graph_edges)} edges")
    print("Graph data: output/graph/graph.json")
    print("Graph summary: output/graph/graph.md")
    print("Graph viewer: output/graph/index.html")
    print(f"Graph viewer URI: {file_uri(graph_html_path)}")
    print("Output hub: output/index.html")
    print(f"Output hub URI: {file_uri(output_home)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
