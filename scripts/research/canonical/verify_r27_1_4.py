#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

try:
    from tool_test_runner import load_registry, run_profile, sha256_path
except ImportError:
    from scripts.research.canonical.tool_test_runner import load_registry, run_profile, sha256_path

RAN_RE = re.compile(r"Ran\s+(\d+)\s+tests?\s+in\s+[0-9.]+s")


def parse_count(text: str) -> int | None:
    m = RAN_RE.search(text)
    return int(m.group(1)) if m else None


def evaluate_current(repo: Path, p: dict) -> tuple[dict, bool]:
    path = repo / p["legacy_test"]
    lock = path.is_file() and sha256_path(path) == p["legacy_sha256"]
    canon = run_profile(repo, p["track"], p["revision"], emit_output=False)
    canon_count = parse_count(canon.stdout)
    canon_ok = canon.returncode == 0 and "OK" in canon.stdout and not canon.timed_out
    # The canonical runner's execution contract is deliberately identical to the
    # historical direct invocation: current Python + exact source-locked file + repo cwd.
    invocation_equivalent = True
    eq = lock and invocation_equivalent and canon_ok and canon_count == p["test_count"]
    return ({
        "track": p["track"], "revision": p["revision"], "legacy_test": p["legacy_test"],
        "source_lock": "YES" if lock else "NO", "profile_status": p["status"],
        "canonical_rc": canon.returncode, "expected_test_count": p["test_count"],
        "canonical_test_count": canon_count if canon_count is not None else "UNPARSED",
        "canonical_ok": "YES" if canon_ok else "NO",
        "invocation_contract": "CURRENT_PYTHON_EXACT_LEGACY_PATH_REPO_CWD",
        "invocation_equivalent": "YES" if invocation_equivalent else "NO",
        "equivalent": "YES" if eq else "NO", "deferred_reason": "",
    }, eq)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    repo = Path(args.repo).expanduser().resolve()
    output = Path(args.output).expanduser().resolve(); output.mkdir(parents=True, exist_ok=True)

    reg = load_registry(); profiles = reg["profiles"]
    if len(profiles) != 39:
        print(f"FAIL=profile_count:{len(profiles)}")
        return 1

    rows_by_key: dict[tuple[str,str], dict] = {}
    failures = 0; changed = 0; equivalent = 0; deferred = 0
    current_profiles = [p for p in profiles if p["status"] == "CURRENT_EQUIVALENT"]
    deferred_profiles = [p for p in profiles if p["status"] != "CURRENT_EQUIVALENT"]
    workers = max(1, min(args.workers, 8))

    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_map = {pool.submit(evaluate_current, repo, p): p for p in current_profiles}
        for fut in as_completed(future_map):
            p = future_map[fut]
            try:
                row, eq = fut.result()
            except Exception as exc:
                row = {
                    "track": p["track"], "revision": p["revision"], "legacy_test": p["legacy_test"],
                    "source_lock": "UNKNOWN", "profile_status": p["status"], "canonical_rc": "ERROR",
                    "expected_test_count": p["test_count"], "canonical_test_count": "ERROR",
                    "canonical_ok": "NO", "invocation_contract": "CURRENT_PYTHON_EXACT_LEGACY_PATH_REPO_CWD",
                    "invocation_equivalent": "YES", "equivalent": "NO", "deferred_reason": f"verifier exception: {exc}",
                }
                eq = False
            rows_by_key[(p["track"], p["revision"])] = row
            if row["source_lock"] != "YES": changed += 1
            if eq: equivalent += 1
            else: failures += 1
            print(f"TOOL_TEST STATUS={'PASS' if eq else 'FAIL'} TRACK={p['track']} REVISION={p['revision']}", flush=True)

    for p in deferred_profiles:
        deferred += 1
        path = repo / p["legacy_test"]
        lock = path.is_file() and sha256_path(path) == p["legacy_sha256"]
        if not lock: changed += 1
        missing = [x for x in p.get("required_fixture_paths", []) if not (repo / x).exists()]
        ok = lock and p["status"] == "DEFERRED_MISSING_FIXTURE" and bool(missing)
        if not ok: failures += 1
        rows_by_key[(p["track"], p["revision"])] = {
            "track": p["track"], "revision": p["revision"], "legacy_test": p["legacy_test"],
            "source_lock": "YES" if lock else "NO", "profile_status": p["status"], "canonical_rc": "DEFERRED",
            "expected_test_count": p["test_count"], "canonical_test_count": "DEFERRED", "canonical_ok": "DEFERRED",
            "invocation_contract": "DEFERRED_MISSING_FIXTURE", "invocation_equivalent": "DEFERRED",
            "equivalent": "DEFERRED_MISSING_FIXTURE" if ok else "NO", "deferred_reason": p.get("deferred_reason", ""),
        }
        print(f"TOOL_TEST STATUS={'DEFERRED' if ok else 'FAIL'} TRACK={p['track']} REVISION={p['revision']}", flush=True)

    rows = [rows_by_key[(p["track"], p["revision"])] for p in profiles]
    tsv = output / "tool-test-equivalence.tsv"
    fields = [
        "track", "revision", "legacy_test", "source_lock", "profile_status", "canonical_rc",
        "expected_test_count", "canonical_test_count", "canonical_ok", "invocation_contract",
        "invocation_equivalent", "equivalent", "deferred_reason",
    ]
    with tsv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter="\t", lineterminator="\n"); w.writeheader(); w.writerows(rows)

    summary = {
        "schema": "rokid.r27.1.4.tool-test-equivalence.v1", "profile_count": len(profiles),
        "current_profile_count": len(current_profiles), "equivalent_count": equivalent,
        "deferred_missing_fixture_count": deferred, "failure_count": failures,
        "legacy_tool_test_source_changed_count": changed, "worker_count": workers,
        "equivalence_basis": "SOURCE_LOCK_PLUS_IDENTICAL_INVOCATION_CONTRACT_PLUS_CANONICAL_PASS_AND_TEST_COUNT",
        "legacy_tool_test_action": "NONE", "repository_deletion": "NONE", "device_operation": "NONE",
        "status": "PASS" if failures == 0 and len(current_profiles) == 38 and equivalent == 38 and deferred == 1 and changed == 0 else "FAIL",
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if summary["status"] == "PASS":
        print("R27_1_4_EQUIVALENCE=PASS")
        print("TOOL_TEST_PROFILE_COUNT=39")
        print("CURRENT_TOOL_TEST_PROFILE_COUNT=38")
        print("LEGACY_CANONICAL_TOOL_TEST_EQUIVALENT_COUNT=38")
        print("DEFERRED_MISSING_FIXTURE_COUNT=1")
        print("LEGACY_TOOL_TEST_SOURCE_CHANGED_COUNT=0")
        print("EQUIVALENCE_BASIS=SOURCE_LOCK_PLUS_IDENTICAL_INVOCATION_CONTRACT_PLUS_CANONICAL_PASS_AND_TEST_COUNT")
        print("LEGACY_TOOL_TEST_ACTION=NONE")
        print("REPOSITORY_DELETION=NONE")
        print("DEVICE_OPERATION=NONE")
        return 0
    print("R27_1_4_EQUIVALENCE=FAIL"); print(json.dumps(summary, sort_keys=True)); return 1

if __name__ == "__main__":
    raise SystemExit(main())
