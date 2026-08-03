#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

try:
    from connection_validator import load_profiles, validate
except ImportError:
    from scripts.research.canonical.connection_validator import load_profiles, validate


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', required=True)
    ap.add_argument('--output', required=True)
    args = ap.parse_args()
    repo = Path(args.repo).expanduser().resolve()
    out = Path(args.output).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)

    profiles = load_profiles()
    legacy_paths = sorted({p['legacy_validator'] for p in profiles.values()})
    before = {rel: digest(repo / rel) for rel in legacy_paths}
    rows = []
    failures = 0

    for revision, profile in sorted(profiles.items()):
        legacy = repo / profile['legacy_validator']
        proc = subprocess.run(
            ['bash', str(legacy), str(repo)],
            cwd=str(repo),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        canonical_rc = validate(repo, revision, quiet=True)
        expected_lines = profile.get('pass_lines', [])
        legacy_markers = all(line in proc.stdout for line in expected_lines)
        equivalent = proc.returncode == 0 and canonical_rc == 0 and legacy_markers
        if not equivalent:
            failures += 1
        rows.append({
            'revision': revision,
            'legacy_validator': profile['legacy_validator'],
            'legacy_rc': proc.returncode,
            'canonical_rc': canonical_rc,
            'expected_pass_markers_found': 'YES' if legacy_markers else 'NO',
            'equivalent': 'YES' if equivalent else 'NO',
        })

    after = {rel: digest(repo / rel) for rel in legacy_paths}
    changed = [rel for rel in legacy_paths if before[rel] != after[rel]]
    if changed:
        failures += len(changed)

    report = out / 'r25-validator-equivalence.tsv'
    with report.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter='\t', lineterminator='\n')
        w.writeheader(); w.writerows(rows)

    summary = {
        'schema': 'rokid.r27.1.1.r25-validator-equivalence.v1',
        'profile_count': len(profiles),
        'equivalent_count': sum(r['equivalent'] == 'YES' for r in rows),
        'failure_count': failures,
        'legacy_validator_source_changed_count': len(changed),
        'legacy_validator_action': 'NONE',
        'repository_deletion': 'NONE',
        'device_operation': 'NONE',
        'status': 'PASS' if failures == 0 else 'FAIL',
    }
    (out / 'summary.json').write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n', encoding='utf-8')

    zip_path = out.parent / (out.name + '-private-equivalence.zip')
    with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for item in ('r25-validator-equivalence.tsv', 'summary.json'):
            zf.write(out / item, arcname=item)
    zip_hash = digest(zip_path)
    sidecar = Path(str(zip_path) + '.sha256')
    sidecar.write_text(f'{zip_hash}  {zip_path.name}\n', encoding='utf-8')

    if failures:
        print('R27_1_1_EQUIVALENCE=FAIL')
        print(f'FAILURE_COUNT={failures}')
        return 1
    print('R27_1_1_EQUIVALENCE=PASS')
    print(f'R25_VALIDATOR_PROFILE_COUNT={len(profiles)}')
    print(f'R25_LEGACY_CANONICAL_EQUIVALENT_COUNT={summary["equivalent_count"]}')
    print('LEGACY_VALIDATOR_SOURCE_CHANGED_COUNT=0')
    print('LEGACY_FILE_ACTION=NONE')
    print('REPOSITORY_DELETION=NONE')
    print(f'PRIVATE_EQUIVALENCE_ZIP={zip_path}')
    print(f'PRIVATE_EQUIVALENCE_SIDECAR={sidecar}')
    print('DEVICE_OPERATION=NONE')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
