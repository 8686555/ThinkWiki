from __future__ import annotations

import json
import os
import re
import shutil
from datetime import date, datetime
from html import escape
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

ROOT_MARKER = ".wiki-schema.md"
WIKI_DIRS = ["concepts", "topics", "sources", "syntheses", "queries", "decisions"]
PAGE_TYPE_TO_DIR = {
    "concept": "concepts",
    "topic": "topics",
    "source": "sources",
    "synthesis": "syntheses",
    "query": "queries",
    "decision": "decisions",
}
SECTION_ORDER = [
    ("Topics", "topic"),
    ("Concepts", "concept"),
    ("Sources", "source"),
    ("Syntheses", "synthesis"),
    ("Queries", "query"),
    ("Decisions", "decision"),
]
REQUIRED_FIELDS = ["title", "type", "created", "updated", "sources", "tags", "confidence", "status"]


def today_str() -> str:
    return date.today().isoformat()


def now_slug() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S")


def slugify(text: str, fallback_prefix: str = "item") -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text or f"{fallback_prefix}-{now_slug()}"


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[1]


def unique_paths(paths: Iterable[Path]) -> list[Path]:
    results: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path.expanduser())
        if key in seen:
            continue
        seen.add(key)
        results.append(path.expanduser())
    return results


def candidate_dependency_paths(
    *,
    env_name: str,
    skill_name: str,
    relative_path: str,
    command_names: Iterable[str] = (),
    script_file: str | Path | None = None,
) -> list[Path]:
    candidates: list[Path] = []
    env_value = os.environ.get(env_name, "").strip()
    if env_value:
        candidates.append(Path(env_value))

    script_root = repo_root_from_script()
    if script_file is not None:
        script_root = Path(script_file).resolve().parents[1]
    cwd = Path.cwd().resolve()
    relative = Path(relative_path)

    # 1) Installed as sibling skills under the same `.trae/skills` directory.
    skill_containers = [script_root.parent, cwd.parent]

    # 2) Running from a project root that contains `.trae/skills`.
    for base in unique_paths([cwd, *cwd.parents, script_root, *script_root.parents]):
        skill_containers.append(base / ".trae" / "skills")

    # 3) Common "project directory next to this repo" layout used in local workspaces.
    sibling_roots = unique_paths([script_root.parent, cwd.parent])
    for parent in sibling_roots:
        try:
            for child in parent.iterdir():
                if child.is_dir():
                    skill_containers.append(child / ".trae" / "skills")
        except OSError:
            continue

    for container in unique_paths(skill_containers):
        candidates.append(container / skill_name / relative)

    for command_name in command_names:
        resolved = shutil.which(command_name)
        if resolved:
            candidates.append(Path(resolved))

    return unique_paths(candidates)


def find_repo_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ROOT_MARKER).exists():
            return candidate
    raise FileNotFoundError(f"Cannot find {ROOT_MARKER} from {current}")


def ensure_runtime_dirs(root: Path) -> None:
    for relative in [
        "raw/articles",
        "raw/papers",
        "raw/books",
        "raw/conversations",
        "raw/web",
        "raw/assets",
        "raw/inbox",
        "normalized/articles",
        "normalized/papers",
        "normalized/books",
        "normalized/conversations",
        "normalized/web",
        "normalized/assets",
        "normalized/inbox",
        "wiki/concepts",
        "wiki/topics",
        "wiki/sources",
        "wiki/syntheses",
        "wiki/queries",
        "wiki/decisions",
        "output/graph",
        "output/viewer",
        "output/inbox",
        "output/exports",
    ]:
        (root / relative).mkdir(parents=True, exist_ok=True)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def file_uri(path: Path) -> str:
    return path.resolve().as_uri()


