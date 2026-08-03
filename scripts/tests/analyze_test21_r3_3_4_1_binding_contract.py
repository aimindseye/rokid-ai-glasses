#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,re,sys
from pathlib import Path
HI='com.rokid.sprite.global.aiapp';CUSTOM='org.aimindseye.rokid.cxrphotoqualification'
SERVICE='com.rokid.sprite.aiapp.externalapp.service.CXRLinkService';PROVIDER='com.rokid.sprite.aiapp.external.CXRLinkProvider'
COMPONENT=HI+'/'+SERVICE

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return p.read_text(errors='replace') if p.is_file() else ''
def events(p):
    out=[]
    for l in read(p).splitlines():
      try:
        x=json.loads(l)
        if isinstance(x,dict):out.append(x)
      except Exception:pass
    return out
def boolish(v):return v is True or str(v).lower() in ('1','true','yes')
def verify_event_contract(raw):
    pre=events(raw/'pre-force-events-private.jsonl');fin=events(raw/'final-events-private.jsonl')
    a=[e for e in pre if e.get('event_type')=='authorization_result']
    if not a or not boolish((a[-1].get('details') or {}).get('token_present')):raise ValueError('authorization not proven')
    forbidden={'connection_attempt_started','callback_cxrl_connected','callback_glass_bt_connected','service_status_result','photo_ready','operator_gate_prerequisite_ready'}
    if any(e.get('event_type') in forbidden for e in pre):raise ValueError('connection existed before force-stop')
    if not any(e.get('event_type')=='connection_attempt_started' for e in fin):raise ValueError('connection attempt not proven')
    if not any(e.get('event_type')=='callback_cxrl_connected' and boolish((e.get('details') or {}).get('connected')) for e in fin):raise ValueError('CXR-L connection callback not proven')
    if not any(e.get('event_type')=='service_status_result' and boolish((e.get('details') or {}).get('status_success')) for e in fin):raise ValueError('service status success not proven')
    for e in fin:
      n=str(e.get('event_type',''))
      if re.search(r'(?i)(take[_ -]?photo|photo_request|capture_dispatch|audio.*(?:start|stop|stream)|(?:start|stop).*audio)',n):raise ValueError('media event detected')

def package_uid(text):
    for pat in (r'(?m)^\s*userId=(\d+)\s*$',r'(?m)^\s*uid=(\d+)\s*$'):
      m=re.search(pat,text)
      if m:return int(m.group(1))
    return None
def uid_token(uid):
    if uid is None:return None
    appid=uid%100000;user=uid//100000
    if appid>=10000:return f'u{user}a{appid-10000}'
    return f'u{user}s{appid}'

def service_evidence(raw):
    names=['at-respawn-activity-services-global-private.txt','at-respawn-hi-services-private.txt','at-respawn-cxrlinkservice-private.txt','collector-final-activity-services-global-private.txt','collector-final-hi-services-private.txt','collector-final-cxrlinkservice-private.txt','binding-contract-samples-private.txt']
    text='\n'.join(read(raw/n) for n in names)
    # Retain only blocks around the exact service for semantic checks.
    lines=text.splitlines();idx=[i for i,l in enumerate(lines) if SERVICE in l or COMPONENT in l]
    chunks=[]
    for i in idx:chunks.extend(lines[max(0,i-12):min(len(lines),i+36)])
    block='\n'.join(chunks) if chunks else text
    return text,block

def parse_intent(block):
    candidates=[]
    for m in re.finditer(r'intent=\{([^\n}]*)\}',block,re.I):
      body=m.group(1)
      if SERVICE in body or COMPONENT in body:candidates.append(body)
    if not candidates:
      for l in block.splitlines():
        if SERVICE in l and ('act=' in l or 'cmp=' in l or 'pkg=' in l):candidates.append(l)
    body=candidates[0] if candidates else ''
    def one(p):
      m=re.search(p,body);return m.group(1) if m else None
    action=one(r'\bact=([^\s}]+)');component=one(r'\bcmp=([^\s}]+)');pkg=one(r'\bpkg=([^\s}]+)');flags=one(r'\bflg=([^\s}]+)')
    if component and component.startswith(HI+'/.'):component=HI+'/'+HI+component[len(HI)+1:]
    return {'raw_present':bool(body),'action':action,'component':component,'package':pkg,'flags':flags,'explicit_component':component==COMPONENT}

def descriptor_from_runtime(block):
    pats=[r'(?i)interfaceDescriptor\s*[=:]\s*([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*){2,})',r'(?i)\bdescriptor\s*[=:]\s*([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*){2,})',r'(?i)\bmDescriptor\s*[=:]\s*([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*){2,})']
    vals=[]
    for p in pats:vals+=re.findall(p,block)
    vals=[v for v in vals if 'rokid' in v.lower() or 'cxr' in v.lower()]
    return sorted(set(vals))
