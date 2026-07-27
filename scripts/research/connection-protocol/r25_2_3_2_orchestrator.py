#!/usr/bin/env python3
"""R25.2.3.2 strict-handoff orchestration and bounded HCI capture."""
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, os, pty, re, shutil, signal, subprocess, sys, time, xml.etree.ElementTree as ET, zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import r25_2_3_2_capture as capture
import r25_2_3_2_hci_preflight as hci_preflight

UTC=dt.timezone.utc
APP_PACKAGE='org.aimindseye.rokid.channelprobe'
STRICT_RUNNER_REL='scripts/research/connection-protocol/run_r1_3_3_2_25_2_2_2.sh'
DEFAULT_SOURCE_SHA256='108d2330cf3ee85b791eec2b5e27118a14c731af26d12a8807a74b371414b82b'
BUTTON_RE=re.compile(r'(?i)open\s+rfcomm\s+socket')
READY_RE=re.compile(r'(?i)private\s+handoff.{0,80}(?:ready|accepted|valid)|(?:ready|accepted|valid).{0,80}private\s+handoff')
NEGATIVE_PATTERNS={
 'missing_or_invalid':re.compile(r'(?i)private\s+handoff.{0,80}(?:missing|invalid)'),
 'rejected':re.compile(r'(?i)private\s+handoff.{0,80}rejected'),
 'stale_or_expired':re.compile(r'(?i)private\s+handoff.{0,80}(?:stale|expired)'),
 'mismatched':re.compile(r'(?i)private\s+handoff.{0,80}mismatch'),
 'revoked':re.compile(r'(?i)private\s+handoff.{0,80}revoked'),
}

class Failure(RuntimeError): pass

def sha256_file(path:Path)->str:
 h=hashlib.sha256()
 with path.open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
 return h.hexdigest()