def display_root_arg(root: Path) -> str:
    repo_root = repo_root_from_script()
    demo_root = (repo_root / "docs" / "demo-wiki").resolve()
    try:
        if root.resolve() == demo_root:
            return "<wiki-root>"
    except OSError:
        pass
    return str(root)


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _first_markdown_heading(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if line.startswith("# "):
                return line[2:].strip()
    except OSError:
        return ""
    return ""


def _page_sort_key(page: dict) -> tuple[str, str]:
    return (str(page.get("updated", "") or ""), str(page.get("title", "") or ""))


def _humanize_label(value: str) -> str:
    text = re.sub(r"[-_]+", " ", value).strip()
    return text or value or "Untitled"


def _inbox_quality(item: dict) -> tuple[str, str]:
    kind = str(item.get("kind", "") or "")
    adapter = str(item.get("adapter", "") or "")
    summary = str(item.get("summary", "") or "").strip()
    title = str(item.get("title", "") or "").strip()
    site_name = str(item.get("site_name", "") or "").strip()
    source_url = str(item.get("source_url", "") or "").strip()
    author = str(item.get("author", "") or "").strip()
    publish_date = str(item.get("publish_date", "") or "").strip()

    score = 0
    if title and len(title) >= 4:
        score += 1
    if summary and summary not in {"(no summary)", "(no summary yet)"} and len(summary) >= 24:
        score += 2
    if source_url:
        score += 1
    if site_name:
        score += 1
    if author:
        score += 1
    if publish_date:
        score += 1
    if adapter == "wechat":
        score += 1
    if kind == "web" and not source_url:
        score -= 2

    if score >= 5:
        return "ready", "网页元数据较完整，适合继续复核后正式 ingest。"
    if score >= 3:
        return "review", "内容已可读，但建议先核对来源、作者或发布时间。"
    return "weak", "提取信息偏少，建议优先人工检查正文质量和来源信息。"


def _capture_state_reason(state: str) -> str:
    if state == "wait_completed":
        return "等待模式下已抓到更完整正文。"
    if state == "wait_timeout":
        return "等待模式已结束，但正文仍不够稳定，建议人工复核。"
    if state == "needs_review":
        return "本次采集已完成，但正文完整度一般。"
    return "采集状态正常。"


def _capture_reason_hint(reason: str, fallback: str) -> str:
    if reason == "loading_placeholder":
        return "页面仍像加载占位，建议稍后重试，或用 wait 模式重新抓取。"
    if reason == "body_too_short":
        return "正文太短，建议先人工确认这是不是完整文章页。"
    if reason == "sparse_structure":
        return "正文结构偏稀疏，可能只抓到了摘要或页头区域。"
    if reason == "metadata_sparse":
        return "作者、来源或发布时间信息不足，建议人工补核。"
    return fallback or "采集结果结构完整。"


def collect_inbox_items(root: Path) -> list[dict]:
    inbox_dir = root / "normalized" / "inbox"
    if not inbox_dir.exists():
        return []

    def sort_key(path: Path) -> tuple[float, str]:
        try:
            return (path.stat().st_mtime, path.name)
        except OSError:
            return (0.0, path.name)

    paths = sorted(inbox_dir.glob("*.md"), key=sort_key, reverse=True)
    items: list[dict] = []
    for path in paths:
        text = read_text(path)
        meta, body = parse_frontmatter(text)
        repo_path = path.relative_to(root).as_posix()
        sidecar_path = path.with_suffix(".json")
        sidecar = _load_json(sidecar_path)
        title = (
            _first_markdown_heading(path)
            or str(meta.get("title", "") or "").strip()
            or _humanize_label(path.stem)
        )
        summary = extract_summary(meta, body)
        try:
            updated = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        except OSError:
            updated = "n/a"
        quality_status, quality_reason = _inbox_quality({
            "kind": str(sidecar.get("kind", "") or ""),
            "adapter": str(sidecar.get("adapter", "") or ""),
            "summary": summary,
            "title": title,
            "site_name": str(sidecar.get("siteName", "") or ""),
            "source_url": str(sidecar.get("url", "") or ""),
            "author": str(sidecar.get("author", "") or ""),
            "publish_date": str(sidecar.get("publishDate", "") or ""),
        })
        capture_state = str(sidecar.get("captureState", "") or "")
        capture_mode = str(sidecar.get("captureMode", "") or "")
        capture_reason = str(sidecar.get("captureReason", "") or "")
        review_hint = str(sidecar.get("reviewHint", "") or "")
        items.append({
            "title": title,
            "summary": summary,
            "updated": updated,
            "path": repo_path,
            "href": Path(os.path.relpath(path, start=root / "output")).as_posix(),
            "ingest_command": f"python scripts/thinkwiki ingest --root {display_root_arg(root)} --source {repo_path}",
            "kind": str(sidecar.get("kind", "") or ""),
            "adapter": str(sidecar.get("adapter", "") or ""),
            "site_name": str(sidecar.get("siteName", "") or ""),
            "author": str(sidecar.get("author", "") or ""),
            "publish_date": str(sidecar.get("publishDate", "") or ""),
            "source_url": str(sidecar.get("url", "") or ""),
            "metadata_path": sidecar_path.relative_to(root).as_posix() if sidecar_path.exists() else "",
            "capture_state": capture_state,
            "capture_mode": capture_mode,
            "capture_attempts": int(sidecar.get("captureAttempts", 0) or 0),
            "capture_elapsed_seconds": sidecar.get("captureElapsedSeconds", ""),
            "capture_state_reason": _capture_state_reason(capture_state),
            "capture_reason": capture_reason,
            "review_hint": _capture_reason_hint(capture_reason, review_hint),
            "media_policy": str(sidecar.get("mediaPolicy", "") or ""),
            "media_status": str(sidecar.get("mediaStatus", "") or ""),
            "media_count": int(sidecar.get("mediaCount", 0) or 0),
            "localized_media_count": int(sidecar.get("localizedMediaCount", 0) or 0),
            "media_dir": str(sidecar.get("mediaDir", "") or ""),
            "quality_status": quality_status,
            "quality_reason": quality_reason,
        })
    return items


def batch_ingest_command(root: Path, quality: str = "ready", limit: int | None = None, dry_run: bool = False) -> str:
    command = f"python scripts/thinkwiki batch-ingest --root {display_root_arg(root)} --quality {quality}"
    if limit is not None and limit > 0:
        command += f" --limit {limit}"
    if dry_run:
        command += " --dry-run"
    return command


def _inbox_groups(items: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {"ready": [], "review": [], "weak": [], "other": []}
    for item in items:
        status = str(item.get("quality_status", "") or "")
        if status not in groups:
            status = "other"
        groups[status].append(item)
    return groups


def _inbox_quality_summary(items: list[dict]) -> dict[str, int]:
    groups = _inbox_groups(items)
    return {key: len(value) for key, value in groups.items()}


def _priority_inbox_items(items: list[dict], limit: int = 3) -> list[dict]:
    groups = _inbox_groups(items)
    ranked: list[dict] = []
    for status in ["ready", "review", "weak", "other"]:
        ranked.extend(groups.get(status, []))
    return ranked[:limit]


def _render_command_list(commands: list[str], empty_text: str) -> str:
    if not commands:
        return "<div class='empty small'>{}</div>".format(escape(empty_text))
    rows = [
        "<pre class='command-pre'>{}</pre>".format(escape(command))
        for command in commands
    ]
    return "\n".join(rows)


def _render_page_list(items: list[dict], empty_text: str) -> str:
    if not items:
        return "<div class='empty small'>{}</div>".format(escape(empty_text))
    cards: list[str] = []
    for item in items:
        page_id = str(item.get("id", ""))
        title = str(item.get("title", page_id or "Untitled"))
        summary = str(item.get("summary", "") or "(no summary yet)")
        page_type = str(item.get("type", "page") or "page")
        updated = str(item.get("updated", "") or "n/a")
        href = "viewer/index.html#page={}".format(escape(page_id, quote=True))
        cards.append(
            "<a class='mini-card' href='{href}' target='_blank' rel='noopener'>"
            "<div class='mini-meta'><span class='mini-type'>{page_type}</span><span>{updated}</span></div>"
            "<strong>{title}</strong>"
            "<span>{summary}</span>"
            "</a>".format(
                href=href,
                page_type=escape(page_type),
                updated=escape(updated),
                title=escape(title),
                summary=escape(summary),
            )
        )
    return "\n".join(cards)


def _render_bullet_list(items: list[str], empty_text: str) -> str:
    if not items:
        return "<div class='empty small'>{}</div>".format(escape(empty_text))
    rows = [
        "<li>{}</li>".format(item)
        for item in items
    ]
    return "<ul class='bullet-list'>{}</ul>".format("".join(rows))


def _render_action_cards(items: list[dict], empty_text: str) -> str:
    if not items:
        return "<div class='empty small'>{}</div>".format(escape(empty_text))
    cards: list[str] = []
    for item in items:
        href = str(item.get("href", "") or "")
        title = str(item.get("title", "Untitled"))
        summary = str(item.get("summary", "") or "")
        label = str(item.get("label", "") or "")
        target_attrs = " target='_blank' rel='noopener'" if href else ""
        tag_html = "<span class='action-tag'>{}</span>".format(escape(label)) if label else ""
        cards.append(
            "<a class='action-card' href='{href}'{target_attrs}>"
            "{tag_html}"
            "<strong>{title}</strong>"
            "<span>{summary}</span>"
            "</a>".format(
                href=escape(href or "#", quote=True),
                target_attrs=target_attrs,
                tag_html=tag_html,
                title=escape(title),
                summary=escape(summary),
            )
        )
    return "\n".join(cards)


def _render_inbox_list(items: list[dict], empty_text: str) -> str:
    if not items:
        return "<div class='empty small'>{}</div>".format(escape(empty_text))
    cards: list[str] = []
    for item in items:
        kind = str(item.get("kind", "") or "")
        adapter = str(item.get("adapter", "") or "")
        mini_type = adapter or kind or "inbox"
        detail_parts = [
            str(item.get("site_name", "") or ""),
            str(item.get("author", "") or ""),
        ]
        detail_text = " · ".join(part for part in detail_parts if part)
        detail_html = "<span>{}</span>".format(escape(detail_text)) if detail_text else ""
        quality_status = str(item.get("quality_status", "") or "")
        quality_html = ""
        if quality_status:
            quality_html = "<span class='quality quality-{status}'>{label}</span>".format(
                status=escape(quality_status),
                label=escape(f"quality: {quality_status}"),
            )
        capture_state = str(item.get("capture_state", "") or "")
        capture_html = ""
        if capture_state:
            capture_html = "<span class='quality quality-{status}'>{label}</span>".format(
                status=escape(capture_state),
                label=escape(f"capture: {capture_state}"),
            )
        capture_reason = str(item.get("capture_reason", "") or "")
        reason_html = ""
        if capture_reason and capture_reason != "ready":
            reason_html = "<span class='quality quality-media'>{label}</span>".format(
                label=escape(f"reason: {capture_reason}"),
            )
        media_status = str(item.get("media_status", "") or "")
        media_html = ""
        if media_status:
            media_html = "<span class='quality quality-media'>{label}</span>".format(
                label=escape(f"media: {media_status}"),
            )
        cards.append(
            "<a class='mini-card' href='{href}' target='_blank' rel='noopener'>"
            "<div class='mini-meta'><span class='mini-type'>{mini_type}</span><span>{updated}</span></div>"
            "<strong>{title}</strong>"
            "<span>{summary}</span>"
            "{detail_html}"
            "{quality_html}"
            "{capture_html}"
            "{reason_html}"
            "{media_html}"
            "<code>{path}</code>"
            "</a>".format(
                href=escape(str(item.get("href", "") or "#"), quote=True),
                mini_type=escape(mini_type),
                updated=escape(str(item.get("updated", "") or "n/a")),
                title=escape(str(item.get("title", "Untitled"))),
                summary=escape(str(item.get("summary", "") or "(no summary yet)")),
                detail_html=detail_html,
                quality_html=quality_html,
                capture_html=capture_html,
                reason_html=reason_html,
                media_html=media_html,
                path=escape(str(item.get("path", "") or "")),
            )
        )
    return "\n".join(cards)


def _render_inbox_review_cards(items: list[dict], inbox_dir: Path, root: Path) -> str:
    cards: list[str] = []
    for item in items:
        normalized_target = root / str(item.get("path", ""))
        normalized_href = Path(os.path.relpath(normalized_target, start=inbox_dir)).as_posix()
        metadata_path = str(item.get("metadata_path", "") or "")
        metadata_target = root / metadata_path if metadata_path else None
        metadata_href = ""
        if metadata_target is not None and metadata_target.exists():
            metadata_href = Path(os.path.relpath(metadata_target, start=inbox_dir)).as_posix()
        meta_rows: list[str] = []
        for label, value in [
            ("Adapter", str(item.get("adapter", "") or "")),
            ("Mode", str(item.get("capture_mode", "") or "")),
            ("State", str(item.get("capture_state", "") or "")),
            ("Reason", str(item.get("capture_reason", "") or "")),
            ("Media", str(item.get("media_status", "") or "")),
            ("Source", str(item.get("site_name", "") or "")),
            ("Author", str(item.get("author", "") or "")),
            ("Published", str(item.get("publish_date", "") or "")),
            ("Quality", str(item.get("quality_status", "") or "")),
        ]:
            if value:
                meta_rows.append(
                    "<span class='fact'><strong>{label}</strong>{value}</span>".format(
                        label=escape(label + ": "),
                        value=escape(value),
                    )
                )
        attempts = int(item.get("capture_attempts", 0) or 0)
        elapsed = str(item.get("capture_elapsed_seconds", "") or "")
        if attempts:
            meta_rows.append(
                "<span class='fact'><strong>Attempts: </strong>{value}</span>".format(value=escape(str(attempts)))
            )
        if elapsed:
            meta_rows.append(
                "<span class='fact'><strong>Elapsed: </strong>{value}s</span>".format(value=escape(elapsed))
            )
        media_count = int(item.get("media_count", 0) or 0)
        localized_media_count = int(item.get("localized_media_count", 0) or 0)
        if media_count:
            meta_rows.append(
                "<span class='fact'><strong>Media files: </strong>{value}</span>".format(
                    value=escape(f"{localized_media_count}/{media_count}")
                )
            )
        media_dir = str(item.get("media_dir", "") or "")
        if media_dir:
            meta_rows.append(
                "<span class='fact'><strong>Media dir: </strong>{value}</span>".format(value=escape(media_dir))
            )
        source_url = str(item.get("source_url", "") or "")
        if source_url:
            meta_rows.append(
                "<a class='fact fact-link' href='{href}' target='_blank' rel='noopener'><strong>URL: </strong>{value}</a>".format(
                    href=escape(source_url, quote=True),
                    value=escape(source_url),
                )
            )
        cards.append(
            "<article class='card'>"
            "<div class='meta'><span class='tag'>{tag}</span><span>{updated}</span></div>"
            "<h3>{title}</h3>"
            "<p>{summary}</p>"
            "<div class='facts'>{facts}</div>"
            "<div class='path'><code>{path}</code></div>"
            "<div class='quality-note'>{capture_reason}</div>"
            "<div class='quality-note'>{review_hint}</div>"
            "<div class='quality-note'>{quality_reason}</div>"
            "<div class='actions'>"
            "<a href='{normalized_href}' target='_blank' rel='noopener'>Open normalized note</a>"
            "<a href='../index.html' target='_blank' rel='noopener'>Open workspace home</a>"
            "{metadata_link}"
            "</div>"
            "<div class='command-label'>Next ingest command</div>"
            "<pre>{command}</pre>"
            "</article>".format(
                tag=escape(str(item.get("adapter", "") or item.get("kind", "") or "inbox")),
                updated=escape(str(item.get("updated", "") or "n/a")),
                title=escape(str(item.get("title", "Untitled"))),
                summary=escape(str(item.get("summary", "") or "(no summary yet)")),
                facts="".join(meta_rows),
                path=escape(str(item.get("path", "") or "")),
                capture_reason=escape(str(item.get("capture_state_reason", "") or "")),
                review_hint=escape(str(item.get("review_hint", "") or "")),
                quality_reason=escape(str(item.get("quality_reason", "") or "")),
                normalized_href=escape(normalized_href, quote=True),
                metadata_link=(
                    "<a href='{href}' target='_blank' rel='noopener'>Open metadata</a>".format(
                        href=escape(metadata_href, quote=True)
                    )
                    if metadata_href
                    else ""
                ),
                command=escape(str(item.get("ingest_command", "") or "")),
            )
        )
    return "\n".join(cards)


def _render_inbox_review_section(
    *,
    anchor: str,
    title: str,
    description: str,
    items: list[dict],
    inbox_dir: Path,
    root: Path,
    empty_text: str,
) -> str:
    cards_html = _render_inbox_review_cards(items, inbox_dir, root) if items else "<div class='empty'>{}</div>".format(escape(empty_text))
    commands = [str(item.get("ingest_command", "") or "") for item in items[:3] if str(item.get("ingest_command", "") or "")]
    if anchor == "ready" and items:
        commands = [
            batch_ingest_command(root, quality="ready", dry_run=True),
            batch_ingest_command(root, quality="ready"),
            *commands,
        ]
    command_html = _render_command_list(commands, "当前分组还没有推荐命令。")
    return (
        "<section class='group' id='{anchor}'>"
        "<div class='group-head'>"
        "<div><h2>{title}</h2><p>{description}</p></div>"
        "<span class='badge'>条目 {count}</span>"
        "</div>"
        "<div class='group-commands'>"
        "<div class='command-label'>建议优先执行的下一步命令</div>"
        "{commands}"
        "</div>"
        "<div class='cards'>{cards}</div>"
        "</section>"
    ).format(
        anchor=escape(anchor, quote=True),
        title=escape(title),
        description=escape(description),
        count=escape(str(len(items))),
        commands=command_html,
        cards=cards_html,
    )


def _recent_pages(pages: list[dict], limit: int = 4) -> list[dict]:
    return sorted(pages, key=_page_sort_key, reverse=True)[:limit]


def _generated_pages(pages: list[dict], limit: int = 4) -> list[dict]:
    generated = [
        page
        for page in pages
        if str(page.get("type", "")) in {"concept", "decision", "synthesis", "query"}
    ]
    return sorted(generated, key=_page_sort_key, reverse=True)[:limit]


def _featured_pages(pages: list[dict], limit: int = 4) -> list[dict]:
    featured = [
        page
        for page in pages
        if str(page.get("type", "")) in {"concept", "decision", "synthesis", "source"}
    ]
    return sorted(featured, key=_page_sort_key, reverse=True)[:limit]


def _attention_items(pages: list[dict], graph_insights: dict, graph_report: dict) -> list[str]:
    items: list[str] = []
    isolated_nodes = graph_insights.get("isolatedNodes", []) if isinstance(graph_insights, dict) else []
    weak_pages = [item for item in isolated_nodes if str(item.get("severity", "")) == "weak"]
    isolated_pages = [item for item in isolated_nodes if str(item.get("severity", "")) == "isolated"]
    if isolated_pages:
        items.append("当前有 <strong>{}</strong> 个孤立页面，建议优先补链接或补来源。".format(len(isolated_pages)))
    if weak_pages:
        items.append("当前有 <strong>{}</strong> 个弱连接页面，适合继续整理上下文。".format(len(weak_pages)))

    report_stats = graph_report.get("stats", {}) if isinstance(graph_report.get("stats"), dict) else {}
    hub_stubs = int(report_stats.get("hubStubCount", 0) or 0)
    fragile_bridges = int(report_stats.get("fragileBridgeCount", 0) or 0)
    isolated_clusters = int(report_stats.get("isolatedClusterCount", 0) or 0)
    if hub_stubs:
        items.append("有 <strong>{}</strong> 个高连接薄内容页面，建议优先补摘要和上下文。".format(hub_stubs))
    if fragile_bridges:
        items.append("有 <strong>{}</strong> 个脆弱桥接页面，建议补强主题之间的连接。".format(fragile_bridges))
    if isolated_clusters:
        items.append("当前存在 <strong>{}</strong> 个脱离主图的页面簇，建议尽快接回主图。".format(isolated_clusters))

    missing_summary = [
        page for page in pages
        if str(page.get("summary", "") or "").strip() in {"", "(no summary)", "(no summary yet)"}
    ]
    if missing_summary:
        items.append("有 <strong>{}</strong> 个页面还没有可靠摘要。".format(len(missing_summary)))

    missing_sources = [
        page for page in pages
        if not isinstance(page.get("sources"), list) or not list(page.get("sources") or [])
    ]
    if missing_sources:
        items.append("有 <strong>{}</strong> 个页面缺少来源信息。".format(len(missing_sources)))

    return items[:4]


def _recommended_actions(
    *,
    viewer_exists: bool,
    graph_exists: bool,
    graph_insights: dict,
    graph_report: dict,
    graph_report_exists: bool,
    recent_pages: list[dict],
    inbox_page_exists: bool,
    inbox_count: int,
    inbox_items: list[dict],
) -> list[dict]:
    actions: list[dict] = []
    ready_items = [item for item in inbox_items if str(item.get("quality_status", "") or "") == "ready"]
    if ready_items:
        actions.append({
            "label": "Ingest",
            "title": "优先处理 Ready Inbox",
            "summary": "当前有 {} 条可直接继续复核并 ingest 的 inbox 条目，建议先看最上面的 ready 分组。".format(len(ready_items)),
            "href": "inbox/index.html#ready" if inbox_page_exists else str(ready_items[0].get("href", "") or "#"),
        })
    if inbox_count:
        actions.append({
            "label": "Review",
            "title": "处理 Inbox 待办",
            "summary": "当前有 {} 条已采集内容，先检查最近一条，再决定是否正式 ingest。".format(inbox_count),
            "href": "inbox/index.html" if inbox_page_exists else str((inbox_items[0] if inbox_items else {}).get("href", "") or "#"),
        })
    if viewer_exists:
        actions.append({
            "label": "Read",
            "title": "打开本地浏览页",
            "summary": "按页面类型、状态和置信度快速浏览整个 wiki。",
            "href": "viewer/index.html",
        })
    if graph_exists:
        summary = "进入图谱页，查看关键页面、桥接页面和建议补链。"
        actions.append({
            "label": "Explore",
            "title": "打开知识图谱",
            "summary": summary,
            "href": "graph/index.html",
        })
    if graph_report_exists:
        report_actions = graph_report.get("topActions", []) if isinstance(graph_report.get("topActions"), list) else []
        actions.append({
            "label": "Govern",
            "title": "查看图谱治理报告",
            "summary": str(report_actions[0]) if report_actions else "查看孤立页面、脆弱桥接和建议补链的治理摘要。",
            "href": "graph/report.html",
        })

    stats = graph_insights.get("stats", {}) if isinstance(graph_insights, dict) else {}
    isolated_count = int(stats.get("isolatedCount", 0) or 0)
    if graph_exists and isolated_count:
        actions.append({
            "label": "Fix",
            "title": "处理孤立页面",
            "summary": "当前有 {} 个孤立页面，建议先在图谱中检查并补链。".format(isolated_count),
            "href": "graph/index.html",
        })

    suggested_links = graph_insights.get("suggestedLinks", []) if isinstance(graph_insights, dict) else []
    if graph_exists and suggested_links:
        actions.append({
            "label": "Link",
            "title": "检查建议补链",
            "summary": "图谱已识别 {} 条高置信度建议补链。".format(len(suggested_links)),
            "href": "graph/index.html",
        })

    if recent_pages:
        page_id = str(recent_pages[0].get("id", "") or "")
        if page_id:
            actions.append({
                "label": "Latest",
                "title": "查看最近更新页面",
                "summary": "从最近更新的页面继续阅读或整理。",
                "href": "viewer/index.html#page={}".format(escape(page_id, quote=True)),
            })

    if not actions:
        actions.append({
            "label": "Build",
            "title": "生成浏览页和图谱页",
            "summary": "先运行 viewer 和 graph，让首页可以展示完整工作台内容。",
            "href": "",
        })
    return actions[:4]


def write_output_home(root: Path) -> Path:
    output_dir = root / "output"
    viewer_path = output_dir / "viewer" / "index.html"
    graph_path = output_dir / "graph" / "index.html"
    graph_report_path = output_dir / "graph" / "report.html"
    inbox_path = output_dir / "inbox" / "index.html"
    viewer_data = _load_json(output_dir / "viewer" / "viewer.json")
    graph_data = _load_json(output_dir / "graph" / "graph.json")
    graph_report = _load_json(output_dir / "graph" / "report.json")
    wiki_title = _first_markdown_heading(root / "index.md") or root.name
    generated_at = str(
        graph_report.get("generated_at")
        or viewer_data.get("generatedAt")
        or graph_data.get("generated_at")
        or today_str()
    )
    page_count = int(viewer_data.get("pageCount", 0) or 0)
    node_count = len(graph_data.get("nodes", [])) if isinstance(graph_data.get("nodes"), list) else 0
    edge_count = len(graph_data.get("edges", [])) if isinstance(graph_data.get("edges"), list) else 0
    graph_insights = graph_data.get("insights", {}) if isinstance(graph_data.get("insights"), dict) else {}
    ready_outputs = int(viewer_path.exists()) + int(graph_path.exists()) + int(inbox_path.exists())
    pages = viewer_data.get("pages", []) if isinstance(viewer_data.get("pages"), list) else []
    all_inbox_items = collect_inbox_items(root)
    inbox_count = len(all_inbox_items)
    inbox_items = all_inbox_items[:4]
    inbox_summary = _inbox_quality_summary(all_inbox_items)
    recent_pages = _recent_pages(pages)
    generated_pages = _generated_pages(pages)
    featured_pages = _featured_pages(pages)
    attention_items = _attention_items(pages, graph_insights, graph_report)
    graph_summary = str(graph_insights.get("summary", "") or "").strip()
    graph_stats = graph_insights.get("stats", {}) if isinstance(graph_insights, dict) else {}
    graph_report_stats = graph_report.get("stats", {}) if isinstance(graph_report.get("stats"), dict) else {}
    key_pages = graph_insights.get("topNodes", []) if isinstance(graph_insights.get("topNodes"), list) else []
    output_items: list[str] = []
    for title, path, summary in [
        ("Inbox Review", inbox_path, "查看待处理 inbox 条目，并复制下一步 ingest 命令"),
        ("本地浏览页", viewer_path, "按页面类型、置信度和状态浏览整个 wiki"),
        ("知识图谱", graph_path, "查看页面之间的引用、包含、关键页面和建议补链"),
        ("图谱治理报告", graph_report_path, "查看孤立页面、脆弱桥接、孤立子图和治理建议"),
    ]:
        if not path.exists():
            continue
        relative = path.relative_to(output_dir).as_posix()
        output_items.append(
            "<a class='card' href='{href}' target='_blank' rel='noopener'>"
            "<strong>{title}</strong>"
            "<span>{summary}</span>"
            "<code>{path}</code>"
            "</a>".format(
                href=escape(relative),
                title=escape(title),
                summary=escape(summary),
                path=escape(relative),
            )
        )
    if not output_items:
        output_items.append("<div class='empty'>还没有可浏览的成果页。先运行 viewer 或 graph 命令。</div>")

    stats: list[str] = []
    for label, value in [
        ("成果页", ready_outputs),
        ("Inbox", inbox_count),
        ("Ready", inbox_summary.get("ready", 0)),
        ("页面数", page_count),
        ("图节点", node_count),
        ("图关系", edge_count),
    ]:
        stats.append(
            "<div class='stat'><strong>{value}</strong><span>{label}</span></div>".format(
                value=escape(str(value)),
                label=escape(label),
            )
        )
    recent_pages_html = _render_page_list(recent_pages, "还没有可推荐的最近页面。先运行 viewer 生成浏览成果页。")
    generated_pages_html = _render_page_list(generated_pages, "还没有最近生成的 query / synthesis / decision / concept 页面。")
    featured_pages_html = _render_page_list(featured_pages, "还没有代表性页面。")
    attention_html = _render_bullet_list(attention_items, "当前没有明显需要优先处理的问题。")
    actions_html = _render_action_cards(
        _recommended_actions(
            viewer_exists=viewer_path.exists(),
            graph_exists=graph_path.exists(),
            graph_insights=graph_insights,
            graph_report=graph_report,
            graph_report_exists=graph_report_path.exists(),
            recent_pages=recent_pages,
            inbox_page_exists=inbox_path.exists(),
            inbox_count=inbox_count,
            inbox_items=all_inbox_items,
        ),
        "当前还没有可推荐的下一步动作。",
    )
    inbox_html = _render_inbox_list(inbox_items, "还没有待处理的 inbox 条目。你可以先运行 clip 采集网页、文本或文件。")
    graph_snapshot_items: list[str] = []
    report_summary = str(graph_report.get("summary", "") or "").strip()
    if report_summary:
        graph_snapshot_items.append("<div class='snapshot-copy'>{}</div>".format(escape(report_summary)))
    elif graph_summary:
        graph_snapshot_items.append("<div class='snapshot-copy'>{}</div>".format(escape(graph_summary)))
    if key_pages:
        graph_snapshot_items.append(
            "<div class='snapshot-chip'>当前关键页面: <strong>{}</strong></div>".format(
                escape(str(key_pages[0].get("title", "") or "n/a"))
            )
        )
    suggested_count = len(graph_insights.get("suggestedLinks", [])) if isinstance(graph_insights.get("suggestedLinks"), list) else 0
    hub_stub_count = int(graph_report_stats.get("hubStubCount", 0) or 0)
    fragile_bridge_count = int(graph_report_stats.get("fragileBridgeCount", 0) or 0)
    isolated_cluster_count = int(graph_report_stats.get("isolatedClusterCount", 0) or 0)
    graph_snapshot_items.append(
        "<div class='snapshot-chip'>孤立页面 {isolated} 个</div>"
        "<div class='snapshot-chip'>建议补链 {links} 条</div>"
        "<div class='snapshot-chip'>Hub Stubs {hub_stubs} 个</div>"
        "<div class='snapshot-chip'>Fragile Bridges {fragile} 个</div>"
        "<div class='snapshot-chip'>Isolated Clusters {clusters} 个</div>".format(
            isolated=escape(str(int(graph_report_stats.get("isolatedPageCount", graph_stats.get("isolatedCount", 0)) or 0))),
            links=escape(str(suggested_count)),
            hub_stubs=escape(str(hub_stub_count)),
            fragile=escape(str(fragile_bridge_count)),
            clusters=escape(str(isolated_cluster_count)),
        )
    )
    report_actions = graph_report.get("topActions", []) if isinstance(graph_report.get("topActions"), list) else []
    if report_actions:
        graph_snapshot_items.append(_render_bullet_list(
            [escape(str(item)) for item in report_actions[:3]],
            "当前没有额外治理动作。",
        ))
    graph_snapshot_html = "\n".join(graph_snapshot_items) if graph_snapshot_items else "<div class='empty small'>图谱洞察将在生成 graph 后显示。</div>"

    html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ThinkWiki Outputs</title>
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
      display: grid;
      place-items: center;
      padding: 24px;
    }}
    .shell {{
      width: min(880px, 100%);
      background: rgba(9, 13, 28, 0.86);
      border: 1px solid var(--border);
      border-radius: 24px;
      padding: 28px;
    }}
    h1, p {{ margin-top: 0; }}
    .lead {{
      color: var(--muted);
      line-height: 1.6;
      margin-bottom: 20px;
    }}
    .hero {{
      display: grid;
      gap: 18px;
      margin-bottom: 24px;
    }}
    .eyebrow {{
      color: var(--accent);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 0.82rem;
      margin-bottom: 10px;
    }}
    .hero-title {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      flex-wrap: wrap;
    }}
    .hero-title h1 {{
      margin-bottom: 0;
    }}
    .meta {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }}
    .badge {{
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 6px 12px;
      color: var(--muted);
      font-size: 0.92rem;
      background: rgba(255,255,255,0.03);
    }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
      gap: 12px;
    }}
    .stat {{
      border: 1px solid var(--border);
      background: var(--panel);
      border-radius: 18px;
      padding: 16px;
    }}
    .stat strong {{
      display: block;
      font-size: 1.45rem;
      margin-bottom: 6px;
    }}
    .stat span {{
      color: var(--muted);
    }}
    .grid {{
      display: grid;
      gap: 14px;
    }}
    .workspace-grid {{
      display: grid;
      gap: 14px;
      grid-template-columns: 1.1fr 0.9fr;
      margin-top: 18px;
    }}
    .section-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
      margin-top: 18px;
    }}
    .panel {{
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.02);
      border-radius: 18px;
      padding: 18px;
    }}
    .panel h2 {{
      margin: 0 0 8px;
      font-size: 1rem;
    }}
    .panel p {{
      margin: 0 0 14px;
      color: var(--muted);
      line-height: 1.5;
    }}
    .card {{
      display: block;
      text-decoration: none;
      color: inherit;
      border: 1px solid var(--border);
      background: var(--panel);
      border-radius: 18px;
      padding: 18px;
    }}
    .card:hover {{
      border-color: rgba(138,180,255,0.55);
      box-shadow: 0 0 0 1px rgba(138,180,255,0.18);
    }}
    .card strong {{
      display: block;
      margin-bottom: 6px;
      font-size: 1.05rem;
    }}
    .card span {{
      display: block;
      color: var(--muted);
      margin-bottom: 10px;
    }}
    code {{
      color: var(--accent);
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      word-break: break-word;
    }}
    .empty {{
      border: 1px dashed var(--border);
      border-radius: 18px;
      padding: 18px;
      color: var(--muted);
    }}
    .small {{
      padding: 14px;
      font-size: 0.95rem;
    }}
    .mini-card {{
      display: block;
      text-decoration: none;
      color: inherit;
      border: 1px solid var(--border);
      background: rgba(18, 25, 53, 0.85);
      border-radius: 16px;
      padding: 14px;
      margin-bottom: 10px;
    }}
    .mini-card:last-child {{
      margin-bottom: 0;
    }}
    .mini-card:hover {{
      border-color: rgba(138,180,255,0.55);
    }}
    .mini-card strong {{
      display: block;
      margin-bottom: 6px;
    }}
    .quality {{
      display: inline-block;
      margin-top: 8px;
      border-radius: 999px;
      padding: 4px 8px;
      font-size: 0.82rem;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
    .quality-ready {{
      background: rgba(47, 163, 91, 0.16);
      color: #8de2a7;
    }}
    .quality-review {{
      background: rgba(242, 166, 43, 0.16);
      color: #ffd08a;
    }}
    .quality-weak {{
      background: rgba(214, 77, 77, 0.16);
      color: #ff9f9f;
    }}
    .quality-media {{
      background: rgba(104, 114, 255, 0.16);
      color: #b9c0ff;
    }}
    .mini-card span {{
      display: block;
      color: var(--muted);
      line-height: 1.45;
    }}
    .mini-meta {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 8px;
      color: var(--muted);
      font-size: 0.88rem;
    }}
    .mini-type {{
      text-transform: uppercase;
      letter-spacing: 0.04em;
      color: var(--accent);
    }}
    .guide {{
      margin-top: 18px;
      border: 1px solid rgba(138,180,255,0.22);
      background: rgba(138,180,255,0.08);
      border-radius: 18px;
      padding: 16px 18px;
    }}
    .guide strong {{
      display: block;
      margin-bottom: 8px;
    }}
    .guide span {{
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
    .bullet-list strong {{
      color: var(--text);
    }}
    .actions {{
      display: grid;
      gap: 10px;
    }}
    .action-card {{
      display: block;
      text-decoration: none;
      color: inherit;
      border: 1px solid var(--border);
      background: rgba(18, 25, 53, 0.85);
      border-radius: 16px;
      padding: 14px;
    }}
    .action-card:hover {{
      border-color: rgba(138,180,255,0.55);
    }}
    .action-card strong {{
      display: block;
      margin: 6px 0;
    }}
    .action-card span {{
      color: var(--muted);
      line-height: 1.45;
      display: block;
    }}
    .action-tag {{
      display: inline-block;
      font-size: 0.8rem;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      color: var(--accent);
    }}
    .snapshot {{
      display: grid;
      gap: 10px;
    }}
    .snapshot-copy {{
      color: var(--muted);
      line-height: 1.55;
    }}
    .snapshot-chip {{
      border: 1px solid var(--border);
      border-radius: 14px;
      background: rgba(255,255,255,0.03);
      padding: 12px 14px;
      color: var(--muted);
    }}
    .snapshot-chip strong {{
      color: var(--text);
    }}
    @media (max-width: 720px) {{
      .stats {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
      .workspace-grid {{
        grid-template-columns: 1fr;
      }}
      .section-grid {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <div class="eyebrow">Knowledge Workspace</div>
      <div class="hero-title">
        <h1>{wiki_title}</h1>
        <div class="meta">
          <span class="badge">知识工作台首页</span>
          <span class="badge">生成日期 {generated_at}</span>
        </div>
      </div>
      <p class="lead">这里不只是成果入口页，而是当前 wiki 的工作台首页。你可以先看最近发生了什么、哪些页面值得继续整理，以及 inbox 里还有哪些采集内容待正式入库，再决定进入浏览页还是图谱页。</p>
      <div class="stats">
        {stats}
      </div>
    </section>
    <div class="workspace-grid">
      <section class="panel">
        <h2>What Changed</h2>
        <p>这里汇总最近更新和最近生成的页面，帮助你快速判断这次整理后 wiki 发生了什么变化。</p>
        {recent_pages}
        <div style="height: 12px;"></div>
        {generated_pages}
      </section>
      <section class="panel">
        <h2>Next Actions</h2>
        <p>从这里直接进入最值得继续操作的下一步，而不是手动判断应该先看哪里。</p>
        <div class="actions">
          {actions}
        </div>
      </section>
    </div>
    <div class="workspace-grid">
      <section class="panel">
        <h2>Needs Attention</h2>
        <p>优先显示当前知识库里还比较薄弱的地方，例如孤立页面、弱连接页面、缺摘要或缺来源的页面。</p>
        {attention}
      </section>
      <section class="panel">
        <h2>Graph Snapshot</h2>
        <p>直接读取知识图谱的结构洞察，让首页先告诉你现在图里最值得关注的地方。</p>
        <div class="snapshot">
          {graph_snapshot}
        </div>
      </section>
    </div>
    <div class="section-grid">
      <section class="panel">
        <h2>Featured Pages</h2>
        <p>优先展示 concept、decision、synthesis 和 source，帮助你快速抓到这个知识库最有价值的沉淀。</p>
        {featured_pages}
      </section>
      <section class="panel">
        <h2>Outputs Overview</h2>
        <p>浏览页和图谱页仍然是最重要的两个成果入口，但现在它们被纳入统一工作台视图。</p>
        <div class="grid">
          {items}
        </div>
      </section>
      <section class="panel">
        <h2>Inbox Queue</h2>
        <p>这里显示最近采集到 inbox 的内容。你可以先打开原始条目做快速复核，再决定是否运行 ingest 正式入库。</p>
        {inbox_items}
      </section>
    </div>
    <div class="guide">
      <strong>从这里开始</strong>
      <span>先看 `What Changed`、`Needs Attention` 和 `Inbox Queue`，再决定进入浏览页或图谱页。如果你刚导入或采集了新资料，建议重新运行 viewer 和 graph 以刷新工作台首页。</span>
    </div>
  </main>
</body>
</html>
""".format(
        wiki_title=escape(wiki_title),
        generated_at=escape(generated_at),
        stats="\n".join(stats),
        items="\n".join(output_items),
        recent_pages=recent_pages_html,
        generated_pages=generated_pages_html,
        actions=actions_html,
        attention=attention_html,
        graph_snapshot=graph_snapshot_html,
        featured_pages=featured_pages_html,
        inbox_items=inbox_html,
    )
    target = output_dir / "index.html"
    write_text(target, html)
    return target


def write_inbox_review(root: Path) -> Path:
    output_dir = root / "output"
    inbox_dir = output_dir / "inbox"
    inbox_path = inbox_dir / "index.html"
    items = collect_inbox_items(root)
    groups = _inbox_groups(items)
    summary = _inbox_quality_summary(items)
    priority_items = _priority_inbox_items(items)
    priority_commands = [str(item.get("ingest_command", "") or "") for item in priority_items if str(item.get("ingest_command", "") or "")]
    priority_html = _render_inbox_list(priority_items, "还没有可优先处理的 inbox 条目。")
    sections_html = "\n".join([
        _render_inbox_review_section(
            anchor="ready",
            title="Ready To Ingest",
            description="这一组的网页元数据和正文完整度都比较好，通常适合先做最终复核，然后正式 ingest。",
            items=groups.get("ready", []),
            inbox_dir=inbox_dir,
            root=root,
            empty_text="当前还没有可直接 ingest 的 ready 条目。",
        ),
        _render_inbox_review_section(
            anchor="review",
            title="Needs Review",
            description="这一组通常已经可读，但还建议核对来源、作者、发布时间或页面主内容是否完整。",
            items=groups.get("review", []),
            inbox_dir=inbox_dir,
            root=root,
            empty_text="当前没有处于 review 状态的条目。",
        ),
        _render_inbox_review_section(
            anchor="weak",
            title="Weak Captures",
            description="这一组优先做人工检查，确认是不是抓到了 loading 页、摘要页或信息过少的内容。",
            items=groups.get("weak", []),
            inbox_dir=inbox_dir,
            root=root,
            empty_text="当前没有 weak 条目。",
        ),
    ]) if items else "<div class='empty'>还没有待处理的 inbox 条目。先运行 `python scripts/thinkwiki clip ...` 采集网页、文本或文件。</div>"
    html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ThinkWiki Inbox Review</title>
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
      width: min(1100px, 100%);
      margin: 0 auto;
    }}
    .hero {{
      margin-bottom: 22px;
      border: 1px solid var(--border);
      background: rgba(9, 13, 28, 0.86);
      border-radius: 24px;
      padding: 28px;
    }}
    .eyebrow {{
      color: var(--accent);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 0.82rem;
      margin-bottom: 10px;
    }}
    h1, h2, p {{ margin-top: 0; }}
    .lead {{
      color: var(--muted);
      line-height: 1.6;
      margin-bottom: 18px;
      max-width: 70ch;
    }}
    .hero-grid {{
      display: grid;
      grid-template-columns: minmax(0, 1.2fr) minmax(300px, 0.8fr);
      gap: 16px;
      align-items: start;
    }}
    .badges {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }}
    .badge {{
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 6px 12px;
      color: var(--muted);
      background: rgba(255,255,255,0.03);
    }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 14px;
    }}
    .panel {{
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.03);
      border-radius: 18px;
      padding: 18px;
    }}
    .summary-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin: 18px 0 0;
    }}
    .summary-stat {{
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 14px;
      background: rgba(255,255,255,0.03);
    }}
    .summary-stat strong {{
      display: block;
      font-size: 1.4rem;
      margin-bottom: 6px;
    }}
    .summary-stat span {{
      color: var(--muted);
    }}
    .group {{
      margin-top: 18px;
      border: 1px solid var(--border);
      background: rgba(9, 13, 28, 0.78);
      border-radius: 22px;
      padding: 20px;
    }}
    .group-head {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: start;
      margin-bottom: 16px;
    }}
    .group-head p {{
      color: var(--muted);
      margin-bottom: 0;
      max-width: 70ch;
    }}
    .group-commands {{
      margin-bottom: 16px;
    }}
    .command-pre {{
      margin-bottom: 10px;
    }}
    .card {{
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.03);
      border-radius: 18px;
      padding: 18px;
    }}
    .card h3 {{
      margin-top: 0;
    }}
    .meta {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      color: var(--muted);
      font-size: 0.9rem;
      margin-bottom: 10px;
    }}
    .tag {{
      color: var(--accent);
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
    .card p {{
      color: var(--muted);
      line-height: 1.55;
    }}
    .facts {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 14px;
    }}
    .fact {{
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 6px 10px;
      color: var(--muted);
      background: rgba(255,255,255,0.02);
      font-size: 0.9rem;
      text-decoration: none;
    }}
    .fact strong {{
      color: var(--text);
    }}
    .fact-link {{
      max-width: 100%;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}
    .path {{
      margin: 14px 0;
    }}
    .quality-note {{
      color: var(--muted);
      line-height: 1.5;
      margin-bottom: 14px;
    }}
    .actions {{
      display: flex;
      gap: 14px;
      flex-wrap: wrap;
      margin-bottom: 14px;
    }}
    a {{
      color: var(--accent);
      text-decoration: none;
    }}
    a:hover {{
      text-decoration: underline;
    }}
    .command-label {{
      color: var(--muted);
      font-size: 0.92rem;
      margin-bottom: 8px;
    }}
    pre {{
      margin: 0;
      padding: 14px;
      border-radius: 14px;
      border: 1px solid var(--border);
      background: var(--panel);
      color: var(--accent);
      white-space: pre-wrap;
      word-break: break-word;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    }}
    .empty {{
      border: 1px dashed var(--border);
      border-radius: 18px;
      padding: 18px;
      color: var(--muted);
      background: rgba(255,255,255,0.02);
    }}
    @media (max-width: 900px) {{
      .hero-grid {{
        grid-template-columns: 1fr;
      }}
      .summary-grid {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
    }}
    @media (max-width: 640px) {{
      .summary-grid {{
        grid-template-columns: 1fr;
      }}
      .group-head {{
        flex-direction: column;
      }}
    }}
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <div class="eyebrow">Inbox Review</div>
      <div class="hero-grid">
        <div>
          <h1>{wiki_title}</h1>
          <p class="lead">这里集中显示已经 clip 到 inbox、但还没有正式 ingest 的内容。现在它会按 `ready / review / weak` 分组，帮助你先处理最值得正式入库的条目，再回头处理需要人工检查的内容。</p>
          <div class="badges">
            <span class="badge">待处理条目 {count}</span>
            <span class="badge"><a href="../index.html" target="_blank" rel="noopener">Open workspace home</a></span>
          </div>
          <div class="summary-grid">
            <div class="summary-stat"><strong>{count}</strong><span>Total</span></div>
            <div class="summary-stat"><strong>{ready_count}</strong><span>Ready</span></div>
            <div class="summary-stat"><strong>{review_count}</strong><span>Review</span></div>
            <div class="summary-stat"><strong>{weak_count}</strong><span>Weak</span></div>
          </div>
        </div>
        <div class="panel">
          <h2>Priority Queue</h2>
          <p>这里先列出最值得优先处理的条目。通常顺序是 ready -> review -> weak。</p>
          {priority_items}
          <div class="command-label" style="margin-top: 14px;">优先建议命令</div>
          {priority_commands}
        </div>
      </div>
    </section>
    {sections}
  </main>
</body>
</html>
""".format(
        wiki_title=escape(_first_markdown_heading(root / "index.md") or root.name),
        count=escape(str(len(items))),
        ready_count=escape(str(summary.get("ready", 0))),
        review_count=escape(str(summary.get("review", 0))),
        weak_count=escape(str(summary.get("weak", 0))),
        priority_items=priority_html,
        priority_commands=_render_command_list(priority_commands[:3], "当前还没有可推荐的 ingest 命令。"),
        sections=sections_html,
    )
    write_text(inbox_path, html)
    return inbox_path


def refresh_output_home_if_present(root: Path) -> Path | None:
    output_dir = root / "output"
    viewer_exists = (output_dir / "viewer" / "index.html").exists()
    graph_exists = (output_dir / "graph" / "index.html").exists()
    inbox_exists = (output_dir / "inbox" / "index.html").exists()
    if not (viewer_exists or graph_exists or inbox_exists):
        return None
    return write_output_home(root)


def output_access_lines(root: Path) -> list[str]:
    output_dir = root / "output"
    viewer_exists = (output_dir / "viewer" / "index.html").exists()
    graph_exists = (output_dir / "graph" / "index.html").exists()
    output_home = refresh_output_home_if_present(root)

    lines: list[str] = []
    if output_home is not None:
        lines.append("Output hub: output/index.html")
        lines.append(f"Output hub URI: {file_uri(output_home)}")
        if viewer_exists and not graph_exists:
            lines.append(f"Next: run `python scripts/thinkwiki graph --root {root}` to generate the graph page.")
        elif graph_exists and not viewer_exists:
            lines.append(f"Next: run `python scripts/thinkwiki viewer --root {root}` to generate the viewer page.")
        return lines

    lines.append(f"Next: run `python scripts/thinkwiki viewer --root {root}` to generate the local viewer page.")
    lines.append(f"Next: run `python scripts/thinkwiki graph --root {root}` to generate the knowledge graph page.")
    return lines


def render_template(template: str, values: Dict[str, str]) -> str:
    for key, value in values.items():
        template = template.replace("{{" + key + "}}", value)
    return template


def load_template(name: str) -> str:
    return read_text(repo_root_from_script() / "templates" / name)


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    counter = 2
    while True:
        candidate = path.with_name(f"{stem}-{counter}{suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def classify_raw_dir(source_path: Path | None, is_text: bool = False) -> str:
    if is_text or source_path is None:
        return "articles"
    suffix = source_path.suffix.lower()
    if suffix == ".pdf":
        return "papers"
    if suffix in {".epub", ".mobi"}:
        return "books"
    if suffix in {".json", ".jsonl"}:
        return "conversations"
    return "articles"


def parse_frontmatter(text: str) -> Tuple[Dict[str, object], str]:
    if not text.startswith("---\n"):
        return {}, text
    parts = text.split("\n---\n", 1)
    if len(parts) != 2:
        return {}, text
    frontmatter, body = parts
    lines = frontmatter.splitlines()[1:]
    meta: Dict[str, object] = {}
    current_list_key = None
    for raw in lines:
        line = raw.rstrip()
        if not line:
            continue
        if line.startswith("  - ") and current_list_key:
            meta.setdefault(current_list_key, []).append(line[4:].strip())
            continue
        if ": " in line:
            key, value = line.split(": ", 1)
            meta[key.strip()] = value.strip()
            current_list_key = None
        elif line.endswith(":"):
            key = line[:-1].strip()
            meta[key] = []
            current_list_key = key
    return meta, body


def extract_summary(meta: Dict[str, object], body: str) -> str:
    if meta.get("summary"):
        return str(meta["summary"])
    lines = [line.strip() for line in body.splitlines()]
    for line in lines:
        if not line or line.startswith("#") or line.startswith("- ") or line.startswith("```"):
            continue
        return line[:120]
    return "(no summary)"


def markdown_links(text: str) -> List[str]:
    return re.findall(r"\[[^\]]+\]\(([^)]+)\)", text)


def is_external_link(target: str) -> bool:
    return target.startswith(("http://", "https://", "mailto:", "#"))


def collect_wiki_pages(root: Path) -> List[Path]:
    pages: List[Path] = []
    for subdir in WIKI_DIRS:
        pages.extend(sorted((root / "wiki" / subdir).glob("*.md")))
    return pages


def normalize_repo_path(root: Path, value: str) -> str:
    path = Path(value)
    if path.is_absolute():
        resolved = path.resolve()
        try:
            path = resolved.relative_to(root.resolve())
        except ValueError:
            return resolved.as_posix()
    return path.as_posix().lstrip("./")


def relative_link(from_page: Path, root: Path, target: str) -> str:
    target_path = root / normalize_repo_path(root, target)
    return Path(os.path.relpath(target_path, start=from_page.parent)).as_posix()


def markdown_link_list(from_page: Path, root: Path, targets: Iterable[str]) -> str:
    items = []
    for target in targets:
        normalized = normalize_repo_path(root, target)
        label = Path(normalized).stem.replace("-", " ").replace("_", " ").strip() or normalized
        items.append(f"- [{label}]({relative_link(from_page, root, normalized)})")
    return "\n".join(items)


def frontmatter_list(items: Iterable[str], fallback: str) -> str:
    values = [item for item in items if item]
    if not values:
        values = [fallback]
    return "\n".join(f"  - {item}" for item in values)


def append_log(root: Path, heading: str, lines: Iterable[str]) -> None:
    log_path = root / "log.md"
    current = read_text(log_path).rstrip()
    block = "## " + heading + "\n" + "\n".join(lines)
    if current:
        current += "\n\n" + block
    else:
        current = "# Wiki Log\n\n" + block
    write_text(log_path, current)
