#!/usr/bin/env python3
from __future__ import annotations

# R27.2.2 compatibility shim.
# Historical implementation SHA-256: 8343c29d594ff39f1eff501e7c0257dd60f6cb1fc45047f5d0a15bb490d0c7dc

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.research.canonical.r25_finalizer import finalize

REVISION = 'r25.2.2.1'
HISTORICAL_SOURCE_SHA256 = '8343c29d594ff39f1eff501e7c0257dd60f6cb1fc45047f5d0a15bb490d0c7dc'


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    rc, _archive, _sidecar = finalize(REPO, REVISION, args.run)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