def run(cmd:Sequence[str], *, check=True, timeout=None, env=None):
 p=subprocess.run(list(map(str,cmd)),check=False,text=True,timeout=timeout,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 if check and p.returncode!=0:
  raise Failure(f"command failed rc={p.returncode}: {' '.join(map(str,cmd))}\n{p.stderr or ''}")
 return p

class Device:
 def __init__(self,adb:str,serial:str): self.adb=adb;self.serial=serial
 def cmd(self,*args,check=True,timeout=None): return run([self.adb,'-s',self.serial,*args],check=check,timeout=timeout)
 def shell(self,*args,check=True,timeout=None): return self.cmd('shell',*args,check=check,timeout=timeout)
 def epoch(self)->int:
  v=self.shell('date','+%s').stdout.strip().splitlines()[-1]
  if not re.fullmatch(r'\d{10,}',v): raise Failure(f'invalid phone epoch: {v!r}')
  return int(v)
 def force_stop(self): self.shell('am','force-stop',APP_PACKAGE,check=False)
 def launch(self): self.shell('monkey','-p',APP_PACKAGE,'-c','android.intent.category.LAUNCHER','1',check=False)
 def dump_ui(self,local:Path,label:str)->Dict[str,Any]:
  remote=f'/sdcard/r25_2_3_2_ui_{os.getpid()}.xml'
  self.shell('uiautomator','dump',remote,check=False,timeout=15)
  p=self.cmd('exec-out','cat',remote,check=False,timeout=10)
  self.shell('rm','-f',remote,check=False)
  raw=p.stdout or ''
  local.parent.mkdir(parents=True,exist_ok=True);local.write_text(raw,encoding='utf-8',errors='replace')
  return classify_ui(raw,label)

def classify_ui(xml_text:str,label='ui')->Dict[str,Any]:
 texts=[];buttons=[];parse_error=None
 try:
  root=ET.fromstring(xml_text)
  for node in root.iter():
   vals=[node.attrib.get('text',''),node.attrib.get('content-desc','')]
   for value in vals:
    value=value.strip()
    if value:texts.append(value)
   joined=' '.join(vals)
   if BUTTON_RE.search(joined):
    buttons.append({'text':joined.strip(),'enabled':node.attrib.get('enabled','').lower()=='true','clickable':node.attrib.get('clickable','').lower()=='true','bounds':node.attrib.get('bounds','')})
 except Exception as exc: parse_error=f'{type(exc).__name__}:{exc}'
 corpus='\n'.join(texts)
 negatives=[name for name,pat in NEGATIVE_PATTERNS.items() if pat.search(corpus)]
 explicit=bool(READY_RE.search(corpus));enabled=[b for b in buttons if b['enabled'] and b['clickable']]
 ready=parse_error is None and len(buttons)==1 and len(enabled)==1 and explicit and not negatives
 revoked=parse_error is None and len(buttons)==1 and len(enabled)==0 and bool(set(negatives)&{'missing_or_invalid','stale_or_expired','revoked'})
 return {'label':label,'parse_error':parse_error,'button_count':len(buttons),'enabled_button_count':len(enabled),'buttons':buttons,'explicit_private_handoff_ready':explicit,'negative_states':negatives,'ready':ready,'revoked_or_invalid':revoked,'texts':texts}

def iso_epoch(epoch:int)->str:
 return dt.datetime.fromtimestamp(epoch,tz=UTC).isoformat(timespec='seconds').replace('+00:00','Z')

def lifecycle_progress(path:Path,start_epoch:int)->Dict[str,Any]:
 connects=set();opens=set();closes=set()
 if not path.exists():return {'connect_count':0,'open_count':0,'close_count':0}
 for line in path.read_text(encoding='utf-8',errors='replace').splitlines():
  m=re.match(r'^\s*(\d{10}(?:\.\d+)?)\s+',line)
  if not m or float(m.group(1))<start_epoch-0.5:continue
  canonical=re.sub(r'^\s*\d{10}(?:\.\d+)?\s+(?:\d+\s+){2,4}[VDIWEF]\s+[^:]+:\s*','',line).strip().lower();key=(round(float(m.group(1)),3),canonical)
  if 'connectsocket' in canonical and 'from uid/pid' in canonical:connects.add(key)
  if 'rfc_port_event_open' in canonical or 'on_cli_rfc_connect' in canonical:opens.add(key)
  if 'rfc_port_event_close' in canonical or 'port_rfc_closed' in canonical or 'bta_jv_rfcomm_close' in canonical:closes.add(key)
 return {'connect_count':len(connects),'open_count':len(opens),'close_count':len(closes)}

class StrictSession:
 def __init__(self,cmd:List[str],log_path:Path,env:Dict[str,str]):
  self.master,self.slave=pty.openpty();log_path.parent.mkdir(parents=True,exist_ok=True);self.log=log_path.open('wb')
  self.proc=subprocess.Popen(cmd,stdin=self.slave,stdout=self.slave,stderr=self.slave,preexec_fn=os.setsid,close_fds=True,env=env)
  os.close(self.slave);os.set_blocking(self.master,False);self.buffer='';self.sent=set()
 def pump(self,echo=True):
  while True:
   try:data=os.read(self.master,65536)
   except (BlockingIOError,OSError):break
   if not data:break
   self.log.write(data);self.log.flush();text=data.decode('utf-8','replace');self.buffer+=text
   if len(self.buffer)>200000:self.buffer=self.buffer[-200000:]
   if echo:sys.stdout.write(text);sys.stdout.flush()
 def send_enter(self,reason:str): os.write(self.master,b'\n');self.sent.add(reason)
 def safe_setup_prompts(self,ui_ready:bool):
  for m in re.finditer(r'(?i)([^\r\n]{0,180}(?:press\s+enter|hit\s+enter)[^\r\n]{0,180})',self.buffer[-6000:]):
   prompt=' '.join(m.group(1).split()).lower()
   if prompt in self.sent:continue
   if any(x in prompt for x in ('tap','socket','connection-only','after the single attempt','after the socket','return to terminal')):continue
   if ('handoff' in prompt or 'reports ready' in prompt) and not ui_ready:continue
   if any(x in prompt for x in ('confirm','continue','proceed','disabled','hi rokid','precondition','ready')):self.send_enter(prompt)
 def finish(self,timeout:float):
  deadline=time.monotonic()+timeout;enters=0
  while time.monotonic()<deadline:
   self.pump();rc=self.proc.poll()
   if rc is not None:self.close();return rc
   tail=self.buffer[-1200:].lower()
   if ('press enter' in tail or 'return to terminal' in tail) and enters<6:self.send_enter(f'final-{enters}');enters+=1
   time.sleep(.2)
  self.terminate();raise Failure('strict r25.2.2.2 runner did not exit after attempt')
 def terminate(self):
  if self.proc.poll() is None:
   try:os.killpg(os.getpgid(self.proc.pid),signal.SIGTERM)
   except ProcessLookupError:pass
   try:self.proc.wait(timeout=3)
   except subprocess.TimeoutExpired:
    try:os.killpg(os.getpgid(self.proc.pid),signal.SIGKILL)
    except ProcessLookupError:pass
    self.proc.wait(timeout=3)
  self.close()
 def close(self):
  try:self.pump(echo=False)
  except Exception:pass
  try:os.close(self.master)
  except OSError:pass
  if not self.log.closed:self.log.close()

def package_tree(root:Path,dest:Path,manifest_name:str):
 lines=[]
 for p in sorted(root.rglob('*')):
  if p.is_file() and p.name!=manifest_name:lines.append(f'{sha256_file(p)}  {p.relative_to(root).as_posix()}')
 (root/manifest_name).write_text('\n'.join(lines)+'\n',encoding='utf-8')
 with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for p in sorted(root.rglob('*')):
   if p.is_symlink():raise Failure(f'symlink rejected: {p}')
   if p.is_file():z.write(p,p.relative_to(root.parent).as_posix())

def augment_results(analysis:Path,orchestration:Dict[str,Any]):
 private_path=analysis/'analysis/r25.2.3.2-private-analysis.json';public_path=analysis/'publication/r25.2.3.2-runtime-status-summary.json'
 private=json.loads(private_path.read_text());private['strict_handoff_orchestration']=orchestration;private_path.write_text(json.dumps(private,indent=2,sort_keys=True)+'\n')
 public=json.loads(public_path.read_text());public['strict_handoff_orchestration']={k:v for k,v in orchestration.items() if k not in {'strict_runner_output_path','baseline_ui_texts','ready_ui_texts','revoked_ui_texts'}};public_path.write_text(json.dumps(public,indent=2,sort_keys=True)+'\n')
 md=analysis/'publication/r25.2.3.2-instrumented-rfcomm-hci-zero-payload.md'
 with md.open('a',encoding='utf-8') as f:f.write('\n## Strict private-handoff orchestration\n\n- Accepted r25.2.2.2 host runner invoked: YES\n- Fresh disabled-button baseline observed: YES\n- Private handoff readiness attested before interval: YES\n- RFCOMM button enabled before interval: YES\n- Exactly one connect request observed: YES\n- HCI bugreport collected after close: YES\n- Probe force-stopped after bugreport: YES\n- Private handoff revoked or invalidated after attempt: YES\n')

def main(argv:Optional[Sequence[str]]=None)->int:
 ap=argparse.ArgumentParser()
 ap.add_argument('--repo',type=Path,required=True);ap.add_argument('--source-private-zip',type=Path,required=True);ap.add_argument('--phone-serial',required=True);ap.add_argument('--output',type=Path,required=True)
 ap.add_argument('--adb',default=os.environ.get('ADB','adb'));ap.add_argument('--strict-runner',type=Path);ap.add_argument('--expected-source-sha256',default=DEFAULT_SOURCE_SHA256)
 ap.add_argument('--readiness-timeout-seconds',type=float,default=float(os.environ.get('R25_2_3_2_READINESS_TIMEOUT_SECONDS','120')));ap.add_argument('--tap-timeout-seconds',type=float,default=float(os.environ.get('R25_2_3_2_TAP_TIMEOUT_SECONDS','90')));ap.add_argument('--close-timeout-seconds',type=float,default=float(os.environ.get('R25_2_3_2_CLOSE_TIMEOUT_SECONDS','40')));ap.add_argument('--strict-exit-timeout-seconds',type=float,default=float(os.environ.get('R25_2_3_2_STRICT_EXIT_TIMEOUT_SECONDS','120')))
 args=ap.parse_args(argv);repo=args.repo.expanduser().resolve();source=args.source_private_zip.expanduser().resolve();out=args.output.expanduser().resolve();strict=(args.strict_runner.expanduser().resolve() if args.strict_runner else repo/STRICT_RUNNER_REL)
 if out.exists():raise Failure(f'output already exists: {out}')
 if not source.is_file():raise Failure(f'source private ZIP not found: {source}')
 actual_source=sha256_file(source)
 if actual_source.lower()!=args.expected_source_sha256.lower():raise Failure(f'source private ZIP SHA-256 mismatch: expected {args.expected_source_sha256}, got {actual_source}')
 if not strict.is_file():raise Failure(f'accepted strict runner missing: {strict}')
 if not repo.is_dir():raise Failure(f'repository missing: {repo}')
 if shutil.which(args.adb) is None and not Path(args.adb).is_file():raise Failure(f'adb not found: {args.adb}')
 dev=Device(args.adb,args.phone_serial)
 if dev.cmd('get-state',check=False).stdout.strip()!='device':raise Failure('phone is not available through ADB')
 if not dev.shell('pm','path',APP_PACKAGE,check=False).stdout.strip().startswith('package:'):raise Failure(f'probe package not installed: {APP_PACKAGE}')
 out.mkdir(parents=True);evidence=out/'private-evidence';analysis=out/'private-analysis';publication=analysis/'publication';strict_out=out/'strict-r25.2.2.2';evidence.mkdir();analysis.mkdir();(evidence/'ui').mkdir();(evidence/'strict-runner').mkdir();(evidence/'hci-preflight').mkdir()
 aborted=out/'ABORTED.txt';sessions=[];logcat_proc=None
 def abort_handler(signum,frame):
  aborted.write_text(f'ABORTED_BY_SIGNAL={signum}\n',encoding='utf-8')
  if logcat_proc and logcat_proc.poll() is None:
   try:os.killpg(os.getpgid(logcat_proc.pid),signal.SIGTERM)
   except Exception:pass
  for s in sessions:
   try:s.terminate()
   except Exception:pass
  try:dev.force_stop()
  except Exception:pass
  raise SystemExit(128+signum)
 signal.signal(signal.SIGINT,abort_handler);signal.signal(signal.SIGTERM,abort_handler)
 probes={'secure_bluetooth_hci_log':dev.shell('settings','get','secure','bluetooth_hci_log',check=False).stdout.strip(),'global_btsnoop_default_mode':dev.shell('settings','get','global','bluetooth_btsnoop_default_mode',check=False).stdout.strip(),'persist_btsnooplogmode':dev.shell('getprop','persist.bluetooth.btsnooplogmode',check=False).stdout.strip(),'persist_btsnoopdefaultmode':dev.shell('getprop','persist.bluetooth.btsnoopdefaultmode',check=False).stdout.strip(),'persist_btsnoopenable':dev.shell('getprop','persist.bluetooth.btsnoopenable',check=False).stdout.strip(),'dumpsys_bluetooth':dev.shell('dumpsys','bluetooth_manager',check=False).stdout}
 pre=hci_preflight.classify(probes);(evidence/'hci-preflight/probes.json').write_text(json.dumps(probes,indent=2,sort_keys=True)+'\n');(evidence/'hci-preflight/result.json').write_text(json.dumps(pre,indent=2,sort_keys=True)+'\n')
 print(f"R25_2_3_2_HCI_PREFLIGHT_STATUS={pre['status']}");print(f"R25_2_3_2_HCI_CAPTURE_ALLOWED={'YES' if pre['capture_allowed'] else 'NO'}")
 if not pre['capture_allowed']:raise Failure(f"HCI preflight rejected capture: {pre['status']}")
 dev.force_stop();dev.launch();time.sleep(float(os.environ.get('R25_2_3_2_UI_SETTLE_SECONDS','1')))
 baseline=dev.dump_ui(evidence/'ui/00-baseline-disabled.xml','baseline');(evidence/'ui/00-baseline-disabled.json').write_text(json.dumps(baseline,indent=2,sort_keys=True)+'\n')
 if baseline['ready'] or baseline['enabled_button_count']:raise Failure('preexisting valid/enabled handoff detected; refusing stale handoff reuse')
 if not baseline['revoked_or_invalid']:raise Failure('disabled-button regression baseline not attested: expected private handoff missing/invalid and disabled button')
 dev.force_stop()
 strict_cmd=['bash',str(strict),'--repo',str(repo),'--source-private-zip',str(source),'--output',str(strict_out),'--phone-serial',args.phone_serial]
 (evidence/'strict-runner/command-private.json').write_text(json.dumps({'runner':str(strict),'runner_sha256':sha256_file(strict),'source_private_zip_sha256':actual_source,'argv':strict_cmd[1:]},indent=2,sort_keys=True)+'\n')
 session=StrictSession(strict_cmd,evidence/'strict-runner/runner-terminal-private.txt',os.environ.copy());sessions.append(session)
 ready=None;deadline=time.monotonic()+args.readiness_timeout_seconds;last_dump=0
 while time.monotonic()<deadline:
  session.pump();session.safe_setup_prompts(bool(ready and ready['ready']))
  if session.proc.poll() is not None:raise Failure(f'strict runner exited before readiness: rc={session.proc.returncode}')
  if time.monotonic()-last_dump>.5:
   candidate=dev.dump_ui(evidence/'ui/01-readiness-probe-latest.xml','ready-probe');last_dump=time.monotonic()
   if candidate['negative_states'] and any(x in candidate['negative_states'] for x in ('rejected','stale_or_expired','mismatched')):raise Failure(f"strict handoff rejected: {candidate['negative_states']}")
   if candidate['ready']:
    ready=candidate;(evidence/'ui/01-ready-attested.xml').write_text((evidence/'ui/01-readiness-probe-latest.xml').read_text(),encoding='utf-8');(evidence/'ui/01-ready-attested.json').write_text(json.dumps(ready,indent=2,sort_keys=True)+'\n');break
  time.sleep(.2)
 if not ready:raise Failure('strict private handoff readiness and enabled button were not attested before timeout')
 session.pump();session.safe_setup_prompts(True);time.sleep(.5)
 still_ready=dev.dump_ui(evidence/'ui/02-ready-before-interval.xml','ready-before-interval')
 if not still_ready['ready']:raise Failure('probe lost ready/enabled state before measured interval')
 print('R25_2_3_2_STRICT_RUNNER_REUSED=YES');print('R25_2_3_2_PRIVATE_HANDOFF_READY=YES');print('R25_2_3_2_RFCOMM_BUTTON_ENABLED=YES')
 (evidence/'getprop-before.txt').write_text(dev.shell('getprop',check=False).stdout);(evidence/'dumpsys-bluetooth-before.txt').write_text(dev.shell('dumpsys','bluetooth_manager',check=False).stdout)
 log_path=evidence/'logcat-all-epoch.txt';log_err=(evidence/'logcat.stderr.txt').open('wb');log_out=log_path.open('wb');logcat_proc=subprocess.Popen([args.adb,'-s',args.phone_serial,'logcat','-b','all','-v','epoch'],stdout=log_out,stderr=log_err,preexec_fn=os.setsid)
 time.sleep(float(os.environ.get('R25_2_3_2_LOGCAT_STARTUP_SECONDS','1')))
 if logcat_proc.poll() is not None:raise Failure('bounded logcat process exited before attempt')
 start_epoch=dev.epoch();start_utc=iso_epoch(start_epoch)
 print('\nSTRICT HANDOFF READY — MEASURED INTERVAL STARTED\nTap OPEN RFCOMM SOCKET — ZERO PAYLOAD exactly once now.\nDo not type, speak, stream, or tap the button a second time.\nThe host will detect the explicit transport close automatically.\n')
 first_deadline=time.monotonic()+args.tap_timeout_seconds;connected=False;close_deadline=None;progress={}
 while True:
  session.pump()
  if session.proc.poll() is not None:raise Failure('strict runner exited during measured attempt')
  progress=lifecycle_progress(log_path,start_epoch)
  if progress['connect_count']>1:raise Failure(f"more than one RFCOMM connect request observed: {progress['connect_count']}")
  if progress['connect_count']==1 and not connected:connected=True;close_deadline=time.monotonic()+args.close_timeout_seconds;print('R25_2_3_2_SINGLE_TAP_CONNECT_DETECTED=YES')
  if connected and progress['close_count']>=1:break
  if not connected and time.monotonic()>first_deadline:raise Failure('no RFCOMM connect request observed before tap timeout')
  if connected and close_deadline and time.monotonic()>close_deadline:raise Failure('RFCOMM connect observed but explicit close was not observed')
  time.sleep(.2)
 time.sleep(float(os.environ.get('R25_2_3_2_POST_CLOSE_SECONDS','1')));progress=lifecycle_progress(log_path,start_epoch)
 if progress['connect_count']!=1:raise Failure(f"single-tap gate failed: connect_count={progress['connect_count']}")
 end_epoch=dev.epoch();end_utc=iso_epoch(end_epoch);os.killpg(os.getpgid(logcat_proc.pid),signal.SIGTERM)
 try:logcat_proc.wait(timeout=5)
 except subprocess.TimeoutExpired:os.killpg(os.getpgid(logcat_proc.pid),signal.SIGKILL);logcat_proc.wait(timeout=3)
 log_out.close();log_err.close();logcat_proc=None
 # Bugreport is collected after close and before handoff revocation.
 bug=evidence/'bugreport.zip';p=dev.cmd('bugreport',str(bug),check=False,timeout=300);(evidence/'bugreport.stdout.txt').write_text(p.stdout or '');(evidence/'bugreport.stderr.txt').write_text(p.stderr or '')
 if p.returncode!=0 or not bug.is_file() or bug.stat().st_size==0:raise Failure('post-close HCI bugreport was not created')
 print('R25_2_3_2_POST_CLOSE_BUGREPORT=PASS');dev.force_stop();print('R25_2_3_2_POST_BUGREPORT_PROBE_FORCE_STOP=PASS')
 metadata={'schema':'rokid.r25.2.3.2.capture-metadata.v1','release':'r1.3.3.2.25.2.3.2','attempt_id':f'r25-2-3-2-{int(time.time())}','interval_start_epoch':start_epoch,'interval_end_epoch':end_epoch,'interval_start_utc':start_utc,'interval_end_utc':end_utc,'phone_serial_sha256':hashlib.sha256(args.phone_serial.encode()).hexdigest(),'expected_dlci':6,'trigger_mode':'strict_private_handoff_single_manual_tap','hci_preflight':pre,'strict_runner_sha256':sha256_file(strict),'strict_source_private_zip_sha256':actual_source,'readiness_attested_before_interval':True,'button_enabled_before_interval':True,'connect_request_count':progress['connect_count'],'explicit_close_count':progress['close_count']}
 (evidence/'metadata.json').write_text(json.dumps(metadata,indent=2,sort_keys=True)+'\n');capture_result=capture.analyze(evidence,analysis)
 strict_rc=session.finish(args.strict_exit_timeout_seconds)
 if strict_rc!=0:raise Failure(f'accepted strict runner failed after attempt: rc={strict_rc}')
 (evidence/'strict-runner/exit.json').write_text(json.dumps({'exit_code':strict_rc,'output_sha256':sha256_file(evidence/'strict-runner/runner-terminal-private.txt')},indent=2)+'\n')
 dev.force_stop();dev.launch();time.sleep(float(os.environ.get('R25_2_3_2_UI_SETTLE_SECONDS','1')));revoked=dev.dump_ui(evidence/'ui/03-post-runner-revocation.xml','post-runner-revocation')
 if not revoked['revoked_or_invalid']:
  cleanup_script="find files cache shared_prefs -type f 2>/dev/null | while read f; do case \"$f\" in *handoff*|*rfcomm*|*connection_only*|*connection-only*) rm -f \"$f\";; esac; done"
  dev.shell('run-as',APP_PACKAGE,'sh','-c',cleanup_script,check=False);dev.force_stop();dev.launch();time.sleep(float(os.environ.get('R25_2_3_2_UI_SETTLE_SECONDS','1')));revoked=dev.dump_ui(evidence/'ui/04-post-targeted-revocation.xml','post-targeted-revocation')
 if not revoked['revoked_or_invalid']:raise Failure('private handoff remained ready/enabled after attempt; revocation not proven')
 dev.force_stop();print('R25_2_3_2_POST_ATTEMPT_HANDOFF_REVOCATION=PASS')
 orchestration={'schema':'rokid.r25.2.3.2.strict-handoff-orchestration.v1','strict_runner_invoked':True,'strict_runner_sha256':sha256_file(strict),'strict_runner_exit_code':strict_rc,'fresh_disabled_baseline_attested':True,'private_handoff_ready_before_interval':True,'rfcomm_button_enabled_before_interval':True,'interval_started_after_readiness':True,'single_connect_request_count':progress['connect_count'],'explicit_close_count':progress['close_count'],'bugreport_collected_after_close':True,'probe_force_stopped_after_bugreport':True,'post_attempt_handoff_revoked_or_invalid':True,'strict_runner_output_path':str(strict_out),'baseline_ui_texts':baseline['texts'],'ready_ui_texts':ready['texts'],'revoked_ui_texts':revoked['texts']}
 augment_results(analysis,orchestration)
 pub_hash=[]
 for q in sorted(publication.rglob('*')):
  if q.is_file() and q.name!='evidence-hashes.txt':pub_hash.append(f'{sha256_file(q)}  {q.relative_to(publication).as_posix()}')
 (publication/'evidence-hashes.txt').write_text('\n'.join(pub_hash)+'\n');package_tree(evidence,Path(str(out)+'-private-evidence.zip'),'SHA256SUMS-private.txt');package_tree(analysis,Path(str(out)+'-private-analysis.zip'),'SHA256SUMS-private-analysis.txt');package_tree(publication,Path(str(out)+'-sanitized-publication.zip'),'SHA256SUMS-sanitized.txt')
 selected=capture_result.get('selected_hci_census') or {};gates=capture_result['gates'];fields=capture_result.get('lifecycle',{}).get('fields',{})
 print('R25_2_3_2_ATTEMPT_COUNT=1');print('R25_2_3_2_SINGLE_TAP_GATE=PASS');print('R25_2_3_2_MATCHING_OPEN_CLOSE=YES');print(f"R25_2_3_2_HCI_POST_BUGREPORT_PARSEABLE={'YES' if capture_result.get('hci_member_census') else 'NO'}");print(f"R25_2_3_2_HCI_DLCI_LIFECYCLE={'YES' if selected.get('lifecycle_complete') else 'NO'}");print(f"R25_2_3_2_HCI_TX_PAYLOAD_BYTES={selected.get('tx_payload_bytes','UNRESOLVED')}");print(f"R25_2_3_2_HCI_RX_PAYLOAD_BYTES={selected.get('rx_payload_bytes','UNRESOLVED')}");print(f"R25_2_3_2_HCI_ZERO_PAYLOAD={'YES' if gates['hci_zero_payload_proven'] else 'NO'}")
 for key in ('uid','pid','slot','port_handle','scn','dlci','mtu'):print(f"R25_2_3_2_{key.upper()}={fields.get(key,'UNRESOLVED')}")
 print(f"R25_2_3_2_QUALIFICATION_OUTCOME={capture_result['qualification_outcome']}");print(f"R1_3_3_2_25_2_3_2_ACCEPTANCE={capture_result['acceptance']}")
 for suffix in ('-private-evidence.zip','-private-analysis.zip','-sanitized-publication.zip'):
  p=Path(str(out)+suffix);print(f'R25_2_3_2_ARTIFACT={p}');print(f'R25_2_3_2_ARTIFACT_SHA256={sha256_file(p)}')
 print(f'R25_2_3_2_OUTPUT={out}');return 0

if __name__=='__main__':
 try:raise SystemExit(main())
 except Failure as exc:print(f'R25_2_3_2_FAILURE={exc}',file=sys.stderr);raise SystemExit(1)
