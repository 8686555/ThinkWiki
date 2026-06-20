#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from urllib.parse import urlparse

from ingest import (
    clean_markdown,
    extract_title_from_markdown,
    fetch_webpage_as_markdown,
    humanize_name,
    normalize_local_source,
)
from utils import (
    append_log,
    ensure_runtime_dirs,
    file_uri,
    find_repo_root,
    write_inbox_review,
    write_output_home,
    slugify,
    today_str,
    unique_path,
    write_text,
)


def next_ingest_command(root: Path, normalized_path: Path) -> str:
    repo_path = normalized_path.relative_to(root).as_posix()
    return f"python scripts/thinkwiki ingest --root {root} --source {repo_path}"


def clip_local_source(root: Path, source_path: Path, title_override: str) -> tuple[str, Path, Path]:
    normalized_text = normalize_local_source(source_path)
    fallback_title = humanize_name(source_path.stem)
    title = title_override.strip() or extract_title_from_markdown(normalized_text, fallback_title)
    slug = slugify(title, "clip")
    raw_path = unique_path(root / "raw" / "inbox" / f"{today_str()}-{slug}{source_path.suffix.lower()}")
    normalized_path = unique_path(root / "normalized" / "inbox" / f"{today_str()}-{slug}.md")
    shutil.copy2(source_path, raw_path)
    write_text(normalized_path, normalized_text)
    return title, raw_path, normalized_path


def clip_web_source(root: Path, url: str, title_override: str) -> tuple[str, Path, Path]:
    normalized_text, raw_html = fetch_webpage_as_markdown(url, title_override)
    parsed = urlparse(url)
    fallback_title = humanize_name(Path(parsed.path).stem or parsed.netloc or "web-clip")
    title = title_override.strip() or extract_title_from_markdown(normalized_text, fallback_title)
    slug = slugify(title, "clip")
    raw_path = unique_path(root / "raw" / "inbox" / f"{today_str()}-{slug}.html")
    normalized_path = unique_path(root / "normalized" / "inbox" / f"{today_str()}-{slug}.md")
    write_text(raw_path, raw_html or f"URL: {url}")
    write_text(normalized_path, normalized_text)
    return title, raw_path, normalized_path


def clip_text_source(root: Path, text: str, title_override: str) -> tuple[str, Path, Path]:
    cleaned_text = clean_markdown(text)
    title = title_override.strip() or extract_title_from_markdown(cleaned_text, "Inbox Clip")
    slug = slugify(title, "clip")
    raw_path = unique_path(root / "raw" / "inbox" / f"{today_str()}-{slug}.md")
    normalized_path = unique_path(root / "normalized" / "inbox" / f"{today_str()}-{slug}.md")
    write_text(raw_path, cleaned_text)
    write_text(normalized_path, cleaned_text)
    return title, raw_path, normalized_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Clip a webpage, file, or pasted text into the ThinkWiki inbox.")
    parser.add_argument("--root", default=".", help="Wiki root path")
    parser.add_argument("--source", help="Path to a local source file to clip into inbox")
    parser.add_argument("--url", help="Webpage URL to clip into inbox")
    parser.add_argument("--text", help="Inline text to clip into inbox")
    parser.add_argument("--title", default="", help="Human readable title")
    args = parser.parse_args()

    provided = [bool(args.source), bool(args.url), bool(args.text)]
    if sum(provided) != 1:
        raise SystemExit("Provide exactly one of --source, --url, or --text")

    root = find_repo_root(Path(args.root))
    ensure_runtime_dirs(root)
    if args.source:
        source_path = Path(args.source).resolve()
        if not source_path.exists() or not source_path.is_file():
            raise SystemExit(f"Source file not found: {source_path}")
        title, raw_path, normalized_path = clip_local_source(root, source_path, args.title)
    elif args.url:
        title, raw_path, normalized_path = clip_web_source(root, args.url, args.title)
    else:
        title, raw_path, normalized_path = clip_text_source(root, args.text or "", args.title)

    append_log(root, f"[{today_str()}] clip | {title}", [
        f"- raw: {raw_path.relative_to(root).as_posix()}",
        f"- normalized: {normalized_path.relative_to(root).as_posix()}",
        "- next: review the inbox item, then ingest it into wiki/sources when ready",
    ])
    print(f"Clipped {title} into inbox")
    print(f"Inbox raw: {raw_path.relative_to(root).as_posix()}")
    print(f"Inbox normalized: {normalized_path.relative_to(root).as_posix()}")
    inbox_page = write_inbox_review(root)
    output_home = write_output_home(root)
    print("Inbox review: output/inbox/index.html")
    print(f"Inbox review URI: {file_uri(inbox_page)}")
    print("Output hub: output/index.html")
    print(f"Output hub URI: {file_uri(output_home)}")
    print(f"Next: run `{next_ingest_command(root, normalized_path)}`")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
