#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,re,sys
from pathlib import Path
HI='com.rokid.sprite.global.aiapp';CUSTOM='org.aimindseye.rokid.cxrphotoqualification'
CXR_SERVICE='com.rokid.sprite.aiapp.externalapp.service.CXRLinkService';CXR_PROVIDER='com.rokid.sprite.aiapp.external.CXRLinkProvider'
EPOCH=re.compile(r'^(?P<t>\d+\.\d+)\s+.*?(?P<tag>[A-Za-z0-9_.-]+):\s*(?P<m>.*)$')
COMP=re.compile(r'com\.rokid\.sprite\.global\.aiapp/(?:\.[A-Za-z0-9_.$-]+|[A-Za-z0-9_.$-]+)')
CLASS=re.compile(r'com\.rokid\.sprite\.aiapp\.[A-Za-z0-9_.$-]+')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def norm(c):
    if not c:return None
    if '/' in c:
      pkg,cl=c.split('/',1)
      return pkg+'/'+(pkg+cl if cl.startswith('.') else cl)
    return c
def lines(path):return path.read_text(errors='replace').splitlines() if path.is_file() else []
def ts_line(line):
    m=EPOCH.match(line.strip());
    if not m:return None,line
    return int(float(m.group('t'))*1000),m.group('m')
def get_components(s):
    out=[]
    for x in COMP.findall(s):
      tail=x.split('/',1)[1] if '/' in x else ''
      if re.fullmatch(r'u\d+(?:a\d+)?',tail):continue
      if not (tail.startswith('.') or tail.startswith('com.')):continue
      out.append(norm(x))
    return sorted(set(out))
def event_stream(path):
    ans=[]
    for l in lines(path):
      try:
        x=json.loads(l)
        if isinstance(x,dict):ans.append(x)
      except Exception:pass
    return ans
def boolish(v):return v is True or str(v).lower() in ('1','true','yes')
def verify_events(raw):
    pre=event_stream(raw/'pre-force-events-private.jsonl');fin=event_stream(raw/'final-events-private.jsonl')
    a=[x for x in pre if x.get('event_type')=='authorization_result']
    if not a or not boolish((a[-1].get('details') or {}).get('token_present')):raise ValueError('authorization not proven')
    forbidden={'connection_attempt_started','callback_cxrl_connected','callback_glass_bt_connected','service_status_result','photo_ready','operator_gate_prerequisite_ready'}
    if any(x.get('event_type') in forbidden for x in pre):raise ValueError('connection existed before force-stop')
    types=[x.get('event_type') for x in fin]
    if 'connection_attempt_started' not in types:raise ValueError('connection attempt not proven')
    if not any(x.get('event_type')=='callback_cxrl_connected' and boolish((x.get('details') or {}).get('connected')) for x in fin):raise ValueError('CXR-L connected callback not proven')
    if not any(x.get('event_type')=='service_status_result' and boolish((x.get('details') or {}).get('status_success')) for x in fin):raise ValueError('service-status success not proven')
    for x in fin:
      et=str(x.get('event_type',''))
      if re.search(r'(?i)(take[_ -]?photo|photo_request|capture_dispatch|audio.*(?:start|stop|stream)|(?:start|stop).*audio)',et):raise ValueError('media event detected')
    return types
def collector(raw):
    p=raw/'local-activation-collector-summary-private.json';return json.loads(p.read_text())
def parse_logcat(raw):
    events=[]
    for src in ('activity-manager-private.txt','activity-events-private.txt'):
      for line in lines(raw/src):
        ts,msg=ts_line(line);low=msg.lower()
        if HI not in line:continue
        comps=get_components(line);classes=CLASS.findall(line)
        kind=None
        if 'start proc' in low or 'am_proc_start' in low:kind='PROCESS_START'
        elif 'am_create_service' in low or ('service' in low and ('create' in low or 'start' in low or 'bind' in low)):kind='SERVICE_EVENT'
        elif 'provider' in low and ('launch' in low or 'acquir' in low or 'publish' in low or 'install' in low or 'start' in low):kind='PROVIDER_EVENT'
        if kind:events.append({'epoch_ms':ts,'kind':kind,'components':comps,'classes':classes,'line':line})
    return sorted(events,key=lambda e:(e['epoch_ms'] is None,e['epoch_ms'] or 0))
def process_trigger(events):
    for e in events:
      if e['kind']!='PROCESS_START':continue
      line=e['line'];low=line.lower();kind='UNKNOWN'
      if 'for content provider' in low or 'for provider' in low:kind='CONTENT_PROVIDER'
      elif 'for service' in low:kind='SERVICE'
      elif 'for activity' in low:kind='ACTIVITY'
      elif 'for broadcast' in low:kind='BROADCAST'
      comp=e['components'][0] if e['components'] else None
      classes=e['classes'];cls=classes[0] if classes else None
      return e['epoch_ms'],kind,comp,cls,line
    return None,'NONE',None,None,None
def runtime_evidence(raw,events):
    text='\n'.join(e['line'] for e in events)+'\n'
    for n in ('at-respawn-hi-services-private.txt','at-respawn-hi-providers-private.txt','collector-final-hi-services-private.txt','collector-final-hi-providers-private.txt','runtime-component-samples-private.txt'):
      text+='\n'+'\n'.join(lines(raw/n))
    return {
      'cxr_link_service_runtime':CXR_SERVICE in text,
      'cxr_link_provider_runtime':CXR_PROVIDER in text,
      'runtime_components':sorted(set(CLASS.findall(text))),
    }
