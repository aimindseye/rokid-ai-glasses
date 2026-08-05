#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

POLICY_PATTERNS = (
    re.compile(r"not allow package install!?", re.I),
    re.compile(r"install[_ ]failed[_ ]user[_ ]restricted", re.I),
)


def classify(text: str, rc: int) -> str:
    if rc == 0 and re.search(r"\bSuccess\b", text):
        return "SUCCESS"
    for pat in POLICY_PATTERNS:
        if pat.search(text):
            return "BLOCKED_STANDARD_ADB_APK_INSTALL"
    return "UNCLASSIFIED_INSTALL_FAILURE"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", required=True)
    ap.add_argument("--return-code", required=True, type=int)
    ap.add_argument("--json-output")
    args = ap.parse_args()
    text = Path(args.log).read_text(encoding="utf-8", errors="replace")
    result = classify(text, args.return_code)
    if args.json_output:
        Path(args.json_output).write_text(
            json.dumps({
                "schema": "rokid.test22.install-policy.v1",
                "classification": result,
                "install_return_code": args.return_code,
            }, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
