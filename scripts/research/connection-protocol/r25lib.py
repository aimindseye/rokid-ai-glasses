#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

MAC_RE = re.compile(r"(?i)\b(?:[0-9a-f]{2}:){5}[0-9a-f]{2}\b")
SERIAL_RE = re.compile(r"(?i)\b(?:R58|RF|ZX|FA|HT|emulator-)[A-Za-z0-9._:-]{4,}\b")
TOKEN_RE = re.compile(r"(?i)(authorization|bearer|access[_-]?token|refresh[_-]?token|cookie)\s*[:=]\s*[^\s,;]+")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def run(command: list[str], *, check: bool = True, capture: bool = True, text: bool = True, timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=check, capture_output=capture, text=text, timeout=timeout)


def adb(serial: str, *args: str, check: bool = True, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return run(["adb", "-s", serial, *args], check=check, timeout=timeout)


def sanitize_text(value: str) -> str:
    value = MAC_RE.sub("<MAC_REDACTED>", value)
    value = SERIAL_RE.sub("<SERIAL_REDACTED>", value)
    value = TOKEN_RE.sub(lambda match: match.group(1) + "=<REDACTED>", value)
    value = re.sub(r"/Users/[^/\s]+", "/Users/<USER>", value)
    value = re.sub(r"/home/[^/\s]+", "/home/<USER>", value)
    return value


def manifest(root: Path, output: Path, *, exclude: Iterable[Path] = ()) -> list[dict[str, Any]]:
    excluded = {item.resolve() for item in exclude}
    rows: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.resolve() in excluded:
            continue
        rows.append({
            "path": path.relative_to(root).as_posix(),
            "size": path.stat().st_size,
            "sha256": sha256_file(path),
        })
    write_json(output, {"schema": "rokid.r25.file-manifest.v1", "files": rows})
    return rows


def verify_manifest(root: Path, manifest_path: Path) -> tuple[bool, list[str]]:
    data = read_json(manifest_path)
    errors: list[str] = []
    for row in data.get("files", []):
        path = root / row["path"]
        if not path.is_file():
            errors.append(f"missing:{row['path']}")
            continue
        if path.stat().st_size != row["size"]:
            errors.append(f"size:{row['path']}")
        if sha256_file(path) != row["sha256"]:
            errors.append(f"sha256:{row['path']}")
    return not errors, errors


def safe_zip_tree(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        destination.unlink()
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_file():
                info = zipfile.ZipInfo(path.relative_to(source.parent).as_posix())
                info.date_time = (2026, 7, 26, 0, 0, 0)
                mode = 0o755 if os.access(path, os.X_OK) else 0o644
                info.external_attr = (mode & 0xFFFF) << 16
                archive.writestr(info, path.read_bytes())


def require_command(name: str) -> str:
    value = shutil.which(name)
    if value is None:
        raise SystemExit(f"required command not found: {name}")
    return value