def binder_handle(block):
    return bool(re.search(r'(?i)\bbinder\s*=\s*(?:android\.os\.)?(?:BinderProxy|Binder)?@?[0-9a-f]+',block))
def binding_records(block):
    return bool(re.search(r'\b(?:IntentBindRecord|AppBindRecord|ConnectionRecord)\b',block))
def caller_evidence(block,custom_uid):
    token=uid_token(custom_uid);pkg=CUSTOM in block;tok=bool(token and token in block)
    ls=block.splitlines();connection=False;appbind=False
    for i,l in enumerate(ls):
      if 'ConnectionRecord' in l or 'AppBindRecord' in l:
        window='\n'.join(ls[max(0,i-3):min(len(ls),i+4)])
        hit=(CUSTOM in window) or bool(token and token in window)
        if 'ConnectionRecord' in l and hit:connection=True
        if 'AppBindRecord' in l and hit:appbind=True
    exact = connection or appbind
    return {'package_seen':pkg,'uid':custom_uid,'uid_token':token,'uid_token_seen':tok,'connection_record_match':connection,'app_bind_record_match':appbind,'exact_custom_binding_client':exact}

def apk_census(raw):
    p=raw/'apk-string-census-private.json'
    if not p.is_file():return {'available':False,'binder_interface_descriptor_candidates':[],'intent_action_string_candidates':[]}
    try:
      x=json.loads(p.read_text());return {'available':True,'binder_interface_descriptor_candidates':x.get('binder_interface_descriptor_candidates') or [],'intent_action_string_candidates':x.get('intent_action_string_candidates') or []}
    except Exception:return {'available':False,'binder_interface_descriptor_candidates':[],'intent_action_string_candidates':[]}

def activation_log(raw):
    text=read(raw/'activity-manager-private.txt')+'\n'+read(raw/'activity-events-private.txt')
    return any(SERVICE in line and ('Start proc' in line or 'am_proc_start' in line) for line in text.splitlines())

