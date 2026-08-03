#!/usr/bin/env python3
import argparse,json,re
from pathlib import Path
HI='com.rokid.sprite.global.aiapp';CUSTOM='org.aimindseye.rokid.cxrphotoqualification'
def j(p,default=None):
 try:return json.loads(p.read_text())
 except:return {} if default is None else default
def rows(p):
 out=[]
 if p.is_file():
  for l in p.read_text(errors='replace').splitlines():
   try:out.append(json.loads(l))
   except:pass
 return out
def first_marker(net,pkg,after):
 xs=[r for r in net if r.get('package')==pkg and r.get('marker_type') and isinstance(r.get('epoch_ms'),int) and r['epoch_ms']>=after]
 return min((r['epoch_ms'] for r in xs),default=None)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--evidence',required=True);a=ap.parse_args();e=Path(a.evidence);raw=e/'raw';san=e/'sanitized';san.mkdir(parents=True,exist_ok=True)
 try:
  coll=j(raw/'collector-summary-private.json');marks=rows(raw/'host-timeline-private.jsonl');net=rows(raw/'network-packets-private.jsonl');http=rows(raw/'decrypted-http-private.jsonl');np=j(raw/'network-parse-private.json');events=rows(raw/'final-events-private.jsonl')
  ets=[str(e.get('event_type','')).strip() for e in events];details=[e.get('details',{}) if isinstance(e.get('details',{}),dict) else {} for e in events]
  if 'connection_attempt_started' not in ets: raise ValueError('final event stream does not prove CXR-L connection attempt')
  for n in ets:
   if re.search(r'(?i)(take[_ -]?photo|photo_request|capture_dispatch|audio.*(?:start|stop|stream)|(?:start|stop).*audio)',n): raise ValueError('forbidden media event in final stream: '+n)
  md={x.get('name'):x.get('host_epoch_ms') for x in marks if x.get('kind')=='host_marker'};force=md.get('hi_force_stop_issued');absent=md.get('hi_absence_proven');ready=md.get('ready_for_r3_connection_confirmed');now=md.get('button2_now_prompt');done=md.get('button2_operator_done');resp=coll.get('first_hi_respawn_host_epoch_ms');ev=coll.get('event_first_seen_host_epoch_ms',{});conn=ev.get('connection_attempt_started')
  if not all(isinstance(x,int) for x in (force,absent)):raise ValueError('force-stop/absence host timeline missing')
  cnet=first_marker(net,CUSTOM,force);hnet=first_marker(net,HI,force)
  replicated=bool(resp is not None and (conn is None or resp<conn))
  if resp is None:disp='NO_RESPAWN_REPLICATION'
  elif cnet is not None and cnet<resp:disp='CUSTOM_NETWORK_MARKER_PRECEDES_RESPAWN'
  elif hnet is not None and hnet<resp:disp='HI_ROKID_NETWORK_MARKER_PRECEDES_RESPAWN'
  elif (cnet is None or resp<=cnet) and (hnet is None or resp<=hnet):disp='RESPAWN_PRECEDES_TARGET_NETWORK_MARKERS'
  else:disp='NETWORK_RESPAWN_ORDERING_MIXED'
  hosts={CUSTOM:sorted(set(r.get('host') for r in net if r.get('package')==CUSTOM and r.get('host'))),HI:sorted(set(r.get('host') for r in net if r.get('package')==HI and r.get('host')))}
  def http_sanitized(r):return {'epoch_ms':r.get('epoch_ms'),'package':r.get('package'),'host':r.get('host'),'method':r.get('method'),'path':r.get('path'),'status':r.get('status')}
  (san/'network-http-sanitized.jsonl').write_text(''.join(json.dumps(http_sanitized(x),sort_keys=True)+'\n' for x in http if x.get('package') in (HI,CUSTOM)))
  summary={'schema':'rokid.test21-r3-3-3.sanitized-summary.v1','analysis':'PASS','original_r3_respawn_before_connection_reproduced':replicated,'network_respawn_disposition':disp,'hi_respawn_epoch_ms':resp,'connection_attempt_epoch_ms':conn,'cxr_l_connected':'callback_cxrl_connected' in ets,'glass_bt_connected':'callback_glass_bt_connected' in ets,'service_status_success':'service_status_result' in ets,'button2_now_prompt_epoch_ms':now,'button2_operator_done_epoch_ms':done,'custom_first_network_marker_after_force_epoch_ms':cnet,'hi_first_network_marker_after_force_epoch_ms':hnet,'custom_hosts':hosts[CUSTOM],'hi_hosts':hosts[HI],'decrypted_http_metadata':np.get('tshark_decryption_metadata','UNAVAILABLE'),'decrypted_http_rows':np.get('decrypted_http_rows',0),'causality_claim':'CORRELATION_ONLY_NOT_CAUSATION'}
  (san/'test21-r3-3-3-summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
  lines=['TEST21_R3_3_3_ANALYSIS=PASS',f'ORIGINAL_R3_RESPAWN_BEFORE_CONNECTION_REPRODUCED={"YES" if replicated else "NO"}',f'NETWORK_RESPAWN_DISPOSITION={disp}',f'HI_ROKID_RESPAWN_OBSERVED={"YES" if resp is not None else "NO"}',f'CUSTOM_FIRST_NETWORK_MARKER_AFTER_FORCE_EPOCH_MS={cnet if cnet is not None else "NONE"}',f'HI_FIRST_NETWORK_MARKER_AFTER_FORCE_EPOCH_MS={hnet if hnet is not None else "NONE"}',f'DECRYPTED_HTTP_METADATA={summary["decrypted_http_metadata"]}',f'DECRYPTED_HTTP_ROWS={summary["decrypted_http_rows"]}','NETWORK_CAUSALITY=CORRELATION_ONLY_NOT_CAUSATION','PHOTO_OPERATION=NONE','AUDIO_OPERATION=NONE']
  (san/'test21-r3-3-3-summary.txt').write_text('\n'.join(lines)+'\n');print('\n'.join(lines));return 0
 except Exception as ex:print('ERROR:',ex);print('TEST21_R3_3_3_ANALYSIS=FAIL');return 1
if __name__=='__main__':raise SystemExit(main())
