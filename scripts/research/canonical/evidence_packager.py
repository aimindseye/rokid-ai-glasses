#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path

try:
    from .primitives import read_json, sha256_file, write_sha256_sidecar
    from .privacy import CURRENT_FORBIDDEN_EXT, MAC_RE, PID_RE, TOKEN_RE, current_privacy_violation
except ImportError:
    try:
        from scripts.research.canonical.primitives import read_json, sha256_file, write_sha256_sidecar
        from scripts.research.canonical.privacy import CURRENT_FORBIDDEN_EXT, MAC_RE, PID_RE, TOKEN_RE, current_privacy_violation
    except ImportError:
        from primitives import read_json, sha256_file, write_sha256_sidecar
        from privacy import CURRENT_FORBIDDEN_EXT, MAC_RE, PID_RE, TOKEN_RE, current_privacy_violation

PROFILE_PATH = Path(__file__).with_name('profiles') / 'test21-sanitized-packagers.json'
FIXED_ZIP_TIME = (2026, 1, 1, 0, 0, 0)
def load_profiles() -> dict:
    return read_json(PROFILE_PATH)['profiles']


def _manifest_text(sanitized: Path, members: list[str]) -> str:
    return ''.join(f'{sha256_file(sanitized / name)}  {name}\n' for name in members)


def _verify_manifest(sanitized: Path, manifest_name: str) -> tuple[bool, str]:
    manifest = sanitized / manifest_name
    try:
        lines = manifest.read_text(encoding='utf-8', errors='strict').splitlines()
    except Exception as exc:
        return False, f'internal manifest unreadable: {exc}'
    for raw in lines:
        if not raw.strip():
            continue
        if '  ' not in raw:
            return False, f'malformed internal manifest entry: {raw}'
        expected, name = raw.split('  ', 1)
        target = sanitized / name
        if not target.is_file():
            return False, f'internal manifest target missing: {name}'
        actual = sha256_file(target)
        if actual != expected:
            return False, f'internal manifest mismatch: {name}'
    return True, ''


def _privacy_check(sanitized: Path, files: list[Path], profile: dict, phone: str) -> tuple[bool, str]:
    policy = profile.get('privacy_policy', 'none')
    if policy == 'none':
        return True, ''

    if policy == 'capture_tree':
        for p in sanitized.rglob('*'):
            if p.is_file() and p.suffix.lower() in {'.pcap', '.pcapng', '.keylog'}:
                return False, f'private capture material in sanitized tree: {p.name}'
        return True, ''

    if policy == 'forbidden_filename':
        forbidden = tuple(profile.get('forbidden_name_terms', []))
        for p in files:
            low = p.name.lower()
            if any(term in low for term in forbidden):
                return False, f'forbidden sanitized filename: {p.name}'
        return True, ''

    if policy in {'r1', 'r2', 'r3'}:
        forbidden = tuple(profile.get('forbidden_name_terms', []))
        for p in files:
            low = p.name.lower()
            if any(term in low for term in forbidden):
                return False, f'forbidden sanitized filename: {p.name}'
            text = p.read_text(encoding='utf-8', errors='replace')
            if phone and phone in text:
                return False, f'raw phone serial found in sanitized artifact: {p.name}'
            if policy in {'r2', 'r3'}:
                if TOKEN_RE.search(text):
                    return False, f'possible authorization token value found in sanitized artifact: {p.name}'
                if MAC_RE.search(text):
                    return False, f'Bluetooth MAC-like value found in sanitized artifact: {p.name}'
            if policy == 'r3' and PID_RE.search(text):
                return False, f'process identifier found in sanitized artifact: {p.name}'
        return True, ''

    if policy == 'current':
        summary_name = next((x for x in profile['members'] if x.endswith('-summary.json')), None)
        if summary_name:
            try:
                summary = json.loads((sanitized / summary_name).read_text(encoding='utf-8', errors='strict'))
            except Exception as exc:
                return False, f'summary json invalid: {exc}'
            if summary.get('fixture_mode'):
                return False, 'refusing to package fixture-mode result'
        for p in sanitized.rglob('*'):
            if not p.is_file():
                continue
            if p.suffix.lower() in CURRENT_FORBIDDEN_EXT:
                return False, f'forbidden file type: {p.name}'
            try:
                text = p.read_text(encoding='utf-8', errors='strict')
            except UnicodeDecodeError:
                return False, f'non-text file in sanitized tree: {p.name}'
            violation = current_privacy_violation(text)
            if violation:
                return False, f'privacy gate failed ({violation}) in {p.name}'
        return True, ''

    return False, f'unknown privacy policy: {policy}'


