#!/usr/bin/env python3
from __future__ import annotations

# R27.2.2 compatibility shim.
# Historical implementation SHA-256: 55ee7ef33348e224dbb4376c9e6d3a9bc2ee8013caf4f0268997c240658be411

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.research.canonical.r25_publication_verifier import verify

REVISION = 'r25.2.2'
HISTORICAL_SOURCE_SHA256 = '55ee7ef33348e224dbb4376c9e6d3a9bc2ee8013caf4f0268997c240658be411'


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--publication", type=Path, required=True)
    args = parser.parse_args()
    rc, _lines = verify(REPO, REVISION, args.publication, emit_output=True)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
