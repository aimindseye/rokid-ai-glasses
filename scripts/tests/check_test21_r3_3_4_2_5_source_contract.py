#!/usr/bin/env python3
from __future__ import annotations
import argparse
import re  # compatibility export used by the r2 historical regression suite
import sys
from pathlib import Path

# R27.1.11 compatibility entry point.  The historical implementation bytes are
# preserved privately; validation is delegated to the canonical accepted-source
# snapshot engine for test21:r3.3.4.2.5.
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    args = ap.parse_args()
    repo = Path(args.repo).expanduser().resolve()
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))
    from scripts.research.canonical.source_contract import compatibility_check
    return compatibility_check(repo, "test21", "r3.3.4.2.5")

if __name__ == "__main__":
    raise SystemExit(main())
