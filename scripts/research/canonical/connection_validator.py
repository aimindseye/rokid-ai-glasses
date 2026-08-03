#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    from .primitives import bash_syntax, first_regex_match, missing_markers, python_syntax, read_json, require_regular_file, sha256_file
except ImportError:
    try:
        from scripts.research.canonical.primitives import bash_syntax, first_regex_match, missing_markers, python_syntax, read_json, require_regular_file, sha256_file
    except ImportError:
        from primitives import bash_syntax, first_regex_match, missing_markers, python_syntax, read_json, require_regular_file, sha256_file

PROFILE_PATH = Path(__file__).with_name('profiles') / 'r25-package-validators.json'


def load_profiles() -> dict:
    return read_json(PROFILE_PATH)['profiles']


def fail(message: str, code: int = 1) -> int:
    print(f'ERROR: {message}', file=sys.stderr)
    return code


def validate(repo: Path, revision: str, quiet: bool = False) -> int:
    profiles = load_profiles()
    if revision not in profiles:
        return fail(f'unknown r25 validator revision: {revision}', 2)
    p = profiles[revision]

    for req in p.get('required', []):
        path = repo / req['path']
        ok, reason = require_regular_file(path, nonempty=bool(req.get('nonempty')), no_symlink=bool(req.get('no_symlink')))
        if not ok:
            return fail(f"{reason} installed file: {req['path']}")

    for rel in p.get('python_compile', []):
        path = repo / rel
        ok, reason = python_syntax(path)
        if not ok:
            return fail(f'python syntax failed for {rel}: {reason}')

    for rel in p.get('bash_syntax', []):
        path = repo / rel
        ok, stderr = bash_syntax(path)
        if not ok:
            if stderr:
                print(stderr, file=sys.stderr, end='')
            return fail(f'bash syntax failed for {rel}')

    for rel, expected in p.get('sha256', {}).items():
        actual = sha256_file(repo / rel)
        if actual != expected:
            return fail(f'hash mismatch: {rel} expected={expected} actual={actual}')

    for rel, markers in p.get('contains', {}).items():
        text = (repo / rel).read_text(encoding='utf-8', errors='replace')
        missing = missing_markers(text, markers)
        if missing:
            return fail(f'missing marker in {rel}: {missing[0]}')

    for gate in p.get('forbidden_regex', []):
        for rel in gate['paths']:
            text = (repo / rel).read_text(encoding='utf-8', errors='replace')
            m = first_regex_match(text, gate['pattern'], ignore_case=bool(gate.get('ignore_case')))
            if m:
                return fail(f"forbidden pattern in {rel}: {gate.get('label', gate['pattern'])}")

    if not quiet:
        for line in p.get('pass_lines', []):
            print(line)
        print(f'R27_1_1_CANONICAL_R25_VALIDATOR=PASS')
        print(f'REVISION={revision}')
        print('DEVICE_OPERATION=NONE')
    return 0


def list_profiles() -> int:
    for revision, p in sorted(load_profiles().items()):
        print(f"{revision}\t{p['legacy_validator']}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='Canonical data-driven r25 installed-package validator')
    ap.add_argument('--repo', required=True)
    ap.add_argument('--revision')
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--quiet', action='store_true')
    args = ap.parse_args(argv)
    if args.list:
        return list_profiles()
    if not args.revision:
        ap.error('--revision is required unless --list is used')
    repo = Path(args.repo).expanduser().resolve()
    if not (repo / 'scripts/research/connection-protocol').is_dir():
        return fail(f'repository root not recognized: {repo}', 2)
    return validate(repo, args.revision, args.quiet)


if __name__ == '__main__':
    raise SystemExit(main())
