#!/usr/bin/env python3
from __future__ import annotations
import sys
from pathlib import Path

try:
    from .primitives import read_json, sha256_file, source_lock
except ImportError:
    try:
        from scripts.research.canonical.primitives import read_json, sha256_file, source_lock
    except ImportError:
        from primitives import read_json, sha256_file, source_lock

PROFILE_PATH = Path(__file__).with_name('profiles') / 'source-contracts.json'


def load_registry():
    return read_json(PROFILE_PATH)


def find_profile(track: str, revision: str):
    for p in load_registry()['profiles']:
        if p['track'] == track and p['revision'] == revision:
            return p
    return None


def list_profiles() -> int:
    reg = load_registry()
    print('track\trevision\tlegacy_checker\tstatus')
    for p in reg['profiles']:
        state = 'CANONICAL_SNAPSHOT_QUALIFIED' if p.get('retirement_state') == 'COMPATIBILITY_SHIM' else 'CANONICAL_DISPATCH_QUALIFIED'
        print(f"{p['track']}\t{p['revision']}\t{p['legacy_checker']}\t{state}")
    for p in reg.get('deferred_historical_contracts', []):
        print(f"{p['track']}\t{p['revision']}\t{p['legacy_checker']}\tDEFERRED_HISTORICAL")
    return 0


def _validate_profile(repo: Path, profile: dict, stack: tuple[tuple[str, str], ...] = (), memo: dict[tuple[str,str], tuple[str,...]] | None = None, index: dict[tuple[str,str], dict] | None = None) -> list[str]:
    key = (profile['track'], profile['revision'])
    if memo is not None and key in memo:
        return list(memo[key])
    if key in stack:
        return [f"source-contract dependency cycle: {' -> '.join(f'{a}:{b}' for a,b in stack + (key,))}"]
    errors: list[str] = []

    # The active historical path is now a compatibility entry point.  Its identity
    # is locked separately from the archived historical oracle identity.
    checker = repo / profile['legacy_checker']
    shim_sha = profile.get('compatibility_shim_sha256')
    if shim_sha:
        locked, actual = source_lock(checker, shim_sha)
        if not locked:
            errors.append(
                f"compatibility shim identity mismatch: {profile['legacy_checker']} expected={shim_sha} actual={actual}"
            )
    elif not checker.is_file():
        errors.append(f"source-contract compatibility path missing: {profile['legacy_checker']}")

    for rel in profile.get('required_directories', []):
        if not (repo / rel).is_dir():
            errors.append(f"required source-contract directory missing: {rel}")

    for rel, expected in profile.get('required_file_sha256', {}).items():
        p = repo / rel
        if not p.is_file():
            errors.append(f"required source-contract file missing: {rel}")
            continue
        actual = sha256_file(p)
        if actual != expected:
            errors.append(f"accepted source snapshot identity mismatch: {rel} expected={expected} actual={actual}")

    next_stack = stack + (key,)
    if index is None:
        index = {(p['track'],p['revision']):p for p in load_registry()['profiles']}
    for dep in profile.get('contract_dependencies', []):
        dp = index.get((dep['track'], dep['revision']))
        if dp is None:
            errors.append(f"source-contract dependency profile missing: {dep['track']}:{dep['revision']}")
            continue
        errors.extend(_validate_profile(repo, dp, next_stack, memo, index))
    if memo is not None:
        memo[key] = tuple(errors)
    return errors


def execute(repo: Path, track: str, revision: str, output: Path | None = None):
    profile = find_profile(track, revision)
    if profile is None:
        return 2, '', f'ERROR: source-contract profile not found: {track}:{revision}\n', None
    if output is not None and not profile.get('supports_output'):
        return 2, '', f'ERROR: profile does not support --output: {track}:{revision}\n', profile
    reg = load_registry()
    index = {(p['track'],p['revision']):p for p in reg['profiles']}
    errors = _validate_profile(repo, profile, memo={}, index=index)
    if errors:
        return 1, '', ''.join(f'ERROR: {e}\n' for e in errors), profile
    stdout = profile.get('legacy_success_stdout', '')
    for marker in profile.get('expected_pass_markers', []):
        if marker not in stdout:
            return 1, stdout, f'ERROR: profile success stdout missing PASS marker: {marker}\n', profile
    return 0, stdout, '', profile


def compatibility_check(repo: Path, track: str, revision: str) -> int:
    rc, out, err, _ = execute(repo, track, revision)
    if out:
        print(out, end='')
    if err:
        print(err, end='', file=sys.stderr)
    return rc


def check(repo: Path, track: str, revision: str, output: Path | None = None) -> int:
    rc, out, err, profile = execute(repo, track, revision, output)
    if out:
        print(out, end='')
    if err:
        print(err, end='', file=sys.stderr)
    if rc == 0:
        print('R27_1_11_CANONICAL_SOURCE_CONTRACT=PASS')
        print(f'TRACK={track}')
        print(f'REVISION={revision}')
        print('CONTRACT_IMPLEMENTATION=INDEPENDENT_ACCEPTED_SOURCE_SNAPSHOT_ENGINE')
        print('LEGACY_CHECKER_IMPLEMENTATION=COMPATIBILITY_SHIM')
        print('DEVICE_OPERATION=NONE')
    return rc
