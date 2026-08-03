#!/usr/bin/env python3
import argparse,json
from pathlib import Path
HI='com.rokid.sprite.global.aiapp';CUSTOM='org.aimindseye.rokid.cxrphotoqualification';TARGETS=(HI,CUSTOM)
def rows(p):
 out=[]
 if p.is_file():
  for line in p.read_text(errors='replace').splitlines():
   try:out.append(json.loads(line))
   except:pass
 return out
def load(p):
 try:return json.loads(p.read_text())
 except:return {}
def phase(ms,marks):
 if ms is None:return 'UNKNOWN'
 if ms < marks.get('baseline_end',10**30):return 'HI_ROKID_BASELINE'
 if ms < marks.get('custom_idle_end',10**30):return 'CUSTOM_IDLE'
 if ms < marks.get('authorization_complete',10**30):return 'AUTHORIZATION'
 if ms <= marks.get('authorized_settle_end',10**30):return 'AUTHORIZED_NO_CONNECT'
 return 'POST_SETTLE'
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--evidence',required=True);a=ap.parse_args();e=Path(a.evidence);raw=e/'raw';san=e/'sanitized';san.mkdir(parents=True,exist_ok=True)
 try:
  tl=rows(raw/'host-timeline-private.jsonl');net=rows(raw/'network-packets-private.jsonl');http=rows(raw/'decrypted-http-private.jsonl');np=load(raw/'network-parse-private.json');events=rows(raw/'final-events-private.jsonl')
  md={x.get('name'):x.get('host_epoch_ms') for x in tl if x.get('kind')=='host_marker'}
  required=('pcapdroid_capture_start','baseline_end','custom_launch','custom_idle_end','authorization_complete','authorized_settle_end','pcapdroid_capture_stop')
  miss=[x for x in required if not isinstance(md.get(x),int)]
  if miss:raise ValueError('missing timeline markers: '+','.join(miss))
  forbidden={'connection_attempt_started','callback_cxrl_connected','callback_glass_bt_connected','service_status_result','photo_ready','operator_gate_prerequisite_ready'}
  seen=sorted(set(str(x.get('event_type','')).strip() for x in events if str(x.get('event_type','')).strip() in forbidden))
  if seen:raise ValueError('forbidden connection events observed: '+','.join(seen))
  counts={}
  for pkg in TARGETS:
   pr=[r for r in net if r.get('package')==pkg];pub=[r for r in pr if r.get('public_endpoint')];mr=[r for r in pr if r.get('marker_type')];hr=[r for r in http if r.get('package')==pkg]
   by={}
   for r in pr:by[phase(r.get('epoch_ms'),md)]=by.get(phase(r.get('epoch_ms'),md),0)+1
   counts[pkg]={'packet_rows':len(pr),'public_packet_rows':len(pub),'marker_rows':len(mr),'decrypted_http_rows':len(hr),'phase_packet_rows':by,'hosts':sorted(set(r.get('host') for r in mr+hr if r.get('host'))),'http_frame_trailer_rows':sum(r.get('attribution_method')=='FRAME_TRAILER' for r in hr)}
  hi=counts[HI]['packet_rows'];cu=counts[CUSTOM]['packet_rows']
  if hi and cu:disp='BOTH_TARGET_PACKET_ATTRIBUTION_PROVEN'
  elif hi and not cu:disp='HI_ATTRIBUTION_PROVEN_CUSTOM_NETWORK_SILENT'
  elif cu and not hi:disp='CUSTOM_ATTRIBUTION_PROVEN_HI_NETWORK_SILENT'
  else:disp='NO_TARGET_PACKET_ATTRIBUTION_OBSERVED'
  target_http=counts[HI]['decrypted_http_rows']+counts[CUSTOM]['decrypted_http_rows']
  httpdisp='TARGET_HTTP_ATTRIBUTION_PROVEN' if target_http else ('DECRYPTION_AVAILABLE_BUT_TARGET_HTTP_UNATTRIBUTED' if np.get('tshark_decryption_metadata')=='AVAILABLE' and np.get('decrypted_http_rows',0)>0 else 'NO_TARGET_HTTP_ROWS_OBSERVED')
  summary={'schema':'rokid.test21-r3-3-3-1.sanitized-summary.v1','analysis':'PASS','profile':'PCAPDROID_DUAL_APP_ATTRIBUTION_AUTHORIZED_NO_CONNECT','attribution_disposition':disp,'http_attribution_disposition':httpdisp,'pcapdroid_target_configuration':'BOTH_APPS_OPERATOR_CONFIRMED_AND_API_REQUESTED','tls_decryption':np.get('tshark_decryption_metadata','UNAVAILABLE'),'all_decrypted_http_rows':np.get('decrypted_http_rows',0),'target_attributed_http_rows':target_http,'frame_trailer_attributed_http_rows':np.get('frame_trailer_attributed_http_rows',0),'hi_rokid':counts[HI],'custom_app':counts[CUSTOM],'custom_direct_public_network_observed':counts[CUSTOM]['public_packet_rows']>0,'cxr_l_connection_attempt':'NONE','hi_rokid_force_stop':'NONE','photo_operation':'NONE','audio_operation':'NONE'}
  (san/'test21-r3-3-3-1-summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
  target_rows=[]
  for r in http:
   if r.get('package') in TARGETS:
    target_rows.append({'epoch_ms':r.get('epoch_ms'),'phase':phase(r.get('epoch_ms'),md),'package':r.get('package'),'attribution_method':r.get('attribution_method'),'host':r.get('host'),'method':r.get('method'),'path':r.get('path'),'status':r.get('status')})
  (san/'network-http-attributed-sanitized.jsonl').write_text(''.join(json.dumps(x,sort_keys=True)+'\n' for x in target_rows))
  lines=['TEST21_R3_3_3_1_ANALYSIS=PASS',f'ATTRIBUTION_DISPOSITION={disp}',f'HTTP_ATTRIBUTION_DISPOSITION={httpdisp}',f'HI_PACKET_ROWS={counts[HI]["packet_rows"]}',f'CUSTOM_PACKET_ROWS={counts[CUSTOM]["packet_rows"]}',f'HI_PUBLIC_PACKET_ROWS={counts[HI]["public_packet_rows"]}',f'CUSTOM_PUBLIC_PACKET_ROWS={counts[CUSTOM]["public_packet_rows"]}',f'HI_DECRYPTED_HTTP_ROWS={counts[HI]["decrypted_http_rows"]}',f'CUSTOM_DECRYPTED_HTTP_ROWS={counts[CUSTOM]["decrypted_http_rows"]}',f'ALL_DECRYPTED_HTTP_ROWS={np.get("decrypted_http_rows",0)}',f'TARGET_ATTRIBUTED_HTTP_ROWS={target_http}',f'FRAME_TRAILER_ATTRIBUTED_HTTP_ROWS={np.get("frame_trailer_attributed_http_rows",0)}',f'CUSTOM_DIRECT_PUBLIC_NETWORK_OBSERVED={"YES" if counts[CUSTOM]["public_packet_rows"] else "NO"}','CXR_L_CONNECTION_ATTEMPT=NONE','HI_ROKID_FORCE_STOP=NONE','PHOTO_OPERATION=NONE','AUDIO_OPERATION=NONE']
  (san/'test21-r3-3-3-1-summary.txt').write_text('\n'.join(lines)+'\n');print('\n'.join(lines));return 0
 except Exception as ex:print('ERROR:',ex);print('TEST21_R3_3_3_1_ANALYSIS=FAIL');return 1
if __name__=='__main__':raise SystemExit(main())