def disposition(resp,bound,caller,intent,activation):
    if not resp:return 'NO_HI_ROKID_RESPAWN'
    if not activation:return 'RESPAWN_WITHOUT_EXACT_CXRLINKSERVICE_START_REASON'
    if bound and caller and intent.get('explicit_component'):return 'EXACT_CUSTOM_TO_CXRLINKSERVICE_BOUND_DEPENDENCY'
    if bound and intent.get('explicit_component') and not caller:return 'EXACT_CXRLINKSERVICE_BOUND_MECHANISM_CALLER_UNRESOLVED'
    if intent.get('explicit_component'):return 'EXACT_CXRLINKSERVICE_INTENT_COMPONENT_BINDING_MECHANISM_UNRESOLVED'
    return 'CXRLINKSERVICE_PROCESS_START_PROVEN_BINDING_CONTRACT_UNRESOLVED'

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--evidence',required=True);a=ap.parse_args();ev=Path(a.evidence).resolve();raw=ev/'raw';san=ev/'sanitized';san.mkdir(parents=True,exist_ok=True)
    try:
      verify_event_contract(raw)
      coll=json.loads((raw/'binding-contract-collector-summary-private.json').read_text());resp=coll.get('first_hi_respawn_host_epoch_ms') is not None
      restored=read(raw/'state-restored.txt')
      if 'OPERATOR_HI_ROKID_RECOVERY=PASS' not in restored:raise ValueError('Hi Rokid restoration not proven')
      _,block=service_evidence(raw);cuid=package_uid(read(raw/'baseline-custom-package-private.txt')+'\n'+read(raw/'at-respawn-custom-package-private.txt'))
      caller=caller_evidence(block,cuid);bound=binding_records(block);intent=parse_intent(block);descs=descriptor_from_runtime(block);handle=binder_handle(block);static=apk_census(raw);activation=activation_log(raw)
      if len(descs)==1:bdisp='RUNTIME_INTERFACE_DESCRIPTOR_EXACT';bdesc=descs[0]
      elif len(descs)>1:bdisp='MULTIPLE_RUNTIME_INTERFACE_DESCRIPTORS_UNRESOLVED';bdesc=None
      elif len(static['binder_interface_descriptor_candidates'])==1:bdisp='STATIC_SINGLE_CANDIDATE_ONLY_NOT_RUNTIME_PROVEN';bdesc=None
      elif len(static['binder_interface_descriptor_candidates'])>1:bdisp='STATIC_MULTIPLE_CANDIDATES_UNRESOLVED';bdesc=None
      else:bdisp='INTERFACE_DESCRIPTOR_UNRESOLVED';bdesc=None
      disp=disposition(resp,bound,caller['exact_custom_binding_client'],intent,activation)
      exact_dep=disp=='EXACT_CUSTOM_TO_CXRLINKSERVICE_BOUND_DEPENDENCY'
      action= intent['action'] or 'NONE'
      evidence_hashes={}
      for n in ['activity-manager-private.txt','activity-events-private.txt','at-respawn-activity-services-global-private.txt','at-respawn-hi-services-private.txt','at-respawn-cxrlinkservice-private.txt','binding-contract-samples-private.txt','apk-string-census-private.json']:
        p=raw/n
        if p.is_file():evidence_hashes[n]=sha(p)
      result={'schema':'rokid.test21-r3-3-4-1.binding-contract.v1','analysis':'PASS','hi_respawn_observed':resp,'exact_cxrlinkservice_process_start_reason':activation,'bound_service_runtime_evidence':bound,'binding_caller':caller,'intent_contract':intent,'binder_handle_runtime_evidence':handle,'runtime_interface_descriptors':descs,'binder_interface_descriptor':bdesc,'binder_interface_disposition':bdisp,'static_apk_census':{'available':static['available'],'binder_interface_descriptor_candidates':static['binder_interface_descriptor_candidates'],'intent_action_string_candidates':static['intent_action_string_candidates']},'dependency_disposition':disp,'dependency_closure_exact':exact_dep,'proof_boundary':'ANDROID_RUNTIME_BINDING_RECORDS_AND_STATIC_STRING_CENSUS_NOT_LIBRARY_INTERNAL_CALLSTACK','private_evidence_sha256':evidence_hashes,'safety':{'photo_operation':'NONE','audio_operation':'NONE','network_capture':'NONE','pcapdroid_operation':'NONE'}}
      jp=san/'test21-r3-3-4-1-summary.json';jp.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
      fields=[
       ('TEST21_R3_3_4_1_ANALYSIS','PASS'),('HI_ROKID_RESPAWN_OBSERVED','YES' if resp else 'NO'),('EXACT_CXRLINKSERVICE_PROCESS_START_REASON','YES' if activation else 'NO'),
       ('BOUND_SERVICE_RUNTIME_EVIDENCE','YES' if bound else 'NO'),('BINDING_CALLER_PACKAGE',CUSTOM if caller['exact_custom_binding_client'] else 'UNRESOLVED'),('BINDING_CALLER_UID',cuid if cuid is not None else 'UNRESOLVED'),('BINDING_CALLER_UID_TOKEN',caller['uid_token'] or 'UNRESOLVED'),
       ('INTENT_EXPLICIT_COMPONENT','YES' if intent['explicit_component'] else 'NO'),('INTENT_COMPONENT',intent['component'] or 'UNRESOLVED'),('INTENT_ACTION',action),('INTENT_PACKAGE',intent['package'] or 'NONE'),('INTENT_FLAGS',intent['flags'] or 'NONE'),
       ('BINDER_HANDLE_RUNTIME_EVIDENCE','YES' if handle else 'NO'),('BINDER_INTERFACE_DESCRIPTOR',bdesc or 'UNRESOLVED'),('BINDER_INTERFACE_DISPOSITION',bdisp),('STATIC_BINDER_DESCRIPTOR_CANDIDATE_COUNT',len(static['binder_interface_descriptor_candidates'])),
       ('DEPENDENCY_DISPOSITION',disp),('DEPENDENCY_CLOSURE_EXACT','YES' if exact_dep else 'NO'),('PROOF_BOUNDARY',result['proof_boundary']),('PRIVATE_EVIDENCE_HASH_COUNT',len(evidence_hashes)),('PCAPDROID_OPERATION','NONE'),('NETWORK_CAPTURE','NONE'),('PHOTO_OPERATION','NONE'),('AUDIO_OPERATION','NONE'),('HI_ROKID_RESTORATION','PASS')]
      tp=san/'test21-r3-3-4-1-summary.txt';tp.write_text('\n'.join(f'{k}={v}' for k,v in fields)+'\n')
      (san/'SHA256SUMS.txt').write_text(f'{sha(jp)}  {jp.name}\n{sha(tp)}  {tp.name}\n')
      for k,v in fields:print(f'{k}={v}')
      return 0
    except Exception as e:
      print('ERROR: '+str(e),file=sys.stderr);print('TEST21_R3_3_4_1_ANALYSIS=FAIL');return 1
if __name__=='__main__':raise SystemExit(main())
