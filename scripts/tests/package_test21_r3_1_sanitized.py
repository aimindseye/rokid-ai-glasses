#!/usr/bin/env python3
# R27.1.7 compatibility shim. Original implementation preserved in the private retirement archive.
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.research.canonical.evidence_packager import package

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--evidence', required=True)
    ap.add_argument('--phone', required=True)
    a = ap.parse_args()
    rc, out, side = package(ROOT, 'r3.1', Path(a.evidence), a.phone, quiet=True)
    if rc != 0:
        return rc
    print('TEST21_R3_1_SANITIZED_PACKAGE=PASS')
    print('SANITIZED_ZIP=' + str(out))
    print('SANITIZED_ZIP_SHA256=' + __import__('hashlib').sha256(out.read_bytes()).hexdigest())
    print('SANITIZED_ZIP_SHA256_FILE=' + str(side))
    print('PRIVATE_RAW_EVIDENCE_INCLUDED=NO')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
