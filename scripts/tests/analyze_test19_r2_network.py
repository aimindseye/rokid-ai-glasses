#!/usr/bin/env python3
# R27.2.8 FINAL compatibility shim. Historical implementation is preserved privately.
# TEST19_R2_NETWORK_ANALYZER_COMPATIBILITY_SHIM=YES
from __future__ import annotations
import argparse, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
CANON=ROOT/"scripts/research/canonical"
if str(CANON) not in sys.path: sys.path.insert(0,str(CANON))
import network_privacy_analyzer as _core
CUSTOM_PACKAGE=_core.CUSTOM_PACKAGE
HI_ROKID_PACKAGE=_core.HI_ROKID_PACKAGE
APP_KEYS=_core.APP_KEYS
HOST_KEYS=_core.HOST_KEYS
IP_KEYS=_core.IP_KEYS
LOCAL_SUFFIXES=_core.LOCAL_SUFFIXES
first=_core.first
local_destination=_core.local_destination
app_scope=_core.app_scope
analyze=_core.analyze_r2
REVISION="test19-r2"
def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--csv',required=True); ap.add_argument('--output',required=True); a=ap.parse_args()
    rc,_result,_lines=_core.analyze_revision(ROOT,REVISION,Path(a.csv),Path(a.output),emit_output=True)
    return rc
if __name__=='__main__': raise SystemExit(main())
