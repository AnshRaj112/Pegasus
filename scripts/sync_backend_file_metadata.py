#!/usr/bin/env python3
"""Synchronize generated author metadata headers in backend Python and native Rust files.

This script reads Git history for each tracked backend Python and native Rust
file and writes a small generated header containing the contributing author
names and the file's most recent edit timestamp.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SUPPORTED_SUFFIXES = {".py", ".rs"}


def run_git(*args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(REPO_ROOT), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def tracked_backend_files() -> list[Path]:
    paths = []
    for relative_path in run_git("ls-files", "-z").split("\0"):
        if not relative_path or not relative_path.startswith("pegasus-backend/"):
            continue
        suffix = Path(relative_path).suffix
        if suffix not in SUPPORTED_SUFFIXES:
            continue
        if suffix == ".rs" and not relative_path.startswith("pegasus-backend/native/"):
            continue
        paths.append(REPO_ROOT / relative_path)
    return paths


def comment_prefix_for_path(path: Path) -> str | None:
    if path.suffix == ".py":
        return "#"
    if path.suffix == ".rs":
        return "//"
    return None


def header_pattern(comment_prefix: str) -> re.Pattern[str]:
    escaped_prefix = re.escape(comment_prefix)
    return re.compile(
        rf"\A{escaped_prefix} --- BEGIN GENERATED FILE METADATA ---\n"
        rf"{escaped_prefix} Authors: .+\n"
        rf"{escaped_prefix} Last edited: .+\n"
        rf"{escaped_prefix} --- END GENERATED FILE METADATA ---\n\n?",
        re.DOTALL,
    )


def file_authors(relative_path: str) -> list[str]:
    authors = []
    shortlog = run_git("shortlog", "-sne", "--", relative_path)
    for line in shortlog.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t", 1)
        contributor = parts[-1]
        name = contributor.rsplit(" <", 1)[0].strip()
        if name and name not in authors:
            authors.append(name)
    if not authors:
        fallback = run_git("log", "-1", "--format=%an", "--", relative_path).strip()
        if fallback:
            authors.append(fallback)
    return authors


def file_last_edited(relative_path: str) -> str:
    last_edited = run_git("log", "-1", "--format=%aI", "--", relative_path).strip()
    return last_edited or "unknown"


def split_prefix(path: Path, text: str) -> tuple[str, str]:
    if not text:
        return "", ""

    lines = text.splitlines(keepends=True)
    prefix: list[str] = []
    index = 0

    if path.suffix == ".py":
        if index < len(lines) and lines[index].startswith("#!"):
            prefix.append(lines[index])
            index += 1

        if index < len(lines):
            candidate = lines[index]
            if candidate.lstrip().startswith("#") and "coding" in candidate:
                prefix.append(candidate)
                index += 1
    elif path.suffix == ".rs":
        while index < len(lines):
            candidate = lines[index]
            if candidate.startswith("//!") or candidate.startswith("/*!") or candidate.startswith("#!["):
                prefix.append(candidate)
                index += 1
                continue
            break

    return "".join(prefix), "".join(lines[index:])


def render_header(authors: list[str], last_edited: str, comment_prefix: str) -> str:
    return (
        f"{comment_prefix} --- BEGIN GENERATED FILE METADATA ---\n"
        f"{comment_prefix} Authors: {', '.join(authors)}\n"
        f"{comment_prefix} Last edited: {last_edited}\n"
        f"{comment_prefix} --- END GENERATED FILE METADATA ---\n"
    )


def update_file(path: Path, check: bool) -> bool:
    relative_path = path.relative_to(REPO_ROOT).as_posix()
    comment_prefix = comment_prefix_for_path(path)
    if comment_prefix is None:
        return False
    original = path.read_text(encoding="utf-8")
    prefix, body = split_prefix(path, original)
    body_without_header = header_pattern(comment_prefix).sub("", body.lstrip("\n"), count=1)
    header = render_header(file_authors(relative_path), file_last_edited(relative_path), comment_prefix)
    prefix_separator = "\n" if prefix and path.suffix == ".rs" else ""
    separator = "\n" if body_without_header.strip() else ""
    updated = prefix + prefix_separator + header + separator + body_without_header.lstrip("\n")

    if updated == original:
        return False

    if check:
        print(relative_path)
        return True

    path.write_text(updated, encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Report files that need metadata refresh and exit non-zero.")
    parser.add_argument(
        "paths",
        nargs="*",
        help="Optional backend-relative file paths to process instead of the full tracked backend set.",
    )
    args = parser.parse_args()

    if args.paths:
        candidate_paths = [REPO_ROOT / Path(path) for path in args.paths]
    else:
        candidate_paths = tracked_backend_files()

    changed = False
    for path in candidate_paths:
        if not path.exists() or not path.is_file():
            continue
        changed |= update_file(path, check=args.check)

    if args.check and changed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())