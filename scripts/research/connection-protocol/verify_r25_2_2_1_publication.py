#!/usr/bin/env python3
from __future__ import annotations

# R27.2.2 compatibility shim.
# Historical implementation SHA-256: af36ba9bc1a8165020c4a4b0d11cca76f0f5b23042cc7dc749d2f03582239320

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.research.canonical.r25_publication_verifier import verify

REVISION = 'r25.2.2.1'
HISTORICAL_SOURCE_SHA256 = 'af36ba9bc1a8165020c4a4b0d11cca76f0f5b23042cc7dc749d2f03582239320'


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--publication", type=Path, required=True)
    args = parser.parse_args()
    rc, _lines = verify(REPO, REVISION, args.publication, emit_output=True)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
