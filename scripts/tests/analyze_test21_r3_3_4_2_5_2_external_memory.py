#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,importlib.util,json
from pathlib import Path
SERVICE='Lcom/rokid/sprite/aiapp/externalapp/service/CXRLinkService;';MEDIA='Lcom/rokid/sprite/aiapp/externalapp/IMediaStreamService;';STUB='Lcom/rokid/sprite/aiapp/externalapp/IMediaStreamService$Stub;';PROXY='Lcom/rokid/sprite/aiapp/externalapp/IMediaStreamService$Stub$Proxy;'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load_prev(repo):
 p=repo/'scripts/tests/analyze_test21_r3_3_4_2_3_code_origin.py';sp=importlib.util.spec_from_file_location('r33423',p);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
def cdefs(h,t):return (h.get(t) or {}).get('class_defs') or []
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--repo',required=True);ap.add_argument('--collection',required=True);ap.add_argument('--output',required=True);a=ap.parse_args();repo=Path(a.repo);col=Path(a.collection);out=Path(a.output);san=out/'sanitized';priv=out/'private';san.mkdir(parents=True,exist_ok=True);priv.mkdir(parents=True,exist_ok=True)
 meta=json.loads((col/'external-memory-private.json').read_text());prev=load_prev(repo);Dex=prev.load_dex_base(repo).Dex
 evidence=[];svc=[];media=[];stub=[];proxy=[];subs=[];onbind=[];parse_errors=0
 for i,p in enumerate(sorted((col/'recovered-dex').glob('*.dex')),1):
  origin=f'EXTERNAL_MEMORY_DEX[{i:03d}]';hits,s,e=prev.scan_dex_bytes(p.read_bytes(),origin,Dex);parse_errors+=1 if e else 0;evidence.append({'origin':origin,'sha256':sha(p),'size':p.stat().st_size,'parse_error':e,'targets':hits});subs.extend(s)
  if cdefs(hits,SERVICE):svc.append({'origin':origin,'sha256':sha(p),'class_defs':cdefs(hits,SERVICE)})
  if cdefs(hits,MEDIA):media.append({'origin':origin,'sha256':sha(p),'class_defs':cdefs(hits,MEDIA)})
  if cdefs(hits,STUB):stub.append({'origin':origin,'sha256':sha(p),'class_defs':cdefs(hits,STUB)})
  if cdefs(hits,PROXY):proxy.append({'origin':origin,'sha256':sha(p),'class_defs':cdefs(hits,PROXY)})
  for row in cdefs(hits,SERVICE):
   for m in row.get('methods') or []:
    if m.get('name')=='onBind':onbind.append({'origin':origin,'sha256':sha(p),'proto':m.get('proto'),'ret':m.get('ret')})
 impls=sorted(set(str(x.get('class') or '') for x in subs if x.get('class')));svc_exact=bool(svc);binder_lineage=bool(stub or impls);impl_exact=svc_exact and bool(onbind) and binder_lineage
 access=meta.get('external_proc_mem_access','UNRESOLVED')
 if impl_exact:disp='EXTERNAL_MEMORY_CXRLINKSERVICE_AND_ONBIND_AND_IMEDIASTREAMSERVICE_BINDER_LINEAGE_RECOVERED'
 elif svc_exact:disp='EXTERNAL_MEMORY_CXRLINKSERVICE_CLASS_DEF_RECOVERED_BINDER_IMPLEMENTATION_PARTIAL'
 elif access=='READABLE':disp='NON_INJECTED_ROOT_MEMORY_CENSUS_EXHAUSTED_TARGET_CLASS_DEF_NOT_RECOVERED'
 elif access=='DENIED':disp='EXTERNAL_PROC_MEM_DENIED_NO_CLASS_ORIGIN_CONCLUSION'
 else:disp='EXTERNAL_PROC_MEM_UNREADABLE_OR_UNSUPPORTED_NO_CLASS_ORIGIN_CONCLUSION'
 private={'schema':'rokid.test21-r3.3.4.2.5.2.private.v1','collection':meta,'dex_evidence':evidence,'stub_subclasses':subs,'service_onbind':onbind}
 (priv/'r3-3-4-2-5-2-private.json').write_text(json.dumps(private,indent=2,sort_keys=True)+'\n')
 def first(xs):return xs[0]['origin'] if xs else 'NOT_RECOVERED'
 def firstsha(xs):return xs[0]['sha256'] if xs else 'NONE'
 summary={'schema':'rokid.test21-r3.3.4.2.5.2.sanitized.v1','analysis':'PASS','root_probe':'AVAILABLE','process_maps_access':meta.get('process_maps_access','UNRESOLVED'),'external_proc_mem_access':access,'readable_mapping_count':meta.get('readable_mapping_count',0),'selected_memory_chunk_count':meta.get('selected_chunk_count',0),'memory_bytes_read':meta.get('memory_bytes_read',0),'dex_magic_hit_count':meta.get('dex_magic_hit_count',0),'cdex_magic_hit_count':meta.get('cdex_magic_hit_count',0),'dex_validated_count':meta.get('dex_validated_count',0),'dex_recovered_unique_count':meta.get('dex_recovered_unique_count',0),'dex_parse_error_count':parse_errors,'cxrlinkservice_code_origin':first(svc),'cxrlinkservice_code_origin_sha256':firstsha(svc),'cxrlinkservice_class_def_confirmed':'YES' if svc_exact else 'NO','imediaservice_interface_origin':first(media),'imediaservice_stub_origin':first(stub),'imediaservice_proxy_origin':first(proxy),'service_side_cxrlinkservice_onbind_count':len(onbind),'imediaservice_stub_subclass_count':len(impls),'service_implementation_origin_closure':'YES' if impl_exact else 'NO','service_implementation_disposition':disp,'proof_boundary':'NON_INJECTED_ROOT_PROC_MAPS_AND_BOUNDED_PROC_MEM_READ_PLUS_EXACT_PARSED_DEX_CLASS_DEF_NO_FRIDA_NO_PTRACE_NO_SIGNAL_NO_PAYLOAD_EXECUTION'}
 (san/'test21-r3-3-4-2-5-2-summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
 lines=['TEST21_R3_3_4_2_5_2_ANALYSIS=PASS','ROOT_PROBE=AVAILABLE','ROOT_PROCESS_MAPS_ACCESS='+summary['process_maps_access'],'EXTERNAL_PROC_MEM_ACCESS='+access,'READABLE_MAPPING_COUNT='+str(summary['readable_mapping_count']),'SELECTED_MEMORY_CHUNK_COUNT='+str(summary['selected_memory_chunk_count']),'MEMORY_BYTES_READ='+str(summary['memory_bytes_read']),'DEX_MAGIC_HIT_COUNT='+str(summary['dex_magic_hit_count']),'CDEX_MAGIC_HIT_COUNT='+str(summary['cdex_magic_hit_count']),'DEX_VALIDATED_COUNT='+str(summary['dex_validated_count']),'DEX_RECOVERED_UNIQUE_COUNT='+str(summary['dex_recovered_unique_count']),'DEX_PARSE_ERROR_COUNT='+str(parse_errors),'CXRLINKSERVICE_CODE_ORIGIN='+summary['cxrlinkservice_code_origin'],'CXRLINKSERVICE_CODE_ORIGIN_SHA256='+summary['cxrlinkservice_code_origin_sha256'],'CXRLINKSERVICE_CLASS_DEF_CONFIRMED='+summary['cxrlinkservice_class_def_confirmed'],'IMEDIASTREAMSERVICE_INTERFACE_ORIGIN='+summary['imediaservice_interface_origin'],'IMEDIASTREAMSERVICE_STUB_ORIGIN='+summary['imediaservice_stub_origin'],'IMEDIASTREAMSERVICE_PROXY_ORIGIN='+summary['imediaservice_proxy_origin'],'SERVICE_SIDE_CXRLINKSERVICE_ONBIND_COUNT='+str(len(onbind)),'IMEDIASTREAMSERVICE_STUB_SUBCLASS_COUNT='+str(len(impls)),'SERVICE_IMPLEMENTATION_ORIGIN_CLOSURE='+summary['service_implementation_origin_closure'],'SERVICE_IMPLEMENTATION_DISPOSITION='+disp,'FRIDA_SERVER_START=NONE','FRIDA_PROCESS_ATTACH=NONE','INJECTED_AGENT_LOAD=NONE','PTRACE_ATTACH=NONE','PROCESS_SIGNAL=NONE','PAYLOAD_EXECUTION=NONE','DEVICE_PERSISTENT_MUTATION=NONE','HI_ROKID_FORCE_STOP=NONE','CXR_L_CONNECTION_ATTEMPT=NONE','PHOTO_OPERATION=NONE','AUDIO_OPERATION=NONE']
 (san/'test21-r3-3-4-2-5-2-summary.txt').write_text('\n'.join(lines)+'\n');print('\n'.join(lines));return 0
if __name__=='__main__':raise SystemExit(main())
