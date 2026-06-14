#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import venv
from pathlib import Path

RUNTIME_MODULES = ("markitdown", "bs4", "markdownify")
PYPI_SIMPLE_URL = "https://pypi.org/simple"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap the llm-wiki runtime environment.")
    parser.add_argument("--repo-root", default="", help="Optional repository root. Defaults to the skill root.")
    parser.add_argument("--check", action="store_true", help="Only check whether the runtime is ready.")
    parser.add_argument("--quiet", action="store_true", help="Reduce bootstrap output.")
    return parser.parse_args()


def infer_repo_root(repo_root_arg: str) -> Path:
    if repo_root_arg:
        return Path(repo_root_arg).expanduser().resolve()
    return Path(__file__).resolve().parent.parent


def venv_python_candidates(repo_root: Path) -> list[Path]:
    windows_candidates = [
        repo_root / ".venv" / "Scripts" / "python.exe",
        repo_root / ".venv" / "Scripts" / "python",
    ]
    unix_candidates = [
        repo_root / ".venv" / "bin" / "python3",
        repo_root / ".venv" / "bin" / "python",
    ]
    return windows_candidates + unix_candidates if os.name == "nt" else unix_candidates + windows_candidates


def venv_python(repo_root: Path) -> Path:
    for candidate in venv_python_candidates(repo_root):
        if candidate.exists():
            return candidate
    return venv_python_candidates(repo_root)[0]


def requirements_path(repo_root: Path) -> Path:
    return repo_root / "requirements.txt"


def runtime_ready_with_python(python_bin: Path) -> bool:
    if not python_bin.exists():
        return False
    script = (
        "import importlib, sys\n"
        f"mods={list(RUNTIME_MODULES)!r}\n"
        "missing=[]\n"
        "for mod in mods:\n"
        "    try:\n"
        "        importlib.import_module(mod)\n"
        "    except Exception:\n"
        "        missing.append(mod)\n"
        "print('\\n'.join(missing))\n"
        "sys.exit(0 if not missing else 1)\n"
    )
    result = subprocess.run([str(python_bin), "-c", script], capture_output=True, text=True)
    return result.returncode == 0


def create_venv(repo_root: Path, quiet: bool) -> Path:
    venv_dir = repo_root / ".venv"
    if not venv_dir.exists():
        if not quiet:
            print(f"[llm-wiki] Creating runtime venv at {venv_dir}")
        builder = venv.EnvBuilder(with_pip=True, clear=False, upgrade=False)
        builder.create(venv_dir)
    python_bin = venv_python(repo_root)
    if not python_bin.exists():
        raise SystemExit(f"Failed to create runtime python: {python_bin}")
    return python_bin


def install_requirements(repo_root: Path, python_bin: Path, quiet: bool) -> None:
    req_path = requirements_path(repo_root)
    if not req_path.exists():
        raise SystemExit(f"requirements.txt not found: {req_path}")
    if not quiet:
        print(f"[llm-wiki] Installing runtime dependencies from {req_path}")
    base_cmd = [str(python_bin), "-m", "pip", "install", "-r", str(req_path)]
    if quiet:
        base_cmd.extend(["--disable-pip-version-check", "--quiet"])
    commands = [
        base_cmd,
        [*base_cmd, "--index-url", PYPI_SIMPLE_URL],
    ]
    last_error = "pip install failed"
    for index, install_cmd in enumerate(commands):
        if not quiet and index == 1:
            print(f"[llm-wiki] Default package index failed, retrying via {PYPI_SIMPLE_URL}")
        result = subprocess.run(install_cmd, capture_output=quiet, text=True)
        if result.returncode == 0:
            return
        last_error = (result.stderr or result.stdout or "pip install failed").strip()
    raise SystemExit(f"Failed to install llm-wiki runtime dependencies: {last_error}")


def ensure_runtime(repo_root: Path, quiet: bool) -> Path:
    python_bin = create_venv(repo_root, quiet)
    if runtime_ready_with_python(python_bin):
        if not quiet:
            print(f"[llm-wiki] Runtime ready: {python_bin}")
        return python_bin
    install_requirements(repo_root, python_bin, quiet)
    if not runtime_ready_with_python(python_bin):
        raise SystemExit("llm-wiki runtime bootstrap completed, but required modules are still unavailable.")
    if not quiet:
        print(f"[llm-wiki] Runtime ready: {python_bin}")
    return python_bin


def check_runtime(repo_root: Path) -> int:
    python_bin = venv_python(repo_root)
    if runtime_ready_with_python(python_bin):
        print(f"READY {python_bin}")
        return 0
    print(f"MISSING {python_bin}")
    return 1


def main() -> int:
    args = parse_args()
    repo_root = infer_repo_root(args.repo_root)
    if args.check:
        return check_runtime(repo_root)
    ensure_runtime(repo_root, args.quiet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
