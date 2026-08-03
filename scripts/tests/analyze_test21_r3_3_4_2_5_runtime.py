#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, importlib.util, json, re
from pathlib import Path
SERVICE='Lcom/rokid/sprite/aiapp/externalapp/service/CXRLinkService;';MEDIA='Lcom/rokid/sprite/aiapp/externalapp/IMediaStreamService;';STUB='Lcom/rokid/sprite/aiapp/externalapp/IMediaStreamService$Stub;';PROXY='Lcom/rokid/sprite/aiapp/externalapp/IMediaStreamService$Stub$Proxy;'
DOT_SERVICE='com.rokid.sprite.aiapp.externalapp.service.CXRLinkService';DOT_MEDIA='com.rokid.sprite.aiapp.externalapp.IMediaStreamService';DOT_STUB=DOT_MEDIA+'$Stub'

def load_prev(repo):
 p=repo/'scripts/tests/analyze_test21_r3_3_4_2_3_code_origin.py';sp=importlib.util.spec_from_file_location('r33423',p);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def sanitize_origin(s):
 if not s:return 'UNRESOLVED'
 s=re.sub(r'/data/(?:user|user_de)/\d+/[^/]+/','/data/<app>/...',s);s=re.sub(r'/data/app/[^/]+/','/data/app/<install>/',s);return s[:260]
def scan_file(p,origin,prev,repo):
 try:return prev.scan_dex_bytes(p.read_bytes(),origin,prev.load_dex_base(repo).Dex)
 except Exception as e:return ({},[],str(e))
