#!/usr/bin/env python3
import argparse, json, re
from pathlib import Path
HI='com.rokid.sprite.global.aiapp'; CUSTOM='org.aimindseye.rokid.cxrphotoqualification'
BIND=re.compile(r'(?i)\b(?:bind|binding|connectionrecord|intentbindrecord|am_bind_service)\b'); PROC=re.compile(r'(?i)\b(?:am_proc_start|start proc|start process|proc_start)\b'); COMP=re.compile(r'com\.rokid\.sprite\.global\.aiapp/(?:\.[A-Za-z0-9_$.-]+|[A-Za-z0-9_$.-]+)'); PHOTO=re.compile(r'(?i)(?:take[_ -]?photo|photo_request|operator_gate_capture_dispatch)'); AUDIO=re.compile(r'(?i)(?:audio.*(?:start|stop|stream)|(?:start|stop).*audio)')
def kv(p):
 d={}
 if not p.is_file(): return d
 for l in p.read_text(errors='replace').splitlines():
  if '=' in l:
   k,v=l.split('=',1); d[k.strip()]=v.strip()
 return d
def events(p):
 out=[]
 if not p.is_file(): return out
 for line in p.read_text(errors='strict').splitlines():
  if line.strip(): out.append(json.loads(line))
 return out
def et(e): return str(e.get('event_type','')).strip()
def det(e): return e.get('details',{}) if isinstance(e.get('details',{}),dict) else {}
def boolish(x): return x is True or str(x).lower() in ('true','1','yes')
def sanitize_candidate(line):
 toks=re.findall(r'(?:[A-Za-z0-9_]+\.){2,}[A-Za-z0-9_:.]+',line); return sorted(set(t for t in toks if any(x in t.lower() for x in ('rokid','cxr','aiui','sprite'))))
def event_gate(ev):
 auth=[e for e in ev if et(e)=='authorization_result']
 if not auth: raise ValueError('authorization_result not observed')
 if not boolish(det(auth[-1]).get('token_present')): raise ValueError('authorization token not present')
 if boolish(det(auth[-1]).get('token_value_logged')): raise ValueError('authorization token value logged')
 for e in ev:
  name=et(e); d=det(e)
  if name in ('connection_attempt_started','callback_cxrl_connected','callback_glass_bt_connected','service_status_result','photo_ready','operator_gate_prerequisite_ready'): raise ValueError('connection/session event observed in authorized-no-connect profile: '+name)
  if PHOTO.search(name) and name!='photo_ready': raise ValueError('photo event observed: '+name)
  if AUDIO.search(name): raise ValueError('audio event observed: '+name)
  if name in ('operator_gate_host_command','operator_gate_arm_result') and boolish(d.get('granted')): raise ValueError('host photo arm granted')
 return True
