#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import contextlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

try:
    from evidence_packager import load_profiles, package, sha256_file, current_privacy_violation
except ImportError:
    from scripts.research.canonical.evidence_packager import load_profiles, package, sha256_file, current_privacy_violation


def _safe_content(name: str, revision: str) -> str:
    if name.endswith('.json'):
        return json.dumps({'revision': revision, 'fixture_mode': False, 'status': 'PASS'}, sort_keys=True) + '\n'
    if name.endswith('.jsonl'):
        return json.dumps({'revision': revision, 'status': 'PASS'}, sort_keys=True) + '\n'
    if name.endswith('.tsv'):
        return f'field\tvalue\nrevision\t{revision}\n'
    if name.endswith('.md'):
        return f'# Synthetic safe result\n\nRevision `{revision}`.\n'
    return f'SYNTHETIC_SAFE_RESULT=YES\nREVISION={revision}\n'


def _write_required_manifest(san: Path, profile: dict) -> None:
    name = profile.get('manifest_name')
    if not name:
        return
    lines = []
    for member in profile['members']:
        p = san / member
        lines.append(f'{sha256_file(p)}  {member}\n')
    (san / name).write_text(''.join(lines), encoding='utf-8')


def _fixture(root: Path, profile: dict, revision: str) -> Path:
    san = root / profile.get('input_subdir', 'sanitized')
    san.mkdir(parents=True, exist_ok=True)
    for name in profile['members']:
        (san / name).write_text(_safe_content(name, revision), encoding='utf-8')
    if profile.get('manifest_mode') in {'require', 'verify'}:
        _write_required_manifest(san, profile)
    return san


def _legacy_run(repo: Path, profile: dict, evidence: Path, output: Path) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(repo / profile['legacy_packager'])]
    mode = profile['legacy_cli']
    if mode == 'input_zip':
        cmd += ['--input', str(evidence / profile['input_subdir']), '--zip', str(output)]
    else:
        cmd += ['--evidence', str(evidence)]
        if profile.get('phone_required'):
            cmd += ['--phone', 'SYNTHETIC_PHONE']
        if mode == 'evidence_output':
            cmd += ['--output', str(output)]
    return subprocess.run(cmd, cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)


def _legacy_output(profile: dict, evidence: Path, explicit_output: Path) -> Path:
    return explicit_output if profile['legacy_cli'] in {'input_zip', 'evidence_output'} else Path(str(evidence) + '-sanitized-summary.zip')


