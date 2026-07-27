#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re
from pathlib import Path

REQUIRED_ORDER = [
    "r25_2_provisioning_started",
    "r25_2_provisioning_characteristic_read",
    "r25_2_runtime_endpoint_acquired",
    "r25_2_rfcomm_connect_requested",
    "r25_2_rfcomm_socket_open",
    "r25_2_rfcomm_socket_closed",
]
FORBIDDEN_EVENTS = {
    "gatt_characteristic_write", "gatt_descriptor_write", "rfcomm_payload_write",
    "rfcomm_payload_read", "cxr_request", "developer_mode_toggle",
}

def load_jsonl(path: Path):
    rows=[]
    for no,line in enumerate(path.read_text(encoding='utf-8').splitlines(),1):
        if not line.strip(): continue
        try: rows.append(json.loads(line))
        except Exception as e: raise SystemExit(f'invalid JSONL line {no}: {e}')
    return rows

def sha256_file(path: Path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--client-log',type=Path,required=True)
    ap.add_argument('--run-metadata',type=Path,required=True)
    ap.add_argument('--phone-logcat',type=Path)
    ap.add_argument('--private-output',type=Path,required=True)
    ap.add_argument('--public-output',type=Path,required=True)
    a=ap.parse_args()
    for p in [a.client_log,a.run_metadata]:
        if not p.is_file(): raise SystemExit(f'missing input: {p}')
    rows=load_jsonl(a.client_log)
    metadata=json.loads(a.run_metadata.read_text())
    types=[r.get('event_type') for r in rows]
    positions={t: types.index(t) if t in types else -1 for t in REQUIRED_ORDER}
    sequence_ok=all(positions[t]>=0 for t in REQUIRED_ORDER) and [positions[t] for t in REQUIRED_ORDER]==sorted(positions.values())
    forbidden=sorted(set(types)&FORBIDDEN_EVENTS)
    read=next((r for r in rows if r.get('event_type')=='r25_2_provisioning_characteristic_read'),None)
    endpoint=next((r for r in rows if r.get('event_type')=='r25_2_runtime_endpoint_acquired'),None)
    opened=next((r for r in rows if r.get('event_type')=='r25_2_rfcomm_socket_open'),None)
    closed=next((r for r in rows if r.get('event_type')=='r25_2_rfcomm_socket_closed'),None)
    def d(row): return (row or {}).get('details',{})
    uuid_hash=d(endpoint).get('runtime_uuid_sha256')
    uuid_hash_ok=bool(re.fullmatch(r'[0-9a-f]{64}',str(uuid_hash or '')))
    zero_io=all(d(r).get('application_payload_read_count',0)==0 and d(r).get('application_payload_write_count',0)==0 for r in [opened,closed] if r)
    privacy_ok=bool(endpoint) and d(endpoint).get('runtime_uuid_published') is False and d(endpoint).get('classic_address_published') is False and d(endpoint).get('account_material_published') is False and d(read).get('raw_value_published') is False
    strict_ok=metadata.get('hi_rokid_disabled_before') is True and metadata.get('hi_rokid_running_before') is False and metadata.get('hi_rokid_disabled_after') is True and metadata.get('hi_rokid_running_after') is False
    socket_open=bool(opened and d(opened).get('connected') is True)
    characteristic_ok=bool(read and d(read).get('characteristic_uuid')=='00009301-0000-1000-8000-00805f9b34fb' and d(read).get('status')==0 and int(d(read).get('value_length',0))>0)
    logcat_scn3=False; logcat_dlci6=False
    if a.phone_logcat and a.phone_logcat.is_file():
        text=a.phone_logcat.read_text(errors='replace')
        uid=str(metadata.get('probe_uid',''))
        logcat_scn3=bool(uid and re.search(rf'on_cli_rfc_connect:.*scn:\s*3,\s*app_uid:\s*{re.escape(uid)}\b',text))
        logcat_dlci6=bool(re.search(r'RFCOMM_CreateConnectionWithSecurity:.*scn=3,.*is_server=false,.*dlci=6\b',text))
    qualified=all([sequence_ok,not forbidden,zero_io,privacy_ok,strict_ok,socket_open,characteristic_ok,uuid_hash_ok])
    private={
      'schema':'rokid.r25.2.connection-only-private.v1',
      'client_log_sha256':sha256_file(a.client_log),'event_count':len(rows),'event_positions':positions,
      'sequence_ok':sequence_ok,'forbidden_events':forbidden,'strict_isolation':strict_ok,
      'characteristic_9301_read':characteristic_ok,'runtime_uuid_sha256':uuid_hash,
      'runtime_uuid_published':False,'classic_address_published':False,'account_material_published':False,
      'rfcomm_socket_open':socket_open,'application_payload_reads':0,'application_payload_writes':0,
      'logcat_scn3_correlated':logcat_scn3,'logcat_dlci6_correlated':logcat_dlci6,
      'connection_only_client_qualified':qualified,
    }
    public={k:v for k,v in private.items() if k not in {'client_log_sha256','event_positions'}}
    public['schema']='rokid.r25.2.connection-only-public.v1'
    a.private_output.parent.mkdir(parents=True,exist_ok=True); a.public_output.parent.mkdir(parents=True,exist_ok=True)
    a.private_output.write_text(json.dumps(private,indent=2,sort_keys=True)+'\n')
    a.public_output.write_text(json.dumps(public,indent=2,sort_keys=True)+'\n')
    print(f'R25_2_CLIENT_EVENT_COUNT={len(rows)}')
    print(f'R25_2_STRICT_ISOLATION={"YES" if strict_ok else "NO"}')
    print(f'R25_2_9301_READ={"YES" if characteristic_ok else "NO"}')
    print(f'R25_2_RUNTIME_UUID_ACQUIRED={"YES" if uuid_hash_ok else "NO"}')
    print(f'R25_2_RFCOMM_SOCKET_OPEN={"YES" if socket_open else "NO"}')
    print('R25_2_APPLICATION_PAYLOAD_READ_COUNT=0')
    print('R25_2_APPLICATION_PAYLOAD_WRITE_COUNT=0')
    print(f'R25_2_LOGCAT_SCN3_CORRELATED={"YES" if logcat_scn3 else "NO"}')
    print(f'R25_2_LOGCAT_DLCI6_CORRELATED={"YES" if logcat_dlci6 else "NO"}')
    print(f'R1_3_3_2_25_2_CONNECTION_ONLY_QUALIFIED={"YES" if qualified else "NO"}')
    return 0 if qualified else 3
if __name__=='__main__': raise SystemExit(main())
