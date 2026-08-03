#!/usr/bin/env python3
# R27.2.5 compatibility shim. Historical implementation is preserved privately.
# TEST21_R3_3_3_1_PCAP_COMPATIBILITY_SHIM=YES
from __future__ import annotations
import argparse, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
CANON=ROOT/"scripts/research/canonical"
if str(CANON) not in sys.path: sys.path.insert(0,str(CANON))
import pcap_parser as _core
# Re-export modules used by historical regression oracles for monkeypatching.
shutil=_core.shutil
subprocess=_core.subprocess
MAGIC=_core.MAGIC
METHODS=_core.METHODS
REVISION='r3.3.3.1'
TARGETS=set(_core.get_profile(REVISION).get("target_packages", []))
clean_path=_core.clean_path
dns_q=_core.dns_q
tls_sni=_core.tls_sni
public_endpoint=_core.public_endpoint
def trailer(data):
    return _core.trailer(data, 96)
def parse_ip(frame, end, linktype):
    return _core.parse_ip(frame, end, linktype, "pcap_linktype_aware")
def parse_pcap(path, uidmap):
    return _core.parse_pcap(Path(path), uidmap, _core.get_profile(REVISION))
def tshark_http(pcap, keylog, frame_pkg, flowmap):
    rows=[]
    rows.extend({"frame_number":frame,"flow_key":None,"package":pkg} for frame,pkg in frame_pkg.items())
    rows.extend({"frame_number":None,"flow_key":key,"package":pkg} for key,pkg in flowmap.items())
    return _core.tshark_http(Path(pcap), Path(keylog) if keylog else None, rows, _core.get_profile(REVISION))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--pcap',required=True)
    ap.add_argument('--uid-map',required=True)
    ap.add_argument('--output',required=True)
    ap.add_argument('--sslkeylog')
    a=ap.parse_args()
    rc, _summary, _lines = _core.parse_revision(
        ROOT, REVISION, Path(a.pcap), Path(a.uid_map), Path(a.output),
        Path(a.sslkeylog) if a.sslkeylog else None, emit_output=True
    )
    return rc
if __name__=='__main__':
    raise SystemExit(main())
