#!/usr/bin/env python3
# R27.1.10 compatibility shim. Original implementation preserved in the private retirement archive.
# The historical CLI/path remains stable; implementation delegates to the canonical packager.

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
from scripts.research.canonical.privacy import current_privacy_violation
REVISION='r3.3.4.2.6.1.3'

# Compatibility API retained for the historical r3.3.4.2.6.1.3 unit tests.
def privacy_violation(text: str):
    return current_privacy_violation(text)

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--input', required=True, type=Path)
    ap.add_argument('--zip', required=True, type=Path)
    a=ap.parse_args()
    evidence=a.input.resolve().parent
    # Canonical profile expects <evidence>/sanitized-summary.  The historical CLI
    # supplies the sanitized-summary directory directly.
    rc,out,side=package(ROOT, REVISION, evidence, '', a.zip, quiet=True)
    if rc != 0: return rc
    print('SANITIZED_PRIVACY_GATE=PASS')
    print('SANITIZED_ZIP=' + str(out))
    print('SANITIZED_ZIP_SHA256=' + hashlib.sha256(out.read_bytes()).hexdigest())
    print('SANITIZED_SHA256_FILE=' + str(side))
    return 0

if __name__=='__main__': raise SystemExit(main())
