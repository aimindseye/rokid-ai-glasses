#!/usr/bin/env python3
import argparse,json,re
from pathlib import Path
HI='com.rokid.sprite.global.aiapp';CUSTOM='org.aimindseye.rokid.cxrphotoqualification'
BIND=re.compile(r'(?i)(bind|binding|bound|connection|service connection|client)');PROC=re.compile(r'(?i)(start proc|start_process|process start|proc start)');COMP=re.compile(r'com\.rokid\.sprite\.global\.aiapp/[A-Za-z0-9_.$]+');PHOTO=re.compile(r'(?i)(?:take[_ -]?photo|photo_request|operator_gate_capture_dispatch)');AUDIO=re.compile(r'(?i)(?:audio.*(?:start|stop|stream)|(?:start|stop).*audio)')
def kv(p):
 d={}
 if p.is_file():
  for l in p.read_text(errors='replace').splitlines():
   if '=' in l:k,v=l.split('=',1);d[k.strip()]=v.strip()
 return d
def events(p):
 o=[]
 if p.is_file():
  for l in p.read_text(errors='replace').splitlines():
   if l.strip():o.append(json.loads(l))
 return o
def et(e):return str(e.get('event_type','')).strip()
def det(e):return e.get('details',{}) if isinstance(e.get('details',{}),dict) else {}
def b(x):return x is True or str(x).lower() in ('true','1','yes')
def gate(ev):
 a=[e for e in ev if et(e)=='authorization_result']
 if not a or not b(det(a[-1]).get('token_present')):raise ValueError('authorization token not proven')
 if b(det(a[-1]).get('token_value_logged')):raise ValueError('authorization token value logged')
 for e in ev:
  n=et(e);d=det(e)
  if n in {'connection_attempt_started','callback_cxrl_connected','callback_glass_bt_connected','service_status_result','photo_ready','operator_gate_prerequisite_ready'}:raise ValueError('forbidden connection/session event: '+n)
  if PHOTO.search(n):raise ValueError('forbidden photo event: '+n)
  if AUDIO.search(n):raise ValueError('forbidden audio event: '+n)
  if n in {'operator_gate_host_command','operator_gate_arm_result'} and b(d.get('granted')):raise ValueError('host arm granted')
def scan(raw,label):
 chunks=[]
 for suf in ('hi-services-private.txt','custom-services-private.txt','activity-processes-private.txt'):
  p=raw/f'{label}-{suf}'
  if p.is_file():chunks.append(p.read_text(errors='replace'))
 text='\n'.join(chunks);bind=[];caller=[]
 for line in text.splitlines():
  if HI in line and BIND.search(line):
   bind.append(line)
   if CUSTOM in line:caller.append(line)
 return {'bind':bool(bind),'caller':bool(caller),'bind_count':len(bind),'caller_count':len(caller),'components':sorted(set(COMP.findall(text)))}
def lifecycle(raw):
 text=''
 for n in ('lifecycle-activity-events-private.txt','lifecycle-activity-task-private.txt'):
  p=raw/n
  if p.is_file():text+='\n'+p.read_text(errors='replace')
 lines=[l for l in text.splitlines() if CUSTOM in l]
 return {'custom_lifecycle_evidence':bool(lines),'line_count':len(lines)}