def disposition(pt_kind,pt_class,rt,resp):
    if resp is None:return 'NO_HI_ROKID_RESPAWN'
    if pt_class==CXR_SERVICE:return 'EXACT_CXRLINKSERVICE_PROCESS_START_TRIGGER'
    if pt_class==CXR_PROVIDER:return 'EXACT_CXRLINKPROVIDER_PROCESS_START_TRIGGER'
    if pt_class:return 'EXACT_OTHER_HI_COMPONENT_PROCESS_START_TRIGGER'
    if rt['cxr_link_service_runtime'] or rt['cxr_link_provider_runtime']:return 'PROCESS_START_TRIGGER_UNRESOLVED_CXR_COMPONENT_RUNTIME_EVIDENCE'
    return 'HI_RESPAWN_PROVEN_EXACT_COMPONENT_UNRESOLVED'
def host_order(coll):
    resp=coll.get('first_hi_respawn_host_epoch_ms');conn=(coll.get('event_first_seen_host_epoch_ms') or {}).get('connection_attempt_started')
    if resp is None or conn is None:return 'UNRESOLVED'
    if resp==conn:return 'SAME_OBSERVATION_TIMESTAMP'
    return 'CONNECTION_ATTEMPT_OBSERVED_FIRST' if conn<resp else 'HI_RESPAWN_OBSERVED_FIRST'
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--evidence',required=True);a=ap.parse_args();ev=Path(a.evidence).resolve();raw=ev/'raw';san=ev/'sanitized';san.mkdir(parents=True,exist_ok=True)
    try:
      verify_events(raw);coll=collector(raw);events=parse_logcat(raw);pt_ms,pt_kind,pt_comp,pt_class,pt_line=process_trigger(events);rt=runtime_evidence(raw,events);resp=coll.get('first_hi_respawn_host_epoch_ms');disp=disposition(pt_kind,pt_class,rt,resp)
      post=(raw/'state-restored.txt').read_text(errors='replace') if (raw/'state-restored.txt').is_file() else ''
      if 'OPERATOR_HI_ROKID_RECOVERY=PASS' not in post:raise ValueError('Hi Rokid restoration not proven')
      exact=disp.startswith('EXACT_')
      result={'schema':'rokid.test21-r3-3-4.local-activation.v1','analysis':'PASS','host_observation_ordering':host_order(coll),'hi_respawn_observed':resp is not None,'process_start_event_epoch_ms':pt_ms,'process_start_trigger_kind':pt_kind,'exact_process_start_trigger_component':pt_comp,'exact_process_start_trigger_class':pt_class,'cxr_link_service_runtime_evidence':rt['cxr_link_service_runtime'],'cxr_link_provider_runtime_evidence':rt['cxr_link_provider_runtime'],'runtime_hi_component_classes':rt['runtime_components'],'activation_disposition':disp,'exact_component_closure':exact,'causality_claim':'LOCAL_ORDERING_AND_ANDROID_START_REASON_ONLY_NOT_LIBRARY_INTERNAL_CALLSTACK','safety':{'photo_operation':'NONE','audio_operation':'NONE','pcapdroid_operation':'NONE','network_capture':'NONE'}}
      jp=san/'test21-r3-3-4-summary.json';jp.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
      fields=[('TEST21_R3_3_4_ANALYSIS','PASS'),('HI_ROKID_RESPAWN_OBSERVED','YES' if resp is not None else 'NO'),('HOST_CONNECTION_RESPAWN_ORDERING',result['host_observation_ordering']),('PROCESS_START_EVENT_EPOCH_MS',pt_ms if pt_ms is not None else 'NONE'),('PROCESS_START_TRIGGER_KIND',pt_kind),('EXACT_PROCESS_START_TRIGGER_COMPONENT',pt_comp or 'NONE'),('EXACT_PROCESS_START_TRIGGER_CLASS',pt_class or 'NONE'),('CXR_LINK_SERVICE_RUNTIME_EVIDENCE','YES' if rt['cxr_link_service_runtime'] else 'NO'),('CXR_LINK_PROVIDER_RUNTIME_EVIDENCE','YES' if rt['cxr_link_provider_runtime'] else 'NO'),('ACTIVATION_DISPOSITION',disp),('EXACT_COMPONENT_CLOSURE','YES' if exact else 'NO'),('CAUSALITY_CLAIM',result['causality_claim']),('PCAPDROID_OPERATION','NONE'),('NETWORK_CAPTURE','NONE'),('PHOTO_OPERATION','NONE'),('AUDIO_OPERATION','NONE'),('HI_ROKID_RESTORATION','PASS')]
      tp=san/'test21-r3-3-4-summary.txt';tp.write_text('\n'.join(f'{k}={v}' for k,v in fields)+'\n')
      (san/'SHA256SUMS.txt').write_text(f'{sha(jp)}  {jp.name}\n{sha(tp)}  {tp.name}\n')
      for k,v in fields:print(f'{k}={v}')
      return 0
    except Exception as e:
      print(f'ERROR: {e}',file=sys.stderr);print('TEST21_R3_3_4_ANALYSIS=FAIL');return 1
if __name__=='__main__':raise SystemExit(main())
