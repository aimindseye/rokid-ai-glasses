#!/usr/bin/env python3
import argparse, json, re
from pathlib import Path
HI='com.rokid.sprite.global.aiapp'; CUSTOM='org.aimindseye.rokid.cxrphotoqualification'

def kv(path):
    d={}
    if not path.exists(): return d
    for l in path.read_text(errors='replace').splitlines():
        if '=' in l:
            k,v=l.split('=',1); d[k]=v
    return d

def sanitize_candidate(line):
    # Keep only recognizable package/process tokens, never PID/user columns.
    toks=re.findall(r'(?:[A-Za-z0-9_]+\.){2,}[A-Za-z0-9_:.]+', line)
    return sorted(set(t for t in toks if any(x in t.lower() for x in ('rokid','cxr','aiui','sprite'))))

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--repo',required=True); ap.add_argument('--evidence',required=True)
    a=ap.parse_args(); e=Path(a.evidence); s=e/'sanitized'; s.mkdir(parents=True,exist_ok=True)
    pre=kv(e/'raw/profile-state-before-hi-force-stop.txt'); fs=kv(e/'raw/force-stop-observation.txt'); obs=kv(e/'raw/topology-observation.txt'); restored=kv(e/'raw/state-restored.txt')
    ext=[]
    p=e/'raw/external-candidates-private.txt'
    if p.exists():
        for line in p.read_text(errors='replace').splitlines(): ext += sanitize_candidate(line)
    ext=sorted(set(x for x in ext if x not in (HI,CUSTOM)))
    custom_alive=pre.get('CUSTOM_PROCESS_VISIBLE')=='YES'
    hi_absent=fs.get('HI_PROCESS_ABSENT_OBSERVED')=='YES'
    same_post=int(fs.get('SAME_PACKAGE_PROCESS_COUNT_POST_FORCE','-1'))
    respawn=obs.get('HI_ROKID_RESPAWN_OBSERVED')=='YES'
    recovery=restored.get('OPERATOR_HI_ROKID_RECOVERY')=='PASS'
    if not custom_alive: disposition='INVALID_CUSTOM_UNAUTHORIZED_NOT_ALIVE'
    elif not hi_absent or same_post!=0: disposition='INVALID_FULL_HI_ROKID_STOP_NOT_PROVEN'
    elif respawn: disposition='CUSTOM_UNAUTHORIZED_ALIVE_HI_ROKID_RESPAWNED'
    else: disposition='CUSTOM_UNAUTHORIZED_ALIVE_HI_ROKID_REMAINED_STOPPED'
    if disposition=='CUSTOM_UNAUTHORIZED_ALIVE_HI_ROKID_RESPAWNED' and ext:
        nxt='R3_3_EXTERNAL_BACKGROUND_OWNER_QUALIFICATION'
    elif disposition=='CUSTOM_UNAUTHORIZED_ALIVE_HI_ROKID_RESPAWNED':
        nxt='R3_2_1_STARTUP_BIND_PROVIDER_CHARACTERIZATION'
    elif disposition=='CUSTOM_UNAUTHORIZED_ALIVE_HI_ROKID_REMAINED_STOPPED':
        nxt='R3_1_PROFILE_CUSTOM_AUTHORIZED_NO_CONNECT'
    else: nxt='STOP_REPAIR_OBSERVABILITY'
    summary={
      'schema':'rokid.test21-r3-2.summary.v1','profile':'CUSTOM_UNAUTHORIZED_ALIVE',
      'analysis':'PASS' if recovery and disposition.startswith('CUSTOM_') else 'FAIL',
      'custom_process_alive_before_hi_force_stop':custom_alive,
      'authorization_performed':False,'cxr_l_connection_attempt':False,
      'hi_rokid_process_absence_observed':hi_absent,
      'same_package_process_count_immediate_post_force':same_post,
      'all_hi_rokid_same_package_processes_down': hi_absent and same_post==0,
      'hi_rokid_respawn_observed':respawn,'first_respawn_elapsed_ms':obs.get('FIRST_RESPAWN_ELAPSED_MS','NONE'),
      'external_rokid_ai_process_candidates':ext,
      'external_candidate_count':len(ext),
      'operator_hi_rokid_recovery':recovery,
      'disposition':disposition,'next_action':nxt,
      'photo_operation':'NONE','audio_operation':'NONE','package_disable_or_uninstall':'NONE','package_data_clear':'NONE'
    }
    (s/'test21-r3-2-summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    lines=[f'{k.upper()}={v}' for k,v in [
      ('analysis',summary['analysis']),('profile',summary['profile']),('custom_process_alive_before_hi_force_stop','YES' if custom_alive else 'NO'),
      ('authorization_performed','NO'),('cxr_l_connection_attempt','NO'),('hi_rokid_process_absence_observed','YES' if hi_absent else 'NO'),
      ('same_package_process_count_immediate_post_force',same_post),('all_hi_rokid_same_package_processes_down','YES' if summary['all_hi_rokid_same_package_processes_down'] else 'NO'),
      ('hi_rokid_respawn_observed','YES' if respawn else 'NO'),('first_respawn_elapsed_ms',summary['first_respawn_elapsed_ms']),
      ('external_rokid_ai_process_candidate_count',len(ext)),('disposition',disposition),('next_action',nxt),('photo_operation','NONE'),('audio_operation','NONE')]]
    (s/'test21-r3-2-summary.txt').write_text('\n'.join(lines)+'\n')
    print('\n'.join('TEST21_R3_2_'+x if x.startswith('ANALYSIS=') else x for x in lines))
    return 0 if summary['analysis']=='PASS' else 1
if __name__=='__main__': raise SystemExit(main())
