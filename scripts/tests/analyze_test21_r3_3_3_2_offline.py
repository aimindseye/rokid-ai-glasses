#!/usr/bin/env python3
import argparse,csv,json,subprocess,shutil,re
from pathlib import Path
from datetime import datetime
HI='com.rokid.sprite.global.aiapp'
INIT_TYPES={'DNS_QUERY','TLS_CLIENT_HELLO','HTTP_REQUEST','HTTP2_REQUEST'}
REQ_COLS=['IPProto','SrcIP','SrcPort','DstIp','DstPort','UID','App','PackageName','Proto','Status','Info','BytesSent','BytesRcvd','PktsSent','PktsRcvd','FirstSeen','LastSeen']

def read_json(p):
 try:return json.loads(p.read_text())
 except:return {}
def rows_jsonl(p):
 out=[]
 if p.is_file():
  for line in p.read_text(errors='replace').splitlines():
   try:
    x=json.loads(line)
    if isinstance(x,dict):out.append(x)
   except:pass
 return out
def iso_ms(s):return int(datetime.fromisoformat(s).timestamp()*1000)
def norm_host(s):return (s or '').strip().lower().rstrip('.')
def find_one(root,pat,required=True):
 xs=[x for x in (root/'raw').glob(pat) if x.is_file() and x.stat().st_size>0]
 if len(xs)==1:return xs[0]
 if not xs and not required:return None
 raise ValueError(f'expected exactly one {pat} under {root}/raw, found {len(xs)}')
def native_csv(path):
 with path.open('r',encoding='utf-8-sig',newline='') as f:
  r=csv.DictReader(f);cols=r.fieldnames or []
  if cols!=REQ_COLS:raise ValueError('native CSV schema mismatch: '+'|'.join(cols))
  src=list(r)
 hi=[]
 for row in src:
  if row.get('PackageName')!=HI:continue
  host=norm_host(row.get('Info'))
  if not host:continue
  hi.append({'app':row.get('App'),'package':row.get('PackageName'),'proto':row.get('Proto'),'status':row.get('Status'),'host':host,'bytes_sent':int(row.get('BytesSent') or 0),'bytes_received':int(row.get('BytesRcvd') or 0),'packets_sent':int(row.get('PktsSent') or 0),'packets_received':int(row.get('PktsRcvd') or 0),'first_seen_epoch_ms':iso_ms(row['FirstSeen']),'last_seen_epoch_ms':iso_ms(row['LastSeen'])})
 if not hi:raise ValueError('native CSV contains no Hi Rokid rows')
 return src,hi

def tshark_scan(pcap,keylog,hosts):
 exe=shutil.which('tshark')
 if not exe:raise ValueError('tshark not found in PATH')
 fields=['frame.number','frame.time_epoch','dns.flags.response','dns.qry.name','tls.handshake.type','tls.handshake.extensions_server_name','http.request.method','http.host','http.request.uri','http2.headers.method','http2.headers.authority','http2.headers.path']
 cmd=[exe,'-r',str(pcap)]
 if keylog:cmd += ['-o',f'tls.keylog_file:{keylog}']
 cmd += ['-T','fields','-E','separator=\\t','-E','occurrence=f']
 for f in fields:cmd += ['-e',f]
 p=subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=90)
 if p.returncode!=0:raise ValueError('tshark failed: '+(p.stderr or '').strip()[:400])
 known={norm_host(h) for h in hosts};out=[];seen=set()
 for line in p.stdout.splitlines():
  c=line.split('\t');c += ['']*(len(fields)-len(c));d=dict(zip(fields,c))
  try:frame=int((d['frame.number'] or '0').split(',')[0]);ms=int(float((d['frame.time_epoch'] or '0').split(',')[0])*1000)
  except:continue
  dns_resp=(d['dns.flags.response'] or '').split(',')[0].strip();dns=[norm_host(x) for x in re.split(r'[,;]',d['dns.qry.name'] or '') if norm_host(x)]
  sni=[norm_host(x) for x in re.split(r'[,;]',d['tls.handshake.extensions_server_name'] or '') if norm_host(x)]
  tls_types={x.strip() for x in re.split(r'[,;]',d['tls.handshake.type'] or '') if x.strip()}
  http_host=norm_host(d['http.host']);h2_host=norm_host(d['http2.headers.authority'])
  method=(d['http.request.method'] or '').split(',')[0].strip();h2method=(d['http2.headers.method'] or '').split(',')[0].strip()
  uri=(d['http.request.uri'] or '').split(',')[0].strip();h2path=(d['http2.headers.path'] or '').split(',')[0].strip()
  candidates=[]
  if dns_resp in ('0','False','false','0x0000',''):
   candidates += [('DNS_QUERY',h,None,None) for h in dns]
  if '1' in tls_types or '0x0001' in tls_types:
   candidates += [('TLS_CLIENT_HELLO',h,None,None) for h in sni]
  if method and http_host:candidates.append(('HTTP_REQUEST',http_host,method,uri or None))
  if h2method and h2_host:candidates.append(('HTTP2_REQUEST',h2_host,h2method,h2path or None))
  for typ,h,m,path in candidates:
   if h not in known:continue
   k=(frame,typ,h,m,path)
   if k in seen:continue
   seen.add(k);out.append({'frame_number':frame,'epoch_ms':ms,'marker_type':typ,'host':h,'method':m,'path':None if not path else path.split('?',1)[0][:240]})
 return sorted(out,key=lambda x:(x['epoch_ms'],x['frame_number'],x['marker_type'],x['host']))