def _zip_member_bytes(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as z:
        return {name: z.read(name) for name in z.namelist()}


def _sidecar_valid(zip_path: Path) -> bool:
    side = Path(str(zip_path) + '.sha256')
    if not side.is_file():
        return False
    expected = side.read_text(encoding='utf-8', errors='replace').split()[0]
    return expected == sha256_file(zip_path)


def verify(repo: Path, output: Path | None = None) -> int:
    profiles = load_profiles()
    rows = []
    failures = 0

    for revision, profile in sorted(profiles.items()):
        legacy_path = repo / profile['legacy_packager']
        source_lock = legacy_path.is_file() and sha256_file(legacy_path) == profile['legacy_sha256']
        with tempfile.TemporaryDirectory(prefix='r2712-') as td:
            base = Path(td)
            legacy_ev = base / 'legacy-evidence'
            canonical_ev = base / 'canonical-evidence'
            _fixture(legacy_ev, profile, revision)
            shutil.copytree(legacy_ev, canonical_ev)

            legacy_explicit = base / 'legacy.zip'
            legacy_proc = _legacy_run(repo, profile, legacy_ev, legacy_explicit)
            legacy_zip = _legacy_output(profile, legacy_ev, legacy_explicit)

            canonical_zip = base / 'canonical.zip'
            canonical_rc, canonical_out, canonical_side = package(
                repo, revision, canonical_ev,
                'SYNTHETIC_PHONE' if profile.get('phone_required') else '',
                canonical_zip, quiet=True,
            )

            members_equal = False
            if legacy_proc.returncode == 0 and canonical_rc == 0 and legacy_zip.is_file() and canonical_zip.is_file():
                members_equal = _zip_member_bytes(legacy_zip) == _zip_member_bytes(canonical_zip)

            marker_ok = all(marker in legacy_proc.stdout for marker in profile.get('legacy_pass_markers', []))
            sidecars_ok = legacy_zip.is_file() and canonical_zip.is_file() and _sidecar_valid(legacy_zip) and _sidecar_valid(canonical_zip)

            # Missing-member negative gate: canonical packager must refuse an incomplete evidence set.
            missing_ev = base / 'missing-evidence'
            missing_san = _fixture(missing_ev, profile, revision)
            first_member = profile['members'][0]
            (missing_san / first_member).unlink()
            with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                missing_rc, _, _ = package(repo, revision, missing_ev, '', base / 'missing.zip', quiet=True)
            missing_gate = missing_rc != 0

            equivalent = all([
                source_lock,
                legacy_proc.returncode == 0,
                canonical_rc == 0,
                members_equal,
                marker_ok,
                sidecars_ok,
                missing_gate,
            ])
            if not equivalent:
                failures += 1
            rows.append({
                'revision': revision,
                'legacy_packager': profile['legacy_packager'],
                'legacy_source_lock': 'YES' if source_lock else 'NO',
                'legacy_rc': legacy_proc.returncode,
                'canonical_rc': canonical_rc,
                'archive_member_content_equal': 'YES' if members_equal else 'NO',
                'legacy_pass_markers_found': 'YES' if marker_ok else 'NO',
                'sidecars_valid': 'YES' if sidecars_ok else 'NO',
                'missing_member_rejected': 'YES' if missing_gate else 'NO',
                'equivalent': 'YES' if equivalent else 'NO',
            })

    dotted_version_safe = current_privacy_violation('revision r3.3.4.2.6.1.3 is accepted') is None
    standalone_ipv4_rejected = current_privacy_violation('endpoint 192.0.2.55 is private evidence') == 'ipv4'
    if not dotted_version_safe or not standalone_ipv4_rejected:
        failures += 1

    summary = {
        'schema': 'rokid.r27.1.2.test21-packager-equivalence.v1',
        'status': 'PASS' if failures == 0 else 'FAIL',
        'profile_count': len(profiles),
        'equivalent_count': sum(r['equivalent'] == 'YES' for r in rows),
        'failure_count': failures,
        'legacy_packager_source_changed_count': sum(r['legacy_source_lock'] != 'YES' for r in rows),
        'dotted_version_ipv4_false_positive_regression': 'PASS' if dotted_version_safe else 'FAIL',
        'standalone_ipv4_rejection_regression': 'PASS' if standalone_ipv4_rejected else 'FAIL',
        'legacy_packager_action': 'NONE',
        'repository_deletion': 'NONE',
        'device_operation': 'NONE',
    }

    if output:
        output.mkdir(parents=True, exist_ok=True)
        fields = list(rows[0].keys()) if rows else []
        with (output / 'test21-packager-equivalence.tsv').open('w', encoding='utf-8', newline='') as f:
            w = csv.DictWriter(f, fieldnames=fields, delimiter='\t', lineterminator='\n')
            w.writeheader(); w.writerows(rows)
        (output / 'summary.json').write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n', encoding='utf-8')

    print('R27_1_2_EQUIVALENCE=' + summary['status'])
    print(f'TEST21_PACKAGER_PROFILE_COUNT={summary["profile_count"]}')
    print(f'TEST21_LEGACY_CANONICAL_EQUIVALENT_COUNT={summary["equivalent_count"]}')
    print(f'LEGACY_PACKAGER_SOURCE_CHANGED_COUNT={summary["legacy_packager_source_changed_count"]}')
    print(f'DOTTED_VERSION_IPV4_FALSE_POSITIVE_REGRESSION={summary["dotted_version_ipv4_false_positive_regression"]}')
    print(f'STANDALONE_IPV4_REJECTION_REGRESSION={summary["standalone_ipv4_rejection_regression"]}')
    print('LEGACY_PACKAGER_ACTION=NONE')
    print('REPOSITORY_DELETION=NONE')
    print('DEVICE_OPERATION=NONE')
    return 0 if failures == 0 else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', required=True)
    ap.add_argument('--output')
    args = ap.parse_args(argv)
    return verify(Path(args.repo).expanduser().resolve(), Path(args.output).expanduser().resolve() if args.output else None)


if __name__ == '__main__':
    raise SystemExit(main())
