#!/usr/bin/env python3
"""Classify PCAPdroid CSV destinations for the Test 19 local-network privacy gate."""
from __future__ import annotations
import argparse,csv,ipaddress,json,re
from pathlib import Path

HOST_KEYS=('remote_host','dst_name','host','domain','server_name','sni')
IP_KEYS=('remote_ip','dst_ip','destination_ip','ip')
LOCAL_SUFFIXES=('.local','.lan','.home','.internal')

def is_local_ip(value:str)->bool:
    try:
        ip=ipaddress.ip_address(value.strip().split('%')[0])
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified
    except ValueError:return False

def analyze(path:Path)->dict:
    with path.open(newline='',encoding='utf-8-sig') as handle:
        rows=list(csv.DictReader(handle))
    public=[]; local=[]; unknown=[]
    for i,row in enumerate(rows,2):
        host=next((str(row.get(k,'')).strip() for k in HOST_KEYS if str(row.get(k,'')).strip()),'')
        ip=next((str(row.get(k,'')).strip() for k in IP_KEYS if str(row.get(k,'')).strip()),'')
        value=host or ip
        rec={'line':i,'host':host,'ip':ip}
        if ip and is_local_ip(ip): local.append(rec)
        elif host and (host.lower() in {'localhost'} or host.lower().endswith(LOCAL_SUFFIXES)): local.append(rec)
        elif value: public.append(rec)
        else: unknown.append(rec)
    return {'schema':'rokid.test19-r1.network-privacy.v1','row_count':len(rows),'local_destination_count':len(local),'public_destination_count':len(public),'unknown_destination_count':len(unknown),'public_destinations':public,'gate':'PASS' if rows and not public else 'FAIL'}

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--csv',required=True); ap.add_argument('--output',required=True); a=ap.parse_args()
    result=analyze(Path(a.csv)); Path(a.output).write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(f"TEST19_R1_LOCAL_NETWORK_PRIVACY_GATE={result['gate']}")
    print(f"TEST19_R1_PUBLIC_DESTINATION_COUNT={result['public_destination_count']}")
    return 0 if result['gate']=='PASS' else 4
if __name__=='__main__': raise SystemExit(main())