def classdefs(hits,desc):return (hits.get(desc) or {}).get('class_defs') or []
def first(hits,desc,origin):return origin if classdefs(hits,desc) else None

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--repo',required=True);ap.add_argument('--runtime-dir',required=True);ap.add_argument('--root-collection',required=True);ap.add_argument('--output',required=True);a=ap.parse_args()
 repo=Path(a.repo);rt=Path(a.runtime_dir);root=Path(a.root_collection);out=Path(a.output);san=out/'sanitized';priv=out/'private';san.mkdir(parents=True,exist_ok=True);priv.mkdir(parents=True,exist_ok=True);prev=load_prev(repo)
 frida_json=rt/'frida-runtime-private.json';obs=json.loads(frida_json.read_text()) if frida_json.is_file() else {}
 targets=obs.get('targets') or {}; svc_loaded=bool((targets.get(DOT_SERVICE) or {}).get('loaded'));media_loaded=bool((targets.get(DOT_MEDIA) or {}).get('loaded'));stub_loaded=bool((targets.get(DOT_STUB) or {}).get('loaded'))
 svc_rec=targets.get(DOT_SERVICE) or {}; loader=svc_rec.get('loader') or {}; dex_elements=loader.get('dex_elements') or []; loader_kind=loader.get('loader_class') or 'UNRESOLVED'
 binder_fields=sorted(set(svc_rec.get('binder_field_classes') or []))
 evidence=[];svc_origin=None;media_origin=None;stub_origin=None;proxy_origin=None;stub_subclasses=[];onbind=[]
 for p in sorted((rt/'memory-dex').glob('*.dex')):
  origin='MEMORY_DEX:'+p.name;hits,subs,err=scan_file(p,origin,prev,repo);evidence.append({'origin':origin,'sha256':sha(p),'size':p.stat().st_size,'error':err,'hits':hits});stub_subclasses.extend(subs)
  if not svc_origin and classdefs(hits,SERVICE):svc_origin=origin
  if not media_origin and classdefs(hits,MEDIA):media_origin=origin
  if not stub_origin and classdefs(hits,STUB):stub_origin=origin
  if not proxy_origin and classdefs(hits,PROXY):proxy_origin=origin
  for row in classdefs(hits,SERVICE):
   for m in row.get('methods') or []:
    if m.get('name')=='onBind':onbind.append({'origin':origin,'proto':m.get('proto'),'ret':m.get('ret')})
 for p in sorted((rt/'file-backed').glob('*')):
  if not p.is_file():continue
  origin='FILE_BACKED:'+p.name;hits,subs,err=scan_file(p,origin,prev,repo);evidence.append({'origin':origin,'sha256':sha(p),'size':p.stat().st_size,'error':err,'hits':hits});stub_subclasses.extend(subs)
  if not svc_origin and classdefs(hits,SERVICE):svc_origin=origin
  if not media_origin and classdefs(hits,MEDIA):media_origin=origin
  if not stub_origin and classdefs(hits,STUB):stub_origin=origin
  if not proxy_origin and classdefs(hits,PROXY):proxy_origin=origin
  for row in classdefs(hits,SERVICE):
   for m in row.get('methods') or []:
    if m.get('name')=='onBind':onbind.append({'origin':origin,'proto':m.get('proto'),'ret':m.get('ret')})
 exact=svc_origin is not None
 if exact and svc_origin.startswith('MEMORY_DEX:'): kind='IN_MEMORY_DEX'
 elif exact: kind='FILE_BACKED_DEX_OR_APK'
 elif svc_loaded: kind='LOADED_CLASS_ORIGIN_NOT_RECOVERED'
 else: kind='TARGET_CLASS_NOT_OBSERVED_LOADED'
 impl_candidates=sorted(set(str(x.get('class') or x.get('descriptor') or x) for x in stub_subclasses)) if stub_subclasses else []
 impl_exact=exact and bool(onbind) and (stub_origin is not None or bool(impl_candidates))
 if impl_exact: impl_disp='CXRLINKSERVICE_DEFINING_DEX_AND_SERVICE_BINDER_LINEAGE_RECOVERED'
 elif exact: impl_disp='CXRLINKSERVICE_DEFINING_DEX_RECOVERED_BINDER_IMPLEMENTATION_PARTIAL'
 elif svc_loaded: impl_disp='RUNTIME_CLASS_LOADED_BUT_DEFINING_DEX_NOT_RECOVERED'
 else: impl_disp='RUNTIME_TARGET_CLASS_NOT_OBSERVED'
 private={'schema':'rokid.test21-r3.3.4.2.5.private.v1','frida_observation':obs,'dex_evidence':evidence,'stub_subclasses':stub_subclasses,'onbind':onbind,'binder_field_classes':binder_fields}
 (priv/'r3-3-4-2-5-private.json').write_text(json.dumps(private,indent=2,sort_keys=True)+'\n')
 summary={'schema':'rokid.test21-r3.3.4.2.5.sanitized.v1','analysis_pass':True,'cxrlinkservice_runtime_class_loaded':'YES' if svc_loaded else 'NO','imediaservice_runtime_class_loaded':'YES' if media_loaded else 'NO','imediaservice_stub_runtime_class_loaded':'YES' if stub_loaded else 'NO','cxrlinkservice_classloader':loader_kind,'cxrlinkservice_dex_element_count':len(dex_elements),'cxrlinkservice_defining_dex_kind':kind,'cxrlinkservice_defining_dex_origin':svc_origin or 'NOT_RECOVERED','cxrlinkservice_defining_dex_sha256': next((e['sha256'] for e in evidence if e['origin']==svc_origin), 'NONE'),'cxrlinkservice_class_def_confirmed':'YES' if exact else 'NO','imediaservice_interface_origin':media_origin or 'NOT_RECOVERED','imediaservice_stub_origin':stub_origin or 'NOT_RECOVERED','imediaservice_proxy_origin':proxy_origin or 'NOT_RECOVERED','service_side_cxrlinkservice_onbind_count':len(onbind),'live_service_binder_field_classes':binder_fields,'imediaservice_stub_subclass_count':len(impl_candidates),'service_implementation_origin_closure':'YES' if impl_exact else 'NO','service_implementation_disposition':impl_disp,'proof_boundary':'ROOT_ASSISTED_FRIDA_OBSERVATION_AND_EXACT_RECOVERED_DEX_CLASS_DEF_NO_METHOD_REPLACEMENT_NO_PAYLOAD_EXECUTION'}
 (san/'test21-r3-3-4-2-5-summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
 def cv(v):return ','.join(v) if v else 'NONE'
 lines=['TEST21_R3_3_4_2_5_ANALYSIS=PASS','CXRLINKSERVICE_RUNTIME_CLASS_LOADED='+summary['cxrlinkservice_runtime_class_loaded'],'IMEDIASTREAMSERVICE_RUNTIME_CLASS_LOADED='+summary['imediaservice_runtime_class_loaded'],'IMEDIASTREAMSERVICE_STUB_RUNTIME_CLASS_LOADED='+summary['imediaservice_stub_runtime_class_loaded'],'CXRLINKSERVICE_CLASSLOADER='+summary['cxrlinkservice_classloader'],f"CXRLINKSERVICE_DEX_ELEMENT_COUNT={summary['cxrlinkservice_dex_element_count']}",'CXRLINKSERVICE_DEFINING_DEX_KIND='+kind,'CXRLINKSERVICE_DEFINING_DEX_ORIGIN='+summary['cxrlinkservice_defining_dex_origin'],'CXRLINKSERVICE_DEFINING_DEX_SHA256='+summary['cxrlinkservice_defining_dex_sha256'],'CXRLINKSERVICE_CLASS_DEF_CONFIRMED='+summary['cxrlinkservice_class_def_confirmed'],'IMEDIASTREAMSERVICE_INTERFACE_ORIGIN='+summary['imediaservice_interface_origin'],'IMEDIASTREAMSERVICE_STUB_ORIGIN='+summary['imediaservice_stub_origin'],'IMEDIASTREAMSERVICE_PROXY_ORIGIN='+summary['imediaservice_proxy_origin'],f'SERVICE_SIDE_CXRLINKSERVICE_ONBIND_COUNT={len(onbind)}','LIVE_SERVICE_BINDER_FIELD_CLASSES='+cv(binder_fields),f'IMEDIASTREAMSERVICE_STUB_SUBCLASS_COUNT={len(impl_candidates)}','SERVICE_IMPLEMENTATION_ORIGIN_CLOSURE='+summary['service_implementation_origin_closure'],'SERVICE_IMPLEMENTATION_DISPOSITION='+impl_disp,'PAYLOAD_EXECUTION=NONE','METHOD_REPLACEMENT=NONE','BINDER_RETURN_MODIFICATION=NONE','DEVICE_PERSISTENT_MUTATION=NONE','HI_ROKID_FORCE_STOP=NONE','CXR_L_CONNECTION_ATTEMPT=NONE','PHOTO_OPERATION=NONE','AUDIO_OPERATION=NONE']
 (san/'test21-r3-3-4-2-5-summary.txt').write_text('\n'.join(lines)+'\n');print('\n'.join(lines));return 0
if __name__=='__main__':raise SystemExit(main())
