#!/usr/bin/env python3
from __future__ import annotations

# R27.2.2 compatibility shim.
# Historical implementation SHA-256: 2e3437dcc3beaa173eb456b79c19b522623687f7dc73c56c6dc1f0202819b4b1

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.research.canonical.r25_finalizer import finalize

REVISION = 'r25.2.2.2'
HISTORICAL_SOURCE_SHA256 = '2e3437dcc3beaa173eb456b79c19b522623687f7dc73c56c6dc1f0202819b4b1'


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    rc, _archive, _sidecar = finalize(REPO, REVISION, args.run)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
