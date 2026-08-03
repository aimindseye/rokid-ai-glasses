#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

try:
    import retirement_status
    from primitives import read_json, source_lock
except ImportError:
    from scripts.research.canonical import retirement_status
    from scripts.research.canonical.primitives import read_json, source_lock

BASE = Path(__file__).resolve().parent
PROFILES = BASE / 'profiles'


def verify(repo: Path) -> int:
    failures=[]

    required=[
        BASE/'primitives.py', BASE/'privacy.py', BASE/'retirement_status.py',
        BASE/'connection_validator.py', BASE/'evidence_packager.py', BASE/'source_contract.py',
        BASE/'tool_test_runner.py', BASE/'r27_catalog.py',
        repo/'scripts/tests/test_r27_1_5_shared_primitives.py',
        repo/'docs/research/r27.1.5-shared-primitives-retirement-readiness.md',
    ]
    for p in required:
        if not p.is_file(): failures.append(f'missing:{p.relative_to(repo)}')

    # Source-lock every historical file represented by the four consolidated families.
    r25=read_json(PROFILES/'r25-package-validators.json')['profiles']
    for rev,p in r25.items():
        expected=p.get('compatibility_shim_sha256') if p.get('retirement_state')=='COMPATIBILITY_SHIM' else p['legacy_source_sha256']
        ok,_=source_lock(repo/p['legacy_validator'],expected)
        if not ok: failures.append(f'r25-source-lock:{rev}')

    pack=read_json(PROFILES/'test21-sanitized-packagers.json')['profiles']
    for rev,p in pack.items():
        expected=p.get('legacy_source_sha256') or p.get('legacy_sha256')
        ok,_=source_lock(repo/p['legacy_packager'],expected)
        if not ok: failures.append(f'packager-source-lock:{rev}')

    contracts=read_json(PROFILES/'source-contracts.json')
    for p in contracts['profiles']:
        ok,_=source_lock(repo/p['legacy_checker'],p['legacy_source_sha256'])
        if not ok: failures.append(f"contract-source-lock:{p['revision']}")

    tests=read_json(PROFILES/'tool-test-suites.json')
    for p in tests['profiles']:
        ok,_=source_lock(repo/p['legacy_test'],p['legacy_sha256'])
        if not ok: failures.append(f"tool-test-source-lock:{p['track']}:{p['revision']}")

    # Shared primitive extraction should be real, not just documented.
    for name in ('connection_validator.py','evidence_packager.py','source_contract.py','tool_test_runner.py','r27_catalog.py'):
        text=(BASE/name).read_text(encoding='utf-8')
        if 'primitives import' not in text:
            failures.append(f'no-primitives-import:{name}')
    for name in ('connection_validator.py','evidence_packager.py','source_contract.py'):
        if 'def sha256_file(' in (BASE/name).read_text(encoding='utf-8'):
            failures.append(f'duplicate-sha256-helper:{name}')

    s=retirement_status.summary(repo)
    if s.get('blocked_source_lock_count') != 0:
        failures.append(f"blocked_source_lock_count:{s.get('blocked_source_lock_count')}!=expected:0")
    if s.get('not_retirement_ready_count') != 67:
        failures.append(f"not_retirement_ready_count:{s.get('not_retirement_ready_count')}!=expected:67")
    if s.get('preserve_historical_count') != 4:
        failures.append(f"preserve_historical_count:{s.get('preserve_historical_count')}!=expected:4")

    if failures:
        for f in failures: print(f'FAIL={f}')
        print('R27_1_5_VERIFY=FAIL')
        return 1
    print('R27_1_5_VERIFY=PASS')
    print('SHARED_PRIMITIVE_MODULE_COUNT=2')
    print(f"RETIREMENT_STATUS_SCHEMA={s.get('schema','unknown')}")
    print(f"RETIREMENT_CANDIDATE_COUNT={s.get('retirement_candidate_count',0)}")
    print(f"NOT_RETIREMENT_READY_COUNT={s.get('not_retirement_ready_count',0)}")
    print(f"PRESERVE_HISTORICAL_COUNT={s.get('preserve_historical_count',0)}")
    print('BLOCKED_SOURCE_LOCK_COUNT=0')
    print('LEGACY_FILE_ACTION=NONE')
    print('REPOSITORY_DELETION=NONE')
    print('DEVICE_OPERATION=NONE')
    return 0


if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser(); ap.add_argument('--repo',required=True); args=ap.parse_args()
    raise SystemExit(verify(Path(args.repo).expanduser().resolve()))
