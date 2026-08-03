#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    from .primitives import read_json, run_text, sha256_file, source_lock
except ImportError:
    try:
        from scripts.research.canonical.primitives import read_json, run_text, sha256_file, source_lock
    except ImportError:
        from primitives import read_json, run_text, sha256_file, source_lock

PROFILE_PATH = Path(__file__).resolve().parent / "profiles" / "tool-test-suites.json"


@dataclass
class RunResult:
    track: str
    revision: str
    path: str
    returncode: int
    stdout: str
    source_lock: bool
    status: str
    timed_out: bool = False


sha256_path = sha256_file


def load_registry() -> dict:
    data = read_json(PROFILE_PATH)
    if data.get("schema") not in {"rokid.r27.1.4.tool-test-suites.v1", "rokid.r27.1.12.tool-test-suites.v2"}:
        raise ValueError("unexpected tool-test profile schema")
    return data


def profiles() -> list[dict]:
    return list(load_registry()["profiles"])


def find_profile(track: str, revision: str) -> dict:
    matches = [p for p in profiles() if p["track"] == track and p["revision"] == revision]
    if len(matches) != 1:
        raise KeyError(f"tool-test profile not uniquely found: track={track} revision={revision}")
    return matches[0]


def list_profiles(track: str | None = None) -> int:
    print("track\trevision\tstatus\ttest_count\texecution_class\tlegacy_test")
    for p in profiles():
        if track and p["track"] != track:
            continue
        print("\t".join([
            p["track"], p["revision"], p["status"], str(p["test_count"]),
            p["execution_class"], p["legacy_test"],
        ]))
    return 0


def run_profile(repo: Path, track: str, revision: str, *, emit_output: bool = True, allow_deferred: bool = False) -> RunResult:
    p = find_profile(track, revision)
    test_path = repo / p["legacy_test"]
    if not test_path.is_file():
        return RunResult(track, revision, p["legacy_test"], 3, f"ERROR: historical tool-test missing: {p['legacy_test']}\n", False, p["status"])
    source_lock_ok, _actual = source_lock(test_path, p["legacy_sha256"])
    if not source_lock_ok:
        return RunResult(track, revision, p["legacy_test"], 4, f"ERROR: historical tool-test source lock mismatch: {p['legacy_test']}\n", False, p["status"])
    if p["status"] != "CURRENT_EQUIVALENT" and not allow_deferred:
        reason = p.get("deferred_reason") or "historical suite is deferred"
        missing = [x for x in p.get("required_fixture_paths", []) if not (repo / x).exists()]
        detail = f"; missing={','.join(missing)}" if missing else ""
        return RunResult(track, revision, p["legacy_test"], 5, f"DEFERRED: {reason}{detail}\n", True, p["status"])

    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    cp = run_text(
        [sys.executable, p["legacy_test"]],
        cwd=repo,
        timeout=int(p.get("timeout_seconds", 45)),
        env=env,
    )
    out = cp.stdout + cp.stderr
    if emit_output and out:
        sys.stdout.write(out)
    if cp.returncode == 124:
        msg = f"ERROR: canonical tool-test timeout after {p.get('timeout_seconds',45)} seconds\n"
        if emit_output:
            sys.stdout.write(msg)
        return RunResult(track, revision, p["legacy_test"], 124, out + msg, True, p["status"], timed_out=True)
    return RunResult(track, revision, p["legacy_test"], cp.returncode, out, True, p["status"])



def verify_oracle_locks(repo: Path, *, emit_output: bool = True) -> tuple[int, dict]:
    reg = load_registry()
    rows = []
    failures = 0
    preserved = 0
    historical = 0
    for p in reg["profiles"]:
        test_path = repo / p["legacy_test"]
        locked, actual = source_lock(test_path, p["legacy_sha256"])
        state = p.get("oracle_state", "UNCLASSIFIED")
        if state == "PRESERVE_REGRESSION_ORACLE":
            preserved += 1
        elif state == "PRESERVE_HISTORICAL":
            historical += 1
        else:
            failures += 1
        if not locked:
            failures += 1
        rows.append({
            "track": p["track"], "revision": p["revision"],
            "legacy_test": p["legacy_test"], "oracle_state": state,
            "source_lock": "PASS" if locked else "FAIL",
            "actual_sha256": actual, "expected_sha256": p["legacy_sha256"],
        })
    summary = {
        "profile_count": len(rows),
        "preserve_regression_oracle_count": preserved,
        "preserve_historical_count": historical,
        "source_lock_failure_count": sum(r["source_lock"] != "PASS" for r in rows),
        "classification_failure_count": failures - sum(r["source_lock"] != "PASS" for r in rows),
        "status": "PASS" if failures == 0 and preserved == 38 and historical == 1 else "FAIL",
    }
    if emit_output:
        print(f"R27_1_12_TOOL_TEST_ORACLE_LOCKS={summary['status']}")
        print(f"TOOL_TEST_PROFILE_COUNT={summary['profile_count']}")
        print(f"PRESERVE_REGRESSION_ORACLE_COUNT={summary['preserve_regression_oracle_count']}")
        print(f"TOOL_TEST_PRESERVE_HISTORICAL_COUNT={summary['preserve_historical_count']}")
        print(f"TOOL_TEST_SOURCE_LOCK_FAILURE_COUNT={summary['source_lock_failure_count']}")
        print("DEVICE_OPERATION=NONE")
    return (0 if summary["status"] == "PASS" else 1), {"rows": rows, "summary": summary}

def run_cli(repo: Path, track: str, revision: str) -> int:
    result = run_profile(repo, track, revision, emit_output=True)
    print(f"R27_1_4_CANONICAL_TOOL_TEST={'PASS' if result.returncode == 0 else 'FAIL'}")
    print(f"TRACK={track}")
    print(f"REVISION={revision}")
    print(f"LEGACY_TEST={result.path}")
    print(f"SOURCE_LOCK={'PASS' if result.source_lock else 'FAIL'}")
    print(f"PROFILE_STATUS={result.status}")
    print("DEVICE_OPERATION=NONE")
    return result.returncode
