#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import zipfile
from pathlib import Path

try:
    from primitives import sha256_file
except ImportError:
    from scripts.research.canonical.primitives import sha256_file

PROFILE_PATH = Path(__file__).resolve().parent / "profiles" / "r25-finalizers.json"


def load_profiles() -> list[dict]:
    data = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    if data.get("schema") != "rokid.r27.2.1.r25-finalizers.v1":
        raise RuntimeError("unexpected r25 finalizer profile schema")
    return list(data.get("profiles", []))


def profile_for(revision: str) -> dict:
    for profile in load_profiles():
        if profile.get("revision") == revision:
            return profile
    raise KeyError(revision)


def list_profiles() -> int:
    for profile in load_profiles():
        print(f"{profile['revision']}\t{profile['legacy_path']}\t{profile['archive']['zip_mode']}")
    return 0


def _selected_files(run: Path, profile: dict) -> list[Path]:
    manifest_name = profile["manifest"]["filename"]
    selection = profile["manifest"]["selection"]
    if selection == "all_except_manifest":
        return [
            path for path in sorted(run.rglob("*"))
            if path.is_file() and path.name != manifest_name
        ]
    if selection == "required_plus_optional":
        included: list[Path] = []
        for rel in profile["requirements"].get("required", []):
            path = run / rel
            if not path.is_file():
                raise SystemExit(f"ERROR: required evidence missing: {rel}")
            included.append(path)
        for rel in profile["requirements"].get("optional", []):
            path = run / rel
            if path.is_file():
                included.append(path)
        return included
    raise RuntimeError(f"unknown finalizer selection: {selection}")


def _validate_requirements(run: Path, profile: dict) -> None:
    # r25.2.1 historically used a different error phrase from later selective finalizers.
    revision = profile["revision"]
    if profile["manifest"]["selection"] == "required_plus_optional":
        return
    for rel in profile["requirements"].get("required", []):
        path = run / rel
        if not path.is_file():
            if revision == "r25.2.1":
                raise SystemExit(f"ERROR: required run artifact missing: {path}")
            raise SystemExit(f"ERROR: required evidence missing: {rel}")


def _manifest_value(run: Path, selected: list[Path], profile: dict):
    manifest = profile["manifest"]
    kind = manifest["kind"]
    if kind == "r25_file_manifest_v1":
        return {
            "schema": "rokid.r25.file-manifest.v1",
            "files": [
                {
                    "path": path.relative_to(run).as_posix(),
                    "size": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
                for path in selected
            ],
        }
    if kind == "sha256_map":
        return {
            str(path.relative_to(run)): sha256_file(path)
            for path in selected
        }
    if kind == "sha256_sizebytes_map":
        return {
            str(path.relative_to(run)): {
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
            }
            for path in selected
        }
    if kind == "sha256_size_map":
        return {
            str(path.relative_to(run)): {
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in selected
        }
    if kind == "release_records":
        return {
            "schema": manifest["schema"],
            "release": manifest["release"],
            "files": [
                {
                    "path": path.relative_to(run).as_posix(),
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
                for path in selected
            ],
        }
    raise RuntimeError(f"unknown manifest kind: {kind}")


def _write_manifest(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _archive_source_metadata(run: Path, archive: Path, members: list[Path]) -> None:
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
        for path in members:
            output.write(path, arcname=f"{run.name}/{path.relative_to(run)}")


def _archive_r25_deterministic(run: Path, archive: Path, members: list[Path]) -> None:
    if archive.exists():
        archive.unlink()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        for path in members:
            info = zipfile.ZipInfo(path.relative_to(run.parent).as_posix())
            info.date_time = (2026, 7, 26, 0, 0, 0)
            mode = 0o755 if os.access(path, os.X_OK) else 0o644
            info.external_attr = (mode & 0xFFFF) << 16
            output.writestr(info, path.read_bytes())


def finalize(repo: Path, revision: str, run: Path) -> tuple[int, Path | None, Path | None]:
    del repo  # retained for a stable canonical signature
    try:
        profile = profile_for(revision)
    except KeyError:
        print(f"ERROR: unknown r25 finalizer revision: {revision}")
        return 2, None, None

    run = run.expanduser().resolve()
    if revision == "r25.2.1" and not run.is_dir():
        print(f"ERROR: run directory not found: {run}")
        return 1, None, None
    if not run.is_dir():
        # Other historical scripts eventually fail on missing paths; canonicalize that into a bounded error.
        print(f"ERROR: run directory not found: {run}")
        return 1, None, None

    try:
        _validate_requirements(run, profile)
        selected = _selected_files(run, profile)
    except SystemExit as exc:
        print(str(exc))
        return 1, None, None

    manifest_path = run / profile["manifest"]["filename"]
    manifest_value = _manifest_value(run, selected, profile)
    _write_manifest(manifest_path, manifest_value)

    membership = profile["archive"]["membership"]
    if membership == "all_after_manifest":
        members = [path for path in sorted(run.rglob("*")) if path.is_file()]
    elif membership == "selected_plus_manifest":
        members = list(selected) + [manifest_path]
    else:
        raise RuntimeError(f"unknown archive membership: {membership}")

    archive = run.parent / f"{run.name}{profile['archive']['suffix']}"
    zip_mode = profile["archive"]["zip_mode"]
    if zip_mode == "r25_deterministic_tree":
        _archive_r25_deterministic(run, archive, members)
    elif zip_mode == "source_metadata":
        _archive_source_metadata(run, archive, members)
    else:
        raise RuntimeError(f"unknown zip mode: {zip_mode}")

    archive_hash = sha256_file(archive)
    sidecar = Path(str(archive) + ".sha256")
    sidecar.write_text(f"{archive_hash}  {archive.name}\n", encoding="utf-8")

    mode = profile["manifest"].get("print_count", "none")
    if mode == "records_excluding_manifest":
        manifest_count = len(selected)
    elif mode == "records_plus_manifest":
        manifest_count = len(selected) + 1
    else:
        manifest_count = len(selected)

    values = {
        "manifest_count": manifest_count,
        "manifest_path": manifest_path,
        "archive": archive,
        "archive_sha256": archive_hash,
    }
    for line in profile.get("stdout", []):
        print(line.format(**values))
    return 0, archive, sidecar


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Canonical profile-driven r25 private-evidence finalizer")
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--revision")
    parser.add_argument("--run", type=Path)
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args(argv)
    if args.list:
        return list_profiles()
    if not args.revision or args.run is None:
        parser.error("--revision and --run are required")
    rc, _archive, _sidecar = finalize(args.repo.expanduser().resolve(), args.revision, args.run)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
