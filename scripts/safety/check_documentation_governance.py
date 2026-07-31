#!/usr/bin/env python3
"""Validate the audience-first documentation information architecture."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote

STATUS_RE = re.compile(
    r"<!--\s*wiki-status:\s*audience=([^;]+);\s*"
    r"applies_to=([^;]+);\s*evidence=([^;]+);\s*"
    r"last_reviewed=(\d{4}-\d{2}-\d{2})\s*-->"
)
TITLE_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
REDIRECT_RE = re.compile(r"<!--\s*wiki-redirect:\s*([^\s]+)\s*-->")
FORBIDDEN_CONSUMER_PREFIXES = (
    "docs/research/", "docs/tests/", "docs/runbooks/", "docs/findings/",
    "docs/methodology/", "docs/experiments/", "scripts/", "evidence/",
    "android-client/", "tools/",
)


def resolve_link(repo: Path, source: Path, raw: str) -> str | None:
    target = raw.split(maxsplit=1)[0].strip("<>")
    if not target or target.startswith(("http://", "https://", "mailto:", "#")):
        return None
    path_part = unquote(target.partition("#")[0])
    destination = (source.parent / path_part).resolve()
    try:
        return destination.relative_to(repo).as_posix()
    except ValueError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    manifest_path = repo / "docs/wiki-navigation.json"
    errors: list[str] = []

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"Documentation governance: FAIL\n- invalid manifest: {exc}", file=sys.stderr)
        return 1

    if manifest.get("schema") != "rokid-ai-glasses.wiki-navigation.v1":
        errors.append("unexpected navigation manifest schema")

    canonical: dict[str, str] = {}
    landings: dict[str, str] = {}
    for entry in manifest.get("landing_pages", []):
        canonical[entry["path"]] = entry["audience"]
    for section in manifest.get("sections", []):
        section_id = section["id"]
        landing = section["landing"]
        landings[section_id] = landing
        for item in section.get("pages", []):
            if item in canonical and canonical[item] != section_id:
                errors.append(f"canonical page listed in multiple audiences: {item}")
            canonical[item] = section_id

    titles: dict[str, str] = {}
    for relative, expected_audience in sorted(canonical.items()):
        path = repo / relative
        if not path.is_file():
            errors.append(f"missing canonical page: {relative}")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        status = STATUS_RE.search(text)
        if not status:
            errors.append(f"missing wiki-status metadata: {relative}")
        else:
            audience, applies_to, _evidence, _date = [value.strip() for value in status.groups()]
            if audience != expected_audience:
                errors.append(
                    f"audience mismatch: {relative}: expected {expected_audience}, found {audience}"
                )
            if applies_to != manifest.get("device_scope"):
                errors.append(f"device scope mismatch: {relative}")
        title_match = TITLE_RE.search(text)
        if not title_match:
            errors.append(f"missing H1 title: {relative}")
        else:
            title = title_match.group(1).strip().casefold()
            if title in titles:
                errors.append(f"duplicate canonical title: {relative} and {titles[title]}")
            else:
                titles[title] = relative
        if relative != "README.md" and "## Page status" not in text:
            errors.append(f"missing visible page-status table: {relative}")

    redirect_sources = {item["from"] for item in manifest.get("legacy_redirects", [])}
    for root_value in manifest.get("canonical_roots", []):
        root = repo / root_value
        if not root.exists():
            errors.append(f"missing canonical root: {root_value}")
            continue
        for path in sorted(root.rglob("*.md")):
            relative = path.relative_to(repo).as_posix()
            if relative not in canonical and relative not in redirect_sources:
                errors.append(f"orphan canonical page not in manifest: {relative}")

    for section in manifest.get("sections", []):
        landing_path = repo / section["landing"]
        if not landing_path.is_file():
            continue
        landing_text = landing_path.read_text(encoding="utf-8", errors="replace")
        linked = {
            resolve_link(repo, landing_path, match.group(1).strip())
            for match in LINK_RE.finditer(landing_text)
        }
        for page in section.get("pages", []):
            if page == section["landing"]:
                continue
            if page not in linked:
                errors.append(
                    f"section landing does not link canonical page: {section['landing']} -> {page}"
                )

    consumer_heading = "## " + manifest.get("consumer_technical_boundary_heading", "Technical evidence")
    for relative, audience in canonical.items():
        if audience != "consumer" or relative.endswith("/README.md"):
            continue
        path = repo / relative
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        public_part = text.split(consumer_heading, 1)[0]
        for match in LINK_RE.finditer(public_part):
            target = resolve_link(repo, path, match.group(1).strip())
            if target and target.startswith(FORBIDDEN_CONSUMER_PREFIXES):
                errors.append(
                    f"consumer technical link appears before '{consumer_heading}': {relative} -> {target}"
                )

    for redirect in manifest.get("legacy_redirects", []):
        source = repo / redirect["from"]
        target = repo / redirect["to"]
        if not source.is_file():
            errors.append(f"missing legacy redirect: {redirect['from']}")
            continue
        if not target.is_file():
            errors.append(f"legacy redirect target missing: {redirect['to']}")
        text = source.read_text(encoding="utf-8", errors="replace")
        marker = REDIRECT_RE.search(text)
        if not marker or marker.group(1) != redirect["to"]:
            errors.append(f"invalid legacy redirect marker: {redirect['from']}")
        resolved_targets = {
            resolve_link(repo, source, match.group(1).strip())
            for match in LINK_RE.finditer(text)
        }
        if redirect["to"] not in resolved_targets:
            errors.append(
                f"legacy redirect does not link target: {redirect['from']} -> {redirect['to']}"
            )

    if errors:
        print("Documentation governance: FAIL", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        "Documentation governance: PASS "
        f"({len(canonical)} canonical pages, {len(titles)} unique titles, "
        f"{len(manifest.get('legacy_redirects', []))} legacy redirects)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
