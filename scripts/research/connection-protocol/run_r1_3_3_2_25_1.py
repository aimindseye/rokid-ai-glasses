#!/usr/bin/env python3
from __future__ import annotations
import argparse,subprocess,sys
from pathlib import Path

def call(cmd:list[str])->None:
    print('+ '+' '.join(cmd),flush=True); subprocess.run(cmd,check=True)

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--evidence-zip',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--expected-sha256')
    ap.add_argument('--soft-client-log',type=Path)
    ap.add_argument('--strict-client-log',type=Path)
    a=ap.parse_args(); out=a.output.resolve()
    if str(out) in {'/','.'}: raise SystemExit('unsafe output')
    here=Path(__file__).resolve().parent; py=sys.executable
    (out/'analysis').mkdir(parents=True,exist_ok=True); (out/'publication').mkdir(parents=True,exist_ok=True)
    cmd=[py,str(here/'analyze_r25_1_stock_session.py'),'--evidence-zip',str(a.evidence_zip),'--private-output',str(out/'analysis/r25.1-stock-session-private.json'),'--public-output',str(out/'publication/r25.1-stock-session-closure.json')]
    if a.expected_sha256: cmd += ['--expected-sha256',a.expected_sha256]
    if a.soft_client_log: cmd += ['--soft-client-log',str(a.soft_client_log)]
    if a.strict_client_log: cmd += ['--strict-client-log',str(a.strict_client_log)]
    call(cmd)
    call([py,str(here/'verify_r25_1_publication.py'),'--publication',str(out/'publication/r25.1-stock-session-closure.json')])
    call([py,str(here/'validate_r25_1_run.py'),'--run',str(out)])
    call([py,str(here/'finalize_r25_1.py'),'--run',str(out)])
    print('R1_3_3_2_25_1_ACCEPTANCE=PASS_STOCK_SESSION_ESTABLISHMENT_CLOSED')
    return 0
if __name__=='__main__': raise SystemExit(main())