def package(repo: Path, revision: str, evidence: Path, phone: str = '', output: Path | None = None, quiet: bool = False) -> tuple[int, Path | None, Path | None]:
    profiles = load_profiles()
    if revision not in profiles:
        print(f'ERROR: unknown Test 21 packaging revision: {revision}', file=sys.stderr)
        return 2, None, None
    profile = profiles[revision]
    evidence = evidence.expanduser().resolve()
    sanitized = evidence / profile.get('input_subdir', 'sanitized')
    if not sanitized.is_dir():
        print(f'ERROR: sanitized directory missing: {sanitized}', file=sys.stderr)
        return 1, None, None

    members = list(profile['members'])
    missing = [name for name in members if not (sanitized / name).is_file()]
    if missing:
        print('ERROR: sanitized output incomplete: ' + ', '.join(missing), file=sys.stderr)
        return 1, None, None

    manifest_mode = profile.get('manifest_mode', 'none')
    manifest_name = profile.get('manifest_name')
    if manifest_mode in {'require', 'verify'}:
        if not manifest_name or not (sanitized / manifest_name).is_file():
            print(f'ERROR: required internal manifest missing: {manifest_name}', file=sys.stderr)
            return 1, None, None
        if manifest_mode == 'verify':
            ok, reason = _verify_manifest(sanitized, manifest_name)
            if not ok:
                print(f'ERROR: {reason}', file=sys.stderr)
                return 1, None, None
    elif manifest_mode == 'generate':
        if not manifest_name:
            print('ERROR: profile manifest_name missing', file=sys.stderr)
            return 1, None, None
        (sanitized / manifest_name).write_text(_manifest_text(sanitized, members), encoding='utf-8')
    elif manifest_mode != 'none':
        print(f'ERROR: unknown manifest mode: {manifest_mode}', file=sys.stderr)
        return 1, None, None

    expected_names = set(members)
    if manifest_name and manifest_mode != 'none':
        expected_names.add(manifest_name)
    mode = profile.get('file_set_mode', 'fixed')
    if mode == 'all_files':
        files = sorted(p for p in sanitized.iterdir() if p.is_file())
    elif mode == 'fixed':
        files = [sanitized / name for name in members]
        if manifest_name and manifest_mode != 'none':
            files.append(sanitized / manifest_name)
    elif mode == 'exact':
        actual_names = {p.name for p in sanitized.iterdir() if p.is_file()}
        if actual_names != expected_names:
            print('ERROR: sanitized file set mismatch: ' + ','.join(sorted(actual_names)), file=sys.stderr)
            return 1, None, None
        files = [sanitized / name for name in sorted(expected_names)]
    else:
        print(f'ERROR: unknown file_set_mode: {mode}', file=sys.stderr)
        return 1, None, None

    ok, reason = _privacy_check(sanitized, files, profile, phone)
    if not ok:
        print(f'ERROR: {reason}', file=sys.stderr)
        return 1, None, None

    out = output.expanduser().resolve() if output else Path(str(evidence) + '-sanitized-summary.zip')
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    container_mode = profile.get('container_mode', 'deterministic')
    if container_mode == 'historical_source_metadata':
        # Preserve the legacy ZipFile.write() semantics used by Test 21 r3.1/r3.2/r3.3.
        # The whole-container hash remains intentionally sensitive to source mtimes/mode,
        # matching the historical scripts rather than the deterministic canonical default.
        with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for p in files:
                archive.write(p, arcname=p.name)
    elif container_mode == 'deterministic':
        with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for p in files:
                info = zipfile.ZipInfo(p.name)
                info.date_time = FIXED_ZIP_TIME
                info.external_attr = 0o100644 << 16
                archive.writestr(info, p.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    else:
        print(f'ERROR: unknown container mode: {container_mode}', file=sys.stderr)
        return 1, None, None

    digest = sha256_file(out)
    sidecar = write_sha256_sidecar(out)
    if not quiet:
        print('R27_1_2_CANONICAL_SANITIZED_PACKAGE=PASS')
        print(f'REVISION={revision}')
        print(f'SANITIZED_ZIP={out}')
        print(f'SANITIZED_ZIP_SHA256={digest}')
        print(f'SANITIZED_ZIP_SHA256_FILE={sidecar}')
        print(f'PRIVACY_POLICY={profile.get("privacy_policy", "none")}')
        print(f'CONTAINER_MODE={container_mode}')
        print('PRIVATE_RAW_EVIDENCE_INCLUDED=NO')
        print('DEVICE_OPERATION=NONE')
    return 0, out, sidecar


def list_profiles() -> int:
    for revision, profile in sorted(load_profiles().items()):
        print(f'{revision}\t{profile["privacy_policy"]}\t{profile["legacy_packager"]}')
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='Canonical Test 21 sanitized-evidence packager')
    ap.add_argument('--repo', required=True)
    ap.add_argument('--revision')
    ap.add_argument('--evidence')
    ap.add_argument('--phone', default='')
    ap.add_argument('--output')
    ap.add_argument('--list', action='store_true')
    args = ap.parse_args(argv)
    if args.list:
        return list_profiles()
    if not args.revision or not args.evidence:
        ap.error('--revision and --evidence are required unless --list is used')
    repo = Path(args.repo).expanduser().resolve()
    if not (repo / 'scripts').is_dir():
        print(f'ERROR: repository root not recognized: {repo}', file=sys.stderr)
        return 2
    output = Path(args.output) if args.output else None
    rc, _, _ = package(repo, args.revision, Path(args.evidence), args.phone, output)
    return rc


if __name__ == '__main__':
    raise SystemExit(main())