def service_evidence(raw):
 chunks=[]
 for name in ('activity-events-private.txt','activity-manager-private.txt','first-respawn-hi-services-private.txt','first-respawn-custom-services-private.txt','first-respawn-activity-processes-private.txt'):
  p=raw/name
  if p.is_file(): chunks.append(p.read_text(errors='replace'))
 text='\n'.join(chunks); bind=[]; caller=[]; starts=[]
 for line in text.splitlines():
  if HI in line and BIND.search(line):
   bind.append(line)
   if CUSTOM in line: caller.append(line)
  if HI in line and PROC.search(line): starts.append(line)
 return {'bound':bool(bind),'caller':bool(caller),'start':bool(starts),'components':sorted(set(COMP.findall(text))),'bind_count':len(bind),'caller_count':len(caller),'start_count':len(starts)}
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--repo',required=True); ap.add_argument('--evidence',required=True); a=ap.parse_args(); e=Path(a.evidence); raw=e/'raw'; s=e/'sanitized'; s.mkdir(parents=True,exist_ok=True)
 try:
  pre=events(raw/'pre-force-events-private.jsonl'); final=events(raw/'final-events-private.jsonl'); event_gate(pre); event_gate(final)
  state=kv(raw/'state-pre-force.txt'); fs=kv(raw/'force-stop-observation.txt'); obs=kv(raw/'topology-observation.txt'); restored=kv(raw/'state-restored.txt')
  custom_alive=state.get('CUSTOM_PROCESS_VISIBLE')=='YES'; hi_absent=fs.get('HI_PROCESS_ABSENT_OBSERVED')=='YES'; same=int(fs.get('SAME_PACKAGE_PROCESS_COUNT_POST_FORCE','-1')); respawn=obs.get('HI_ROKID_RESPAWN_OBSERVED')=='YES'; recovery=restored.get('OPERATOR_HI_ROKID_RECOVERY')=='PASS'
  ext=[]; p=raw/'external-candidates-private.txt'
  if p.is_file():
   for line in p.read_text(errors='replace').splitlines(): ext += sanitize_candidate(line)
  ext=sorted(set(x for x in ext if x not in (HI,CUSTOM))); svc=service_evidence(raw)
  if not custom_alive: disp='INVALID_AUTHORIZED_CUSTOM_PROCESS_NOT_ALIVE'
  elif not hi_absent or same!=0: disp='INVALID_FULL_HI_ROKID_STOP_NOT_PROVEN'
  elif respawn: disp='CUSTOM_AUTHORIZED_NO_CONNECT_HI_ROKID_RESPAWNED'
  else: disp='CUSTOM_AUTHORIZED_NO_CONNECT_HI_ROKID_REMAINED_STOPPED'
  if disp=='CUSTOM_AUTHORIZED_NO_CONNECT_HI_ROKID_RESPAWNED' and svc['caller']: nxt='R3_4_AUTHORIZATION_BOUND_COMPONENT_QUALIFICATION'
  elif disp=='CUSTOM_AUTHORIZED_NO_CONNECT_HI_ROKID_RESPAWNED': nxt='R3_3_1_AUTHORIZATION_RESPAWN_CALLER_CHARACTERIZATION'
  elif disp=='CUSTOM_AUTHORIZED_NO_CONNECT_HI_ROKID_REMAINED_STOPPED': nxt='R3_3_1_POST_AUTHORIZATION_DELAY_OR_FOREGROUND_STATE_CHARACTERIZATION'
  else: nxt='STOP_REPAIR_OBSERVABILITY'
  analysis='PASS' if recovery and disp.startswith('CUSTOM_') else 'FAIL'
  summary={'schema':'rokid.test21-r3-3.summary.v1','profile':'CUSTOM_AUTHORIZED_NO_CONNECT','analysis':analysis,'custom_process_alive_before_hi_force_stop':custom_alive,'authorization_performed':True,'authorization_token_present':True,'authorization_token_host_exported':False,'cxr_l_connection_attempt':False,'hi_rokid_process_absence_observed':hi_absent,'same_package_process_count_immediate_post_force':same,'all_hi_rokid_same_package_processes_down':hi_absent and same==0,'hi_rokid_respawn_observed':respawn,'first_respawn_elapsed_ms':obs.get('FIRST_RESPAWN_ELAPSED_MS','NONE'),'external_rokid_ai_process_candidates':ext,'external_candidate_count':len(ext),'bound_service_caller_evidence':svc['caller'],'bound_service_evidence':svc['bound'],'process_start_event_evidence':svc['start'],'hi_rokid_components_at_respawn':svc['components'],'binding_evidence_line_count':svc['bind_count'],'caller_binding_evidence_line_count':svc['caller_count'],'process_start_evidence_line_count':svc['start_count'],'operator_hi_rokid_recovery':recovery,'disposition':disp,'next_action':nxt,'photo_operation':'NONE','audio_operation':'NONE','package_disable_or_uninstall':'NONE','package_data_clear':'NONE'}
  (s/'test21-r3-3-summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
  lines=[f'TEST21_R3_3_ANALYSIS={analysis}','PROFILE=CUSTOM_AUTHORIZED_NO_CONNECT',f'CUSTOM_PROCESS_ALIVE_BEFORE_HI_FORCE_STOP={"YES" if custom_alive else "NO"}','AUTHORIZATION_PERFORMED=YES','AUTHORIZATION_TOKEN_PRESENT=YES','AUTHORIZATION_TOKEN_HOST_EXPORT=NO','CXR_L_CONNECTION_ATTEMPT=NO',f'HI_ROKID_PROCESS_ABSENCE_OBSERVED={"YES" if hi_absent else "NO"}',f'SAME_PACKAGE_PROCESS_COUNT_IMMEDIATE_POST_FORCE={same}',f'ALL_HI_ROKID_SAME_PACKAGE_PROCESSES_DOWN={"YES" if hi_absent and same==0 else "NO"}',f'HI_ROKID_RESPAWN_OBSERVED={"YES" if respawn else "NO"}',f'FIRST_RESPAWN_ELAPSED_MS={summary["first_respawn_elapsed_ms"]}',f'EXTERNAL_ROKID_AI_PROCESS_CANDIDATE_COUNT={len(ext)}',f'BOUND_SERVICE_CALLER_EVIDENCE={"YES" if svc["caller"] else "NO"}',f'BOUND_SERVICE_EVIDENCE={"YES" if svc["bound"] else "NO"}',f'PROCESS_START_EVENT_EVIDENCE={"YES" if svc["start"] else "NO"}',f'DISPOSITION={disp}',f'NEXT_ACTION={nxt}','PHOTO_OPERATION=NONE','AUDIO_OPERATION=NONE']
  (s/'test21-r3-3-summary.txt').write_text('\n'.join(lines)+'\n'); print('\n'.join(lines)); return 0 if analysis=='PASS' else 1
 except Exception as ex:
  print('ERROR:',ex); print('TEST21_R3_3_ANALYSIS=FAIL'); return 1
if __name__=='__main__': raise SystemExit(main())
