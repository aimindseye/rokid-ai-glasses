#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--run',type=Path,required=True); args=ap.parse_args()
    priv=json.loads((args.run/'analysis/r25.1-stock-session-private.json').read_text())
    pub=json.loads((args.run/'publication/r25.1-stock-session-closure.json').read_text())
    if priv['source']['sha256'] != pub['source_archive_sha256']: raise SystemExit('source hash mismatch')
    if priv['rfcomm_session']['sdp_server_channel'] != 3 or priv['rfcomm_session']['dlci'] != 6: raise SystemExit('channel mismatch')
    if priv['fixed_uuid_path']['bluetooth_socket_attempts'] != 18: raise SystemExit('fixed attempt count mismatch')
    if priv['fixed_uuid_path']['sdp_failure_scn_zero_count'] != 18: raise SystemExit('fixed failure count mismatch')
    c=priv['closure']
    if not c['stock_session_establishment_sequence_closed']: raise SystemExit('establishment not closed')
    if c['application_message_framing_closed'] or c['developer_mode_remote_invocation_closed']: raise SystemExit('overclaim')
    print('R25_1_STOCK_SESSION_ESTABLISHMENT_CLOSED=YES')
    print('R25_1_APPLICATION_FRAMING_CLOSED=NO')
    print('R25_1_DEVELOPER_MODE_REMOTE_INVOCATION_CLOSED=NO')
    print('R1_3_3_2_25_1_RUN_VALIDATION=PASS')
    return 0
if __name__=='__main__': raise SystemExit(main())
