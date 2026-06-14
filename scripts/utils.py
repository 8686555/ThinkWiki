from __future__ import annotations

import os
import re
import shutil
from datetime import date, datetime
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
        "normalized/articles",
        "normalized/papers",
        "normalized/books",
        "normalized/conversations",
        "normalized/web",
        "normalized/assets",
        "wiki/concepts",
        "wiki/topics",
        "wiki/sources",
        "wiki/syntheses",
        "wiki/queries",
        "wiki/decisions",
        "output/graph",
        "output/viewer",
        "output/exports",
    ]:
        (root / relative).mkdir(parents=True, exist_ok=True)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


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
