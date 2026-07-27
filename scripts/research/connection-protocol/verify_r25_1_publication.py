#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
from pathlib import Path

MAC_RE = re.compile(r"\b[0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5}\b")
UUID_RE = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)
ALLOWED_UUIDS = {"00009301-0000-1000-8000-00805f9b34fb"}

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--publication', type=Path, required=True)
    args=ap.parse_args()
    data=json.loads(args.publication.read_text(encoding='utf-8'))
    text=args.publication.read_text(encoding='utf-8')
    if MAC_RE.search(text): raise SystemExit('public publication contains Bluetooth address')
    def contains_raw_base64(value):
        if isinstance(value, dict): return any(contains_raw_base64(v) for v in value.values())
        if isinstance(value, list): return any(contains_raw_base64(v) for v in value)
        return isinstance(value, str) and len(value) >= 40 and any(ch in value for ch in '+/=')
    if contains_raw_base64(data): raise SystemExit('public publication contains base64-like material')
    unexpected={u.lower() for u in UUID_RE.findall(text)}-ALLOWED_UUIDS
    if unexpected: raise SystemExit(f'public publication contains unexpected raw UUIDs: {sorted(unexpected)}')
    closure=data.get('closure',{})
    required={
      'ble_to_rfcomm_bootstrap_attributed': True,
      'sdp_service_channel_attributed': True,
      'rfcomm_scn_dlci_reconstructed': True,
      'stock_session_establishment_sequence_closed': True,
      'application_message_framing_closed': False,
      'session_authentication_semantics_closed': False,
      'independent_client_rfcomm_session_implemented': False,
      'developer_mode_remote_invocation_closed': False,
    }
    for key,want in required.items():
        if closure.get(key) is not want: raise SystemExit(f'closure mismatch {key}')
    if data.get('rfcomm_session',{}).get('sdp_server_channel') != 3: raise SystemExit('SCN mismatch')
    if data.get('rfcomm_session',{}).get('dlci') != 6: raise SystemExit('DLCI mismatch')
    if data.get('rfcomm_session',{}).get('mtu') != 990: raise SystemExit('MTU mismatch')
    safety=data.get('public_safety',{})
    if any(safety.get(k) is not False for k in ['raw_hci_published','bluetooth_address_published','runtime_uuid_published','account_material_published']):
        raise SystemExit('public safety flags mismatch')
    print('R1_3_3_2_25_1_PUBLICATION_VERIFY=PASS')
    return 0
if __name__=='__main__': raise SystemExit(main())