def postforce(raw):
 text=''
 for n in ('postforce-activity-events-private.txt','postforce-activity-manager-private.txt','first-respawn-hi-services-private.txt','first-respawn-custom-services-private.txt','first-respawn-activity-processes-private.txt'):
  p=raw/n
  if p.is_file():text+='\n'+p.read_text(errors='replace')
 bind=[l for l in text.splitlines() if HI in l and BIND.search(l)];caller=[l for l in bind if CUSTOM in l];starts=[l for l in text.splitlines() if HI in l and PROC.search(l)]
 return {'bind':bool(bind),'caller':bool(caller),'start':bool(starts),'bind_count':len(bind),'caller_count':len(caller),'start_count':len(starts),'components':sorted(set(COMP.findall(text)))}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--repo',required=True);ap.add_argument('--evidence',required=True);a=ap.parse_args();e=Path(a.evidence);raw=e/'raw';s=e/'sanitized';s.mkdir(parents=True,exist_ok=True)
 try:
  gate(events(raw/'pre-force-events-private.jsonl'));gate(events(raw/'final-events-private.jsonl'))
  fg=kv(raw/'foreground-before-state.txt');b0=kv(raw/'background-00-state.txt');b15=kv(raw/'background-15-state.txt');fs=kv(raw/'force-stop-observation.txt');obs=kv(raw/'topology-observation.txt');rest=kv(raw/'state-restored.txt')
  scans={x:scan(raw,x) for x in ('foreground-before','background-00','background-15')};life=lifecycle(raw);pf=postforce(raw)
  transition=(fg.get('CUSTOM_PROCESS_VISIBLE')=='YES' and fg.get('CUSTOM_FOREGROUND_PROVEN')=='YES' and b0.get('CUSTOM_PROCESS_VISIBLE')=='YES' and b0.get('CUSTOM_FOREGROUND_PROVEN')=='NO' and b15.get('CUSTOM_PROCESS_VISIBLE')=='YES' and b15.get('CUSTOM_FOREGROUND_PROVEN')=='NO')
  hi_abs=fs.get('HI_PROCESS_ABSENT_OBSERVED')=='YES';same=int(fs.get('SAME_PACKAGE_PROCESS_COUNT_POST_FORCE','-1'));resp=obs.get('HI_ROKID_RESPAWN_OBSERVED')=='YES';recovery=rest.get('OPERATOR_HI_ROKID_RECOVERY')=='PASS'
  first_bind='NONE';first_caller='NONE'
  for label in ('foreground-before','background-00','background-15'):
   if first_bind=='NONE' and scans[label]['bind']:first_bind=label
   if first_caller=='NONE' and scans[label]['caller']:first_caller=label
  transition_bind='YES' if (not scans['foreground-before']['caller'] and (scans['background-00']['caller'] or scans['background-15']['caller'])) else 'NO'
  if not transition:disp='INVALID_FOREGROUND_BACKGROUND_TRANSITION_NOT_PROVEN'
  elif not hi_abs or same!=0:disp='INVALID_FULL_HI_ROKID_STOP_NOT_PROVEN'
  elif resp:disp='AUTHORIZED_BACKGROUND_TRANSITION_HI_ROKID_RESPAWNED'
  else:disp='AUTHORIZED_BACKGROUND_TRANSITION_HI_ROKID_REMAINED_STOPPED'
  if transition_bind=='YES':nxt='R3_3_3_LIFECYCLE_CREATED_BOUND_COMPONENT_QUALIFICATION'
  elif resp and pf['caller']:nxt='R3_3_3_RESPAWN_BOUND_COMPONENT_QUALIFICATION'
  elif resp:nxt='R3_3_3_RESPAWN_TRIGGER_TIMING_REPLICATION'
  elif disp=='AUTHORIZED_BACKGROUND_TRANSITION_HI_ROKID_REMAINED_STOPPED':nxt='R3_3_3_ORIGINAL_R3_SEQUENCE_DIFFERENTIAL_REPLICATION'
  else:nxt='STOP_REPAIR_OBSERVABILITY'
  analysis='PASS' if recovery and disp.startswith('AUTHORIZED_') else 'FAIL'
  summary={'schema':'rokid.test21-r3-3-2.summary.v1','profile':'AUTHORIZED_FOREGROUND_TO_BACKGROUND_HOME_15S','analysis':analysis,'authorization_performed':True,'authorization_token_present':True,'authorization_token_host_exported':False,'cxr_l_connection_attempt':False,'lifecycle_transition_method':'HOST_KEYCODE_HOME','foreground_to_background_transition_proven':transition,'custom_lifecycle_log_evidence':life,'pre_force_binding_evidence':scans,'first_pre_force_binding_checkpoint':first_bind,'first_pre_force_caller_binding_checkpoint':first_caller,'caller_binding_created_after_background_transition':transition_bind=='YES','hi_rokid_process_absence_observed':hi_abs,'same_package_process_count_immediate_post_force':same,'all_hi_rokid_same_package_processes_down':hi_abs and same==0,'hi_rokid_respawn_observed':resp,'first_respawn_elapsed_ms':obs.get('FIRST_RESPAWN_ELAPSED_MS','NONE'),'post_force_bound_service_caller_evidence':pf['caller'],'post_force_bound_service_evidence':pf['bind'],'process_start_event_evidence':pf['start'],'hi_rokid_components_at_respawn':pf['components'],'operator_hi_rokid_recovery':recovery,'disposition':disp,'next_action':nxt,'photo_operation':'NONE','audio_operation':'NONE'}
  (s/'test21-r3-3-2-summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
  lines=[f'TEST21_R3_3_2_ANALYSIS={analysis}','PROFILE=AUTHORIZED_FOREGROUND_TO_BACKGROUND_HOME_15S','AUTHORIZATION_PERFORMED=YES','AUTHORIZATION_TOKEN_PRESENT=YES','AUTHORIZATION_TOKEN_HOST_EXPORT=NO','CXR_L_CONNECTION_ATTEMPT=NO','LIFECYCLE_TRANSITION_METHOD=HOST_KEYCODE_HOME',f'FOREGROUND_TO_BACKGROUND_TRANSITION_PROVEN={"YES" if transition else "NO"}',f'CUSTOM_LIFECYCLE_LOG_EVIDENCE={"YES" if life["custom_lifecycle_evidence"] else "NO"}',f'CALLER_BINDING_EVIDENCE_FOREGROUND_BEFORE={"YES" if scans["foreground-before"]["caller"] else "NO"}',f'CALLER_BINDING_EVIDENCE_BACKGROUND_00={"YES" if scans["background-00"]["caller"] else "NO"}',f'CALLER_BINDING_EVIDENCE_BACKGROUND_15={"YES" if scans["background-15"]["caller"] else "NO"}',f'FIRST_PRE_FORCE_CALLER_BINDING_CHECKPOINT={first_caller}',f'CALLER_BINDING_CREATED_AFTER_BACKGROUND_TRANSITION={transition_bind}',f'HI_ROKID_PROCESS_ABSENCE_OBSERVED={"YES" if hi_abs else "NO"}',f'ALL_HI_ROKID_SAME_PACKAGE_PROCESSES_DOWN={"YES" if hi_abs and same==0 else "NO"}',f'HI_ROKID_RESPAWN_OBSERVED={"YES" if resp else "NO"}',f'FIRST_RESPAWN_ELAPSED_MS={summary["first_respawn_elapsed_ms"]}',f'POST_FORCE_BOUND_SERVICE_CALLER_EVIDENCE={"YES" if pf["caller"] else "NO"}',f'PROCESS_START_EVENT_EVIDENCE={"YES" if pf["start"] else "NO"}',f'DISPOSITION={disp}',f'NEXT_ACTION={nxt}','PHOTO_OPERATION=NONE','AUDIO_OPERATION=NONE']
  (s/'test21-r3-3-2-summary.txt').write_text('\n'.join(lines)+'\n');print('\n'.join(lines));return 0 if analysis=='PASS' else 1
 except Exception as ex:
  print('ERROR:',ex);print('TEST21_R3_3_2_ANALYSIS=FAIL');return 1
if __name__=='__main__':raise SystemExit(main())