def ground_truth_match(native,scan):
 details=[];matched_hosts=set()
 byhost={}
 for x in scan:byhost.setdefault(x['host'],[]).append(x)
 for row in native:
  h=row['host'];proto=(row['proto'] or '').upper();want={'DNS_QUERY'} if proto=='DNS' else {'TLS_CLIENT_HELLO','HTTP_REQUEST','HTTP2_REQUEST'}
  cand=[x for x in byhost.get(h,[]) if x['marker_type'] in want]
  if cand:
   best=min(cand,key=lambda x:abs(x['epoch_ms']-row['first_seen_epoch_ms']));delta=best['epoch_ms']-row['first_seen_epoch_ms'];ok=abs(delta)<=5000
   if ok:matched_hosts.add(h)
   details.append({'host':h,'native_proto':proto,'native_first_seen_epoch_ms':row['first_seen_epoch_ms'],'scanner_marker_type':best['marker_type'],'scanner_epoch_ms':best['epoch_ms'],'delta_ms':delta,'within_5s':ok})
  else:details.append({'host':h,'native_proto':proto,'native_first_seen_epoch_ms':row['first_seen_epoch_ms'],'scanner_marker_type':None,'scanner_epoch_ms':None,'delta_ms':None,'within_5s':False})
 unique_hosts=sorted(set(x['host'] for x in native));coverage=len(matched_hosts)/len(unique_hosts) if unique_hosts else 0.0
 return details,sorted(matched_hosts),unique_hosts,coverage

def timeline(r333):
 raw=r333/'raw';marks=rows_jsonl(raw/'host-timeline-private.jsonl');md={x.get('name'):x.get('host_epoch_ms') for x in marks if x.get('kind')=='host_marker'};coll=read_json(raw/'collector-summary-private.json');ev=coll.get('event_first_seen_host_epoch_ms',{}) if isinstance(coll.get('event_first_seen_host_epoch_ms'),dict) else {}
 out={'pcap_start':md.get('pcapdroid_capture_start'),'hi_force_stop':md.get('hi_force_stop_issued'),'hi_absence':md.get('hi_absence_proven'),'button_prompt':md.get('button2_now_prompt'),'button_done':md.get('button2_operator_done'),'connection_attempt':ev.get('connection_attempt_started'),'hi_respawn':coll.get('first_hi_respawn_host_epoch_ms'),'pcap_stop':md.get('pcapdroid_capture_stop')}
 for k in ('hi_force_stop','hi_absence','button_prompt','connection_attempt','hi_respawn'):
  if not isinstance(out.get(k),int):raise ValueError('r3.3.3 timeline missing '+k)
 return out

