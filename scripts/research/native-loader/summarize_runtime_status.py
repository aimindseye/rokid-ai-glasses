#!/usr/bin/env python3
"""Validate and print the sanitized protected-loader status summary."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

REQUIRED_METHODS = {
    "load", "run", "d", "e", "cp", "ip", "ra", "getEnvInfo", "cl", "rp", "ed"
}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("status", type=Path)
    args = p.parse_args()
    data = json.loads(args.status.read_text(encoding="utf-8"))

    errors: list[str] = []
    closure = data.get("six_blocker_closure", {})
    if closure.get("resolved_count") != 6 or closure.get("total_count") != 6:
        errors.append("six-blocker closure is not 6/6")
    callbacks = data.get("callbacks", {})
    if callbacks.get("initializer_execution_count") != 29:
        errors.append("initializer execution count is not 29")
    if callbacks.get("finalizer_execution_count") != 0:
        errors.append("finalizer execution count is not 0")
    methods = data.get("register_natives", {}).get("myjni_methods", [])
    names = {m.get("name") for m in methods}
    if names != REQUIRED_METHODS:
        errors.append(f"unexpected MyJni method set: {sorted(names)}")
    if data.get("java_handoff", {}).get("application_oncreate_count") != 0:
        errors.append("public evidence must not claim Application.onCreate")

    if errors:
        print("SANITIZED_STATUS=FAIL")
        for error in errors:
            print(f"ERROR {error}")
        return 1

    print(f"TITLE={data['title']}")
    print(f"RUNTIME_ACCEPTANCE={data['runtime_acceptance']}")
    print("RUNTIME_BLOCKERS_RESOLVED=6_OF_6")
    print(f"MYJNI_METHOD_COUNT={len(methods)}")
    print(f"INIT_CALLBACK_EXECUTIONS={callbacks['initializer_execution_count']}")
    print(f"FINI_CALLBACK_EXECUTIONS={callbacks['finalizer_execution_count']}")
    print("SANITIZED_STATUS=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
