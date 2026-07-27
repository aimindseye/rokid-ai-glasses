#!/usr/bin/env python3
import argparse,json,re
from pathlib import Path

def main():
 p=argparse.ArgumentParser(); p.add_argument('--publication',type=Path,required=True); a=p.parse_args()
 data=json.loads(a.publication.read_text()); text=a.publication.read_text()
 assert data['schema']=='rokid.r25.2.connection-only-public.v1'
 assert data.get('runtime_uuid_published') is False
 assert data.get('classic_address_published') is False
 assert data.get('account_material_published') is False
 assert data.get('application_payload_reads')==0 and data.get('application_payload_writes')==0
 forbidden=[r'(?i)\b[0-9a-f]{2}(?::[0-9a-f]{2}){5}\b',r'(?i)\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b']
 # Allow the schema's fixed public 0x9301 UUID only if ever added; current publication contains no UUIDs.
 for pattern in forbidden:
  if re.search(pattern,text): raise SystemExit('raw endpoint value in publication')
 print('R1_3_3_2_25_2_PUBLICATION_VERIFY=PASS')
if __name__=='__main__': main()
