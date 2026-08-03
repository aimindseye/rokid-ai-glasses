#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

PROFILE_PATH = Path(__file__).resolve().parent / "profiles" / "r25-publication-verifiers.json"
_MISSING = object()


def load_profiles() -> list[dict]:
    data = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    if data.get("schema") != "rokid.r27.2.1.r25-publication-verifiers.v1":
        raise RuntimeError("unexpected r25 publication verifier profile schema")
    return list(data.get("profiles", []))


def profile_for(revision: str) -> dict:
    for profile in load_profiles():
        if profile.get("revision") == revision:
            return profile
    raise KeyError(revision)


def list_profiles() -> int:
    for profile in load_profiles():
        print(f"{profile['revision']}\t{profile['legacy_path']}")
    return 0


def get_path(value: Any, dotted: str):
    current = value
    for part in dotted.split(".") if dotted else []:
        if not isinstance(current, dict) or part not in current:
            return _MISSING
        current = current[part]
    return current


def walk(value: Any):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key, child
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def contains_base64_like(value: Any) -> bool:
    if isinstance(value, dict):
        return any(contains_base64_like(v) for v in value.values())
    if isinstance(value, list):
        return any(contains_base64_like(v) for v in value)
    return isinstance(value, str) and len(value) >= 40 and any(ch in value for ch in "+/=")


def _fail(message: str) -> tuple[int, list[str]]:
    return 1, [message]


def verify(repo: Path, revision: str, publication: Path, *, emit_output: bool = True) -> tuple[int, list[str]]:
    del repo  # stable signature for canonical harness use
    try:
        profile = profile_for(revision)
    except KeyError:
        lines = [f"ERROR: unknown r25 publication verifier revision: {revision}"]
        if emit_output:
            print(lines[0])
        return 2, lines

    publication = publication.expanduser().resolve()
    if not publication.is_file():
        lines = [f"ERROR: publication not found: {publication}"]
        if emit_output:
            print(lines[0])
        return 1, lines
    try:
        raw = publication.read_text(encoding="utf-8")
        value = json.loads(raw)
    except Exception as exc:
        lines = [f"ERROR: invalid publication JSON: {exc}"]
        if emit_output:
            print(lines[0])
        return 1, lines

    failures: list[str] = []
    for pattern in profile.get("text_forbidden_regex", []):
        if re.search(pattern, raw):
            failures.append(f"forbidden text pattern: {pattern}")

    uuid_policy = profile.get("uuid_policy")
    if uuid_policy:
        found = {match.lower() for match in re.findall(uuid_policy["regex"], raw)}
        allowed = {item.lower() for item in uuid_policy.get("allowed", [])}
        unexpected = sorted(found - allowed)
        if unexpected:
            failures.append("unexpected raw UUIDs: " + ",".join(unexpected))

    if profile.get("reject_base64_like") and contains_base64_like(value):
        failures.append("base64-like material")

    forbidden_keys = set(profile.get("forbidden_keys", []))
    string_patterns = [re.compile(pattern) for pattern in profile.get("string_forbidden_regex", [])]
    if forbidden_keys or string_patterns:
        for key, child in walk(value):
            if key in forbidden_keys:
                failures.append(f"forbidden key: {key}")
            if isinstance(child, str):
                for pattern in string_patterns:
                    if pattern.search(child):
                        failures.append(f"forbidden string pattern at key: {key}")
                        break

    for path, expected in profile.get("equals", []):
        actual = get_path(value, path)
        if actual is _MISSING or actual != expected:
            failures.append(f"value mismatch: {path}")

    if failures:
        if emit_output:
            print("R27_2_1_R25_PUBLICATION_VERIFY=FAIL")
            for failure in failures:
                print(f"- {failure}")
        return 1, failures

    lines = list(profile.get("success_lines", []))
    if emit_output:
        for line in lines:
            print(line)
    return 0, lines


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Canonical profile-driven r25 publication verifier")
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--revision")
    parser.add_argument("--publication", type=Path)
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args(argv)
    if args.list:
        return list_profiles()
    if not args.revision or args.publication is None:
        parser.error("--revision and --publication are required")
    rc, _lines = verify(args.repo.expanduser().resolve(), args.revision, args.publication, emit_output=True)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
