#!/usr/bin/env python3
# R27.1.10 compatibility shim. Original implementation preserved in the private retirement archive.
# The historical CLI/path remains stable; implementation delegates to the canonical packager.
# compatibility-contract marker: ALLOWED
# compatibility-contract marker: parcel-contract.tsv

from __future__ import annotations
import argparse,hashlib,sys
from pathlib import Path
def _repo_root() -> Path:
    p=Path(__file__).resolve()
    for parent in p.parents:
        if (parent/'scripts'/'rokid-research').is_file(): return parent
    raise RuntimeError('repository root not found')
ROOT=_repo_root()
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from scripts.research.canonical.evidence_packager import package
REVISION='r3.3.4.2.6.1'

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--evidence', required=True, type=Path)
    ap.add_argument('--phone', default='')
    a=ap.parse_args()
    rc,out,side=package(ROOT, REVISION, a.evidence, a.phone, None, quiet=True)
    if rc != 0: return rc
    print('SANITIZED_PACKAGE=PASS')
    print('PRIVATE_AAR_INCLUDED=NO')
    print('PRIVATE_CLASS_BYTES_INCLUDED=NO')
    print('DEVICE_SERIAL_INCLUDED=NO')
    print('AUTH_TOKEN_INCLUDED=NO')
    print('SANITIZED_ZIP=' + str(out))
    print('SANITIZED_ZIP_SHA256=' + hashlib.sha256(out.read_bytes()).hexdigest())
    return 0

if __name__=='__main__': raise SystemExit(main())