def ordering(a,b,a_name,b_name):
 if a is None or b is None:return 'UNRESOLVED_MISSING_TIMESTAMP'
 if a==b:return 'SAME_OBSERVATION_TIMESTAMP'
 return a_name+'_PRECEDES_'+b_name if a<b else b_name+'_PRECEDES_'+a_name

def phase(ms,t):
 if ms<t['hi_force_stop']:return 'PRE_FORCE_STOP'
 if ms<t['button_prompt']:return 'FORCE_STOP_TO_BUTTON_PROMPT'
 boundary=min(t['connection_attempt'],t['hi_respawn'])
 if ms<boundary:return 'BUTTON_PROMPT_TO_CONNECTION_RESPAWN_BOUNDARY'
 if ms==boundary:return 'CONNECTION_RESPAWN_BOUNDARY_TIMESTAMP'
 return 'POST_CONNECTION_RESPAWN_BOUNDARY'

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--r333-evidence',required=True);ap.add_argument('--r3331-evidence',required=True);ap.add_argument('--native-csv',required=True);ap.add_argument('--output',required=True);a=ap.parse_args()
 r333=Path(a.r333_evidence);r3331=Path(a.r3331_evidence);csvp=Path(a.native_csv);out=Path(a.output);priv=out/'private';san=out/'sanitized';priv.mkdir(parents=True,exist_ok=True);san.mkdir(parents=True,exist_ok=True)
 try:
  if not csvp.is_file() or not csvp.stat().st_size:raise ValueError('native CSV missing/empty')
  src,native=native_csv(csvp);known=sorted(set(x['host'] for x in native));rokid=sorted(h for h in known if h=='rokid.com' or h.endswith('.rokid.com'))
  if not rokid:raise ValueError('native CSV contains no *.rokid.com ground-truth hosts')
  p1=find_one(r3331,'*-private.pcap');k1=find_one(r3331,'*-private.sslkeylog',False);scan1=tshark_scan(p1,k1,known);cal,matched,unique,coverage=ground_truth_match(native,scan1)
  p0=find_one(r333,'*-private.pcap');k0=find_one(r333,'*-private.sslkeylog',False);scan0=tshark_scan(p0,k0,known);t=timeline(r333)
  known_r=[x for x in scan0 if x['host'] in rokid and x['marker_type'] in INIT_TYPES];after=[x for x in known_r if x['epoch_ms']>=t['hi_force_stop']];preprompt=[x for x in after if x['epoch_ms']<t['button_prompt']];first=after[0] if after else None
  conn_resp=ordering(t['connection_attempt'],t['hi_respawn'],'CONNECTION','RESPAWN')
  if first is None:netdisp='NO_KNOWN_ROKID_ENDPOINT_INITIATION_AFTER_FORCE'
  elif first['epoch_ms']<t['hi_respawn']:netdisp='KNOWN_ROKID_ENDPOINT_INITIATION_PRECEDES_RESPAWN'
  elif first['epoch_ms']==t['hi_respawn']:netdisp='KNOWN_ROKID_ENDPOINT_INITIATION_SAME_OBSERVATION_TIMESTAMP_AS_RESPAWN'
  else:netdisp='RESPAWN_PRECEDES_KNOWN_ROKID_ENDPOINT_INITIATION'
  if preprompt:server='KNOWN_ROKID_ENDPOINT_INITIATION_BEFORE_BUTTON_PROMPT_CORRELATION'
  elif first is not None and first['epoch_ms']<t['hi_respawn']:server='KNOWN_ROKID_ENDPOINT_INITIATION_PRE_RESPAWN_BUT_NOT_PRE_BUTTON_PROMPT'
  else:server='NO_PRE_RESPAWN_SERVER_INITIATION_SIGNAL_OBSERVED'
  safe_native=[{k:x[k] for k in ('app','package','proto','status','host','bytes_sent','bytes_received','packets_sent','packets_received','first_seen_epoch_ms','last_seen_epoch_ms')} for x in native]
  safe_scan=[]
  for x in scan0:
   if x['host'] not in known:continue
   y=dict(x);y['phase']=phase(x['epoch_ms'],t);safe_scan.append(y)
  (san/'native-csv-ground-truth-sanitized.jsonl').write_text(''.join(json.dumps(x,sort_keys=True)+'\n' for x in safe_native))
  (san/'r333-known-endpoint-timeline-sanitized.jsonl').write_text(''.join(json.dumps(x,sort_keys=True)+'\n' for x in safe_scan))
  (san/'scanner-ground-truth-calibration-sanitized.json').write_text(json.dumps({'native_unique_hosts':unique,'matched_hosts_within_5s':matched,'coverage_fraction':coverage,'rows':cal},indent=2,sort_keys=True)+'\n')
  summary={'schema':'rokid.test21-r3-3-3-2.sanitized-summary.v1','analysis':'PASS','mode':'OFFLINE_EXISTING_EVIDENCE_ONLY','native_csv_rows':len(src),'native_hi_rokid_rows':len(native),'native_known_hosts':known,'native_rokid_hosts':rokid,'scanner_ground_truth_unique_hosts':len(unique),'scanner_ground_truth_matched_hosts_within_5s':len(matched),'scanner_ground_truth_coverage_fraction':coverage,'scanner_ground_truth_disposition':'QUALIFIED' if coverage>=0.75 else ('PARTIAL' if coverage>0 else 'NOT_QUALIFIED'),'r333_known_endpoint_marker_rows':len(safe_scan),'r333_known_rokid_initiation_rows_after_force':len(after),'r333_known_rokid_initiation_rows_before_button_prompt':len(preprompt),'first_known_rokid_initiation_after_force':first,'connection_attempt_epoch_ms':t['connection_attempt'],'hi_respawn_epoch_ms':t['hi_respawn'],'connection_respawn_ordering':conn_resp,'network_respawn_disposition':netdisp,'server_dependency_interpretation':server,'causality_claim':'CORRELATION_ONLY_NOT_CAUSATION','device_operation':'NONE','new_capture':'NONE','photo_operation':'NONE','audio_operation':'NONE'}
  (san/'test21-r3-3-3-2-summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
  lines=['TEST21_R3_3_3_2_ANALYSIS=PASS','MODE=OFFLINE_EXISTING_EVIDENCE_ONLY',f'NATIVE_CSV_ROWS={len(src)}',f'NATIVE_HI_ROKID_ROWS={len(native)}','NATIVE_KNOWN_HOSTS='+','.join(known),'NATIVE_ROKID_HOSTS='+','.join(rokid),f'SCANNER_GROUND_TRUTH_DISPOSITION={summary["scanner_ground_truth_disposition"]}',f'SCANNER_GROUND_TRUTH_MATCHED_HOSTS={len(matched)}/{len(unique)}',f'R333_KNOWN_ROKID_INITIATION_ROWS_AFTER_FORCE={len(after)}',f'R333_KNOWN_ROKID_INITIATION_ROWS_BEFORE_BUTTON_PROMPT={len(preprompt)}',f'FIRST_KNOWN_ROKID_INITIATION_AFTER_FORCE_EPOCH_MS={first["epoch_ms"] if first else "NONE"}',f'FIRST_KNOWN_ROKID_INITIATION_HOST={first["host"] if first else "NONE"}',f'FIRST_KNOWN_ROKID_INITIATION_TYPE={first["marker_type"] if first else "NONE"}',f'CONNECTION_ATTEMPT_EPOCH_MS={t["connection_attempt"]}',f'HI_RESPAWN_EPOCH_MS={t["hi_respawn"]}',f'CONNECTION_RESPAWN_ORDERING={conn_resp}',f'NETWORK_RESPAWN_DISPOSITION={netdisp}',f'SERVER_DEPENDENCY_INTERPRETATION={server}','NETWORK_CAUSALITY=CORRELATION_ONLY_NOT_CAUSATION','DEVICE_OPERATION=NONE','NEW_CAPTURE=NONE','PHOTO_OPERATION=NONE','AUDIO_OPERATION=NONE']
  (san/'test21-r3-3-3-2-summary.txt').write_text('\n'.join(lines)+'\n');print('\n'.join(lines));return 0
 except Exception as ex:
  print('ERROR:',ex);print('TEST21_R3_3_3_2_ANALYSIS=FAIL');return 1
if __name__=='__main__':raise SystemExit(main())
