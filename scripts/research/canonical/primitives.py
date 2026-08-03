#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def source_lock(path: Path, expected_sha256: str) -> tuple[bool, str]:
    if not path.is_file():
        return False, ''
    actual = sha256_file(path)
    return actual == expected_sha256, actual


def run_text(
    argv: Sequence[str],
    *,
    cwd: Path | None = None,
    timeout: int | None = None,
    env: dict[str, str] | None = None,
) -> CommandResult:
    try:
        cp = subprocess.run(
            list(argv),
            cwd=str(cwd) if cwd else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            env=env,
            check=False,
        )
        return CommandResult(cp.returncode, cp.stdout, cp.stderr)
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout if isinstance(exc.stdout, str) else ''
        err = exc.stderr if isinstance(exc.stderr, str) else ''
        return CommandResult(124, out, err)


def python_syntax(path: Path) -> tuple[bool, str]:
    try:
        compile(path.read_text(encoding='utf-8'), str(path), 'exec')
        return True, ''
    except Exception as exc:
        return False, str(exc)


def bash_syntax(path: Path) -> tuple[bool, str]:
    result = run_text(['bash', '-n', str(path)])
    return result.returncode == 0, result.stderr


def require_regular_file(path: Path, *, nonempty: bool = False, no_symlink: bool = False) -> tuple[bool, str]:
    if not path.is_file():
        return False, 'missing'
    if nonempty and path.stat().st_size == 0:
        return False, 'empty'
    if no_symlink and path.is_symlink():
        return False, 'symlink'
    return True, ''


def missing_markers(text: str, markers: Iterable[str]) -> list[str]:
    return [marker for marker in markers if marker not in text]


def first_regex_match(text: str, pattern: str, *, ignore_case: bool = False):
    flags = re.MULTILINE | (re.IGNORECASE if ignore_case else 0)
    return re.compile(pattern, flags).search(text)


def write_sha256_sidecar(path: Path) -> Path:
    sidecar = Path(str(path) + '.sha256')
    sidecar.write_text(f'{sha256_file(path)}  {path.name}\n', encoding='utf-8')
    return sidecar
