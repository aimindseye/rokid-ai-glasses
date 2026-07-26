#!/usr/bin/env python3
"""Fail-closed checker for local Markdown file links and heading fragments."""
from __future__ import annotations

import argparse
import re
import sys
import urllib.parse
from collections import defaultdict
from pathlib import Path

LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
HTML_ANCHOR_RE = re.compile(r"<a\s+(?:name|id)=[\"']([^\"']+)[\"']", re.I)
CODE_FENCE_RE = re.compile(r"^\s*(```|~~~)")


def github_slug(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[`*_~]", "", text)
    text = text.strip().lower()
    text = re.sub(r"[^\w\- ]", "", text, flags=re.UNICODE)
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def anchors_for(path: Path) -> set[str]:
    anchors: set[str] = set()
    counts: defaultdict[str, int] = defaultdict(int)
    in_fence = False
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if CODE_FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for match in HTML_ANCHOR_RE.finditer(line):
            anchors.add(match.group(1))
        match = HEADING_RE.match(line)
        if not match:
            continue
        base = github_slug(match.group(2))
        if not base:
            continue
        count = counts[base]
        counts[base] += 1
        anchors.add(base if count == 0 else f"{base}-{count}")
    return anchors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()

    markdown = sorted(
        p for p in repo.rglob("*.md")
        if ".git" not in p.parts
        and not any(part.startswith(".documentation-") for part in p.parts)
    )
    anchor_cache: dict[Path, set[str]] = {}
    errors: list[str] = []
    checked = 0

    for source in markdown:
        text = source.read_text(encoding="utf-8", errors="replace")
        for line_no, line in enumerate(text.splitlines(), start=1):
            for match in LINK_RE.finditer(line):
                raw = match.group(1).strip()
                if not raw:
                    continue
                target = raw.split(maxsplit=1)[0].strip("<>")
                if target.startswith(("http://", "https://", "mailto:")):
                    continue
                checked += 1
                if target.startswith("#"):
                    destination = source
                    fragment = target[1:]
                else:
                    path_part, sep, fragment = target.partition("#")
                    destination = (source.parent / urllib.parse.unquote(path_part)).resolve()
                    try:
                        destination.relative_to(repo)
                    except ValueError:
                        errors.append(f"{source.relative_to(repo)}:{line_no}: link escapes repository: {target}")
                        continue
                    if not destination.exists():
                        errors.append(f"{source.relative_to(repo)}:{line_no}: missing target: {target}")
                        continue
                    if destination.is_dir():
                        readme = destination / "README.md"
                        if not readme.exists():
                            errors.append(f"{source.relative_to(repo)}:{line_no}: directory has no README.md: {target}")
                        destination = readme
                if fragment and destination.suffix.lower() == ".md" and destination.exists():
                    anchors = anchor_cache.setdefault(destination, anchors_for(destination))
                    decoded = urllib.parse.unquote(fragment).lower()
                    if decoded not in anchors:
                        errors.append(
                            f"{source.relative_to(repo)}:{line_no}: missing heading fragment "
                            f"#{fragment} in {destination.relative_to(repo)}"
                        )

    if errors:
        print("Markdown link validation: FAIL", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"Markdown link validation: PASS ({len(markdown)} files, {checked} local links checked)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
