#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import zipfile
from pathlib import Path

try:
    from tool_test_runner import load_registry, verify_oracle_locks
    from retirement_status import summary as retirement_summary
except ImportError:
    from scripts.research.canonical.tool_test_runner import load_registry, verify_oracle_locks
    from scripts.research.canonical.retirement_status import summary as retirement_summary


def _deterministic_zip(path: Path, repo: Path, profiles: list[dict]) -> None:
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in sorted(profiles, key=lambda x: (x['track'], x['revision'], x['legacy_test'])):
            src = repo / p['legacy_test']
            info = zipfile.ZipInfo(p['legacy_test'], date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            z.writestr(info, src.read_bytes())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', required=True)
    ap.add_argument('--output', required=True)
    args = ap.parse_args()
    repo = Path(args.repo).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)

    reg = load_registry()
    profiles = reg['profiles']
    errors: list[str] = []
    if reg.get('schema') != 'rokid.r27.1.12.tool-test-suites.v2':
        errors.append(f"schema={reg.get('schema')}")
    if len(profiles) != 39:
        errors.append(f'profile_count={len(profiles)}')

    rc, detail = verify_oracle_locks(repo, emit_output=False)
    if rc != 0:
        errors.append('oracle_source_lock_or_classification_failure')

    current = [p for p in profiles if p.get('oracle_state') == 'PRESERVE_REGRESSION_ORACLE']
    historical = [p for p in profiles if p.get('oracle_state') == 'PRESERVE_HISTORICAL']
    if len(current) != 38:
        errors.append(f'preserve_regression_oracle_count={len(current)}')
    if len(historical) != 1:
        errors.append(f'tool_test_preserve_historical_count={len(historical)}')
    if any(p.get('status') != 'CURRENT_EQUIVALENT' for p in current):
        errors.append('current_oracle_status_mismatch')
    if len(historical) == 1:
        p = historical[0]
        missing = [x for x in p.get('required_fixture_paths', []) if not (repo / x).exists()]
        if p.get('status') != 'DEFERRED_MISSING_FIXTURE' or not missing:
            errors.append('deferred_fixture_contract_not_preserved')

    rs = retirement_summary(repo)
    expected = {
        'retired_compatibility_shim_count': 71,
        'not_retirement_ready_count': 0,
        'preserve_regression_oracle_count': 38,
        'preserve_historical_count': 4,
        'retirement_candidate_count': 0,
        'blocked_inbound_dependency_count': 0,
        'blocked_output_container_compatibility_count': 0,
        'blocked_source_lock_count': 0,
    }
    for k, v in expected.items():
        if rs.get(k) != v:
            errors.append(f'{k}={rs.get(k)} expected={v}')

    rows = []
    for p in profiles:
        src = repo / p['legacy_test']
        actual = hashlib.sha256(src.read_bytes()).hexdigest() if src.is_file() else 'MISSING'
        rows.append({
            'track': p['track'],
            'revision': p['revision'],
            'legacy_test': p['legacy_test'],
            'status': p['status'],
            'oracle_state': p.get('oracle_state', ''),
            'execution_class': p['execution_class'],
            'test_count': p['test_count'],
            'expected_sha256': p['legacy_sha256'],
            'actual_sha256': actual,
            'source_lock': 'PASS' if actual == p['legacy_sha256'] else 'FAIL',
            'deferred_reason': p.get('deferred_reason', ''),
        })

    tsv = output / 'tool-test-oracle-freeze.tsv'
    fields = ['track','revision','legacy_test','status','oracle_state','execution_class','test_count','expected_sha256','actual_sha256','source_lock','deferred_reason']
    with tsv.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter='\t', lineterminator='\n')
        w.writeheader(); w.writerows(rows)

    archive = output / 'tool-test-oracles.zip'
    if not errors:
        _deterministic_zip(archive, repo, profiles)
        archive_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
        sidecar = Path(str(archive) + '.sha256')
        sidecar.write_text(f'{archive_sha}  {archive.name}\n', encoding='utf-8')
        with zipfile.ZipFile(archive) as z:
            names = z.namelist()
            if len(names) != 39 or len(set(names)) != 39:
                errors.append('oracle_archive_member_count')
            for p in profiles:
                if p['legacy_test'] not in names:
                    errors.append('oracle_archive_missing:' + p['legacy_test'])
                    continue
                if hashlib.sha256(z.read(p['legacy_test'])).hexdigest() != p['legacy_sha256']:
                    errors.append('oracle_archive_hash:' + p['legacy_test'])
    else:
        archive_sha = ''

    summary = {
        'schema': 'rokid.r27.1.12.tool-test-oracle-finalization.v1',
        'profile_count': len(profiles),
        'preserve_regression_oracle_count': len(current),
        'tool_test_preserve_historical_count': len(historical),
        'source_lock_failure_count': sum(r['source_lock'] != 'PASS' for r in rows),
        'retired_compatibility_shim_count': rs.get('retired_compatibility_shim_count'),
        'not_retirement_ready_count': rs.get('not_retirement_ready_count'),
        'global_preserve_historical_count': rs.get('preserve_historical_count'),
        'blocked_source_lock_count': rs.get('blocked_source_lock_count'),
        'oracle_archive_sha256': archive_sha,
        'legacy_tool_test_action': 'PRESERVE_AS_INDEPENDENT_REGRESSION_ORACLES',
        'legacy_path_deletion_count': 0,
        'device_operation': 'NONE',
        'failures': errors,
        'status': 'PASS' if not errors else 'FAIL',
    }
    (output / 'summary.json').write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n', encoding='utf-8')

    if errors:
        print('R27_1_12_VERIFY=FAIL')
        for e in errors:
            print('ERROR=' + e)
        return 1
    print('R27_1_12_VERIFY=PASS')
    print('TOOL_TEST_PROFILE_COUNT=39')
    print('PRESERVE_REGRESSION_ORACLE_COUNT=38')
    print('TOOL_TEST_PRESERVE_HISTORICAL_COUNT=1')
    print('TOOL_TEST_SOURCE_LOCK_FAILURE_COUNT=0')
    print('RETIRED_COMPATIBILITY_SHIM_COUNT=71')
    print('NOT_RETIREMENT_READY_COUNT=0')
    print('GLOBAL_PRESERVE_HISTORICAL_COUNT=4')
    print('BLOCKED_SOURCE_LOCK_COUNT=0')
    print(f'TOOL_TEST_ORACLE_ARCHIVE={archive}')
    print(f'TOOL_TEST_ORACLE_ARCHIVE_SHA256={archive_sha}')
    print('LEGACY_TOOL_TEST_ACTION=PRESERVE_AS_INDEPENDENT_REGRESSION_ORACLES')
    print('LEGACY_PATH_DELETION_COUNT=0')
    print('DEVICE_OPERATION=NONE')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
