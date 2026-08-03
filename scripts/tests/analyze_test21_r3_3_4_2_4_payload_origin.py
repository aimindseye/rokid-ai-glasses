#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, importlib.util, io, json, re, struct, zipfile
from pathlib import Path

HI_PACKAGE='com.rokid.sprite.global.aiapp'
SERVICE_DOT='com.rokid.sprite.aiapp.externalapp.service.CXRLinkService'
SERVICE_DESC='Lcom/rokid/sprite/aiapp/externalapp/service/CXRLinkService;'
MEDIA_DOT='com.rokid.sprite.aiapp.externalapp.IMediaStreamService'
MEDIA_DESC='Lcom/rokid/sprite/aiapp/externalapp/IMediaStreamService;'
STUB_DESC='Lcom/rokid/sprite/aiapp/externalapp/IMediaStreamService$Stub;'
PROXY_DESC='Lcom/rokid/sprite/aiapp/externalapp/IMediaStreamService$Stub$Proxy;'
ACTION='com.rokid.sprite.aiapp.externalapp.MEDIA_STREAM_SERVICE'
TARGETS=(SERVICE_DESC,MEDIA_DESC,STUB_DESC,PROXY_DESC)
TARGET_NEEDLES=(SERVICE_DOT,SERVICE_DESC,MEDIA_DOT,MEDIA_DESC,STUB_DESC,PROXY_DESC,ACTION)
LOADER_MARKERS=(
 'dalvik.system.DexClassLoader','dalvik.system.InMemoryDexClassLoader','dalvik.system.PathClassLoader',
 'dalvik.system.BaseDexClassLoader','dalvik.system.DexFile','DexFile.loadDex','loadDex','loadClass',
 'InMemoryDexClassLoader','DexClassLoader','BaseDexClassLoader','PathClassLoader',
 'java.lang.ClassLoader','System.loadLibrary','Runtime.loadLibrary','android_dlopen_ext','dlopen',
 'RegisterNatives','DefineClass','JNI_OnLoad')
PROTECTOR_MARKERS=('secneo','bangcle','ijiami','jiagu','dexprotector','appsealing','dexguard','packer','shell dex','encrypted dex')
ARCHIVE_EXT={'.apk','.jar','.zip','.xapk','.apks'}
CODE_EXT={'.dex','.apk','.jar','.zip','.odex','.vdex','.so','.bin','.dat','.pak'}
SKIP_MEDIA={'.png','.jpg','.jpeg','.webp','.gif','.mp4','.m4a','.mp3','.ogg','.wav','.ttf','.otf','.arsc'}
MAX_FULL=128*1024*1024
MAX_DEPTH=2


def sha256_bytes(data:bytes)->str:return hashlib.sha256(data).hexdigest()
def sha256_file(p:Path)->str:
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()

def load_prev(repo:Path):
 p=repo/'scripts/tests/analyze_test21_r3_3_4_2_3_code_origin.py'
 if not p.is_file():raise SystemExit('ERROR: prerequisite r3.3.4.2.3 analyzer missing')
 sp=importlib.util.spec_from_file_location('r33423',p);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m

def read_text(p:Path)->str:return p.read_text(errors='replace') if p.is_file() else ''

def sanitize_id(text:str)->str:
 text=re.sub(r'[^A-Za-z0-9_.:+@=-]+','_',text)
 return text[:180] or 'artifact'

def marker_hits_bytes(data:bytes, markers):
 low=data.lower();out=[]
 for m in markers:
  if m.encode().lower() in low:out.append(m)
 return out

def stream_marker_hits(zf:zipfile.ZipFile, info:zipfile.ZipInfo, markers):
 needles=[(m,m.encode().lower()) for m in markers];found=set();tail=b''
 try:
  with zf.open(info) as f:
   while True:
    b=f.read(1024*1024)
    if not b:break
    x=(tail+b).lower()
    for m,n in needles:
     if m not in found and n in x:found.add(m)
    tail=x[-512:]
 except Exception:return []
 return sorted(found)

def embedded_dex_slices(data:bytes):
 out=[];pos=0
 while True:
  off=data.find(b'dex\n',pos)
  if off<0:break
  if off+112<=len(data):
   try:
    version=data[off+4:off+7]
    fsize=struct.unpack_from('<I',data,off+32)[0];hsize=struct.unpack_from('<I',data,off+36)[0]
    if version.isdigit() and hsize==0x70 and 112<=fsize<=len(data)-off:
     out.append((off,data[off:off+fsize]))
   except Exception:pass
  pos=off+4
 return out

def try_nested_zip(data:bytes):
 try:
  bio=io.BytesIO(data)
  if zipfile.is_zipfile(bio):return bio
 except Exception:pass
 return None

def dex_scan(data:bytes,label:str,prev):
 hits,subs,err=prev.scan_dex_bytes(data,label,prev.load_dex_base(Path(prev.__file__).resolve().parents[2]).Dex) if False else (None,None,None)
 # Do not recursively load through prev. Use the same base parser directly from its repository later.
 return hits,subs,err

def scan_dex_with(Dex,data:bytes,label:str):
 result={t:{'class_defs':[],'type_refs':[],'string_refs':[],'raw_hits':[]} for t in TARGETS};subs=[];err=None
 for t in TARGETS:
  dot=t[1:-1].replace('/','.')
  if t.encode() in data or dot.encode() in data:result[t]['raw_hits'].append(label)
 try:
  d=Dex(data,label)
  for t in TARGETS:
   c=d.classes.get(t)
   if c:
    methods=[]
    for idx in c.get('methods') or []:
     try:
      m=d.methods[idx];methods.append({'name':m.get('name'),'proto':m.get('proto'),'ret':m.get('ret')})
     except Exception:pass
    result[t]['class_defs'].append({'label':label,'super':c.get('super'),'interfaces':c.get('interfaces') or [],'methods':methods})
   if t in d.types:result[t]['type_refs'].append(label)
   dot=t[1:-1].replace('/','.')
   if t in d.strings or dot in d.strings:result[t]['string_refs'].append(label)
  for desc,c in d.classes.items():
   if c.get('super')==STUB_DESC:subs.append({'label':label,'class':desc})
 except Exception as e:err=type(e).__name__+': '+str(e)[:180]
 return result,subs,err

def merge_dex(dst,src,origin):
 for t in TARGETS:
  for c in src[t]['class_defs']:dst[t]['class_defs'].append({'origin':origin,**c})
  for k in ('type_refs','string_refs','raw_hits'):
   if src[t][k]:dst[t][k].append(origin)

def shared_library_names(text:str):
 names=[];in_block=False
 for line in text.splitlines():
  low=line.lower();stripped=line.strip()
  header=any(x in low for x in ('useslibrar','shared librar','libraries:'))
  if header:in_block=True
  elif stripped and not line[:1].isspace() and not low.startswith('library:'):in_block=False
  if not (header or in_block or low.startswith('library:')):continue
  for tok in re.findall(r'[A-Za-z0-9_.-]{3,}',line):
   if any(k in tok.lower() for k in ('rokid','cxr','sprite','aiapp')) and tok not in names:names.append(tok)
 return names[:64]

def read_pull_manifest(path:Path,base:Path):
 rows=[]
 if not path.is_file():return rows
 for line in path.read_text(errors='replace').splitlines():
  if not line.strip() or line.startswith('KIND\t'):continue
  parts=line.split('\t')
  if len(parts)>=5 and parts[3]=='PASS':
   p=base/parts[2]
   if p.is_file():rows.append((parts[0],p,parts[1]))
 return rows

def inspect_container(path:Path, origin:str, Dex, recovered:Path):
 stats={'zip_entries':0,'non_dex_entries':0,'native_entries':0,'nested_archives':0,'embedded_dex':0,'embedded_archives':0,'skipped_media':0,'loader_markers':set(),'protector_markers':set(),'target_refs':set(),'native_target_refs':set(),'candidate_ids':set(),'dex_parse_errors':[]}
 dexagg={t:{'class_defs':[],'type_refs':[],'string_refs':[],'raw_hits':[]} for t in TARGETS};stubsubs=[]
 seen=set()
 def record_blob(data:bytes,label:str,depth:int,is_native=False):
  nonlocal stats,dexagg,stubsubs
  mh=marker_hits_bytes(data,LOADER_MARKERS);ph=marker_hits_bytes(data,PROTECTOR_MARKERS);th=marker_hits_bytes(data,TARGET_NEEDLES)
  stats['loader_markers'].update(mh);stats['protector_markers'].update(ph);stats['target_refs'].update(th)
  if is_native and th:stats['native_target_refs'].update(th)
  if th and (mh or ph or is_native):stats['candidate_ids'].add(sanitize_id(origin+'!'+label))
  if data.startswith(b'dex\n'):
   ds,ss,err=scan_dex_with(Dex,data,label);merge_dex(dexagg,ds,origin+'!'+label);stubsubs.extend({'origin':origin,**x} for x in ss)
   if err:stats['dex_parse_errors'].append(label+':'+err)
  if depth<MAX_DEPTH and len(data)<=MAX_FULL:
   for off,dd in embedded_dex_slices(data):
    key=(label,'dex',off,sha256_bytes(dd))
    if key in seen:continue
    seen.add(key);stats['embedded_dex']+=1
    rid=sanitize_id(origin+'!'+label+f'@dex{off}')+'.dex';rp=recovered/rid
    if not rp.exists():rp.write_bytes(dd)
    ds,ss,err=scan_dex_with(Dex,dd,label+f'@embedded-dex:{off}');merge_dex(dexagg,ds,origin+'!'+label+f'@embedded-dex:{off}');stubsubs.extend({'origin':origin,**x} for x in ss)
    if err:stats['dex_parse_errors'].append(label+f'@{off}:'+err)
   bio=try_nested_zip(data)
   if bio is not None and not label.lower().endswith(('.apk','.jar','.zip')):
    stats['embedded_archives']+=1
  return
 try:
  if zipfile.is_zipfile(path):
   with zipfile.ZipFile(path) as z:
    for info in z.infolist():
     if info.is_dir():continue
     stats['zip_entries']+=1;name=info.filename;ext=Path(name).suffix.lower()
     if ext=='.dex' or re.fullmatch(r'(?:.*/)?classes(?:\d+)?\.dex',name):
      try:data=z.read(info)
      except Exception:continue
      record_blob(data,name,0);continue
     stats['non_dex_entries']+=1
     if ext=='.so':stats['native_entries']+=1
     if ext in SKIP_MEDIA:
      stats['skipped_media']+=1;continue
     # For small/suspicious entries, full-read permits nested/embedded recovery. Large entries still receive streaming marker scan.
     full=(info.file_size<=MAX_FULL and (ext in CODE_EXT or ext=='' or info.file_size<=16*1024*1024))
     if full:
      try:data=z.read(info)
      except Exception:continue
      is_native=ext=='.so' or data.startswith(b'\x7fELF')
      record_blob(data,name,0,is_native)
      if len(data)>=4 and data[:4]==b'PK\x03\x04' and ext not in ('.apk','.jar','.zip'):
       stats['nested_archives']+=1
       if len(data)<=MAX_FULL:
        rid=sanitize_id(origin+'!'+name)+'.zip';rp=recovered/rid
        if not rp.exists():rp.write_bytes(data)
        try:
         with zipfile.ZipFile(io.BytesIO(data)) as nz:
          for ni in nz.infolist():
           if ni.is_dir() or ni.file_size>MAX_FULL:continue
           ne=Path(ni.filename).suffix.lower()
           if ne=='.dex' or re.fullmatch(r'(?:.*/)?classes(?:\d+)?\.dex',ni.filename):record_blob(nz.read(ni),name+'!'+ni.filename,1)
        except Exception:pass
     else:
      stats['loader_markers'].update(stream_marker_hits(z,info,LOADER_MARKERS));stats['protector_markers'].update(stream_marker_hits(z,info,PROTECTOR_MARKERS));tr=stream_marker_hits(z,info,TARGET_NEEDLES);stats['target_refs'].update(tr)
      if ext=='.so' and tr:stats['native_target_refs'].update(tr);stats['candidate_ids'].add(sanitize_id(origin+'!'+name))
  elif path.suffix.lower()=='.dex':record_blob(path.read_bytes(),path.name,0)
  else:
   data=path.read_bytes() if path.stat().st_size<=MAX_FULL else None
   if data is not None:record_blob(data,path.name,0,path.suffix.lower()=='.so' or data.startswith(b'\x7fELF'))
   else:
    # stream ordinary file marker scan
    found={};tail=b''
    with path.open('rb') as f:
     while True:
      b=f.read(1024*1024)
      if not b:break
      x=(tail+b).lower()
      for m in TARGET_NEEDLES+LOADER_MARKERS+PROTECTOR_MARKERS:
       if m.encode().lower() in x:found[m]=1
      tail=x[-512:]
    stats['target_refs'].update(m for m in TARGET_NEEDLES if m in found);stats['loader_markers'].update(m for m in LOADER_MARKERS if m in found);stats['protector_markers'].update(m for m in PROTECTOR_MARKERS if m in found)
 except Exception as e:stats['dex_parse_errors'].append('container:'+type(e).__name__+':'+str(e)[:160])
 for k in ('loader_markers','protector_markers','target_refs','native_target_refs','candidate_ids'):stats[k]=sorted(stats[k])
 return stats,dexagg,stubsubs

def first_origin(agg,target):
 a=agg[target]['class_defs'];return a[0]['origin'] if a else 'NOT_RECOVERED'

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--repo',required=True);ap.add_argument('--r3341-evidence',required=True);ap.add_argument('--r33423-evidence',required=True);ap.add_argument('--root-collection',required=True);ap.add_argument('--output',required=True)
 a=ap.parse_args();repo=Path(a.repo).resolve();r3341=Path(a.r3341_evidence).resolve();r33423=Path(a.r33423_evidence).resolve();root=Path(a.root_collection).resolve();out=Path(a.output).resolve();san=out/'sanitized';priv=out/'private';rec=priv/'recovered-payloads';san.mkdir(parents=True,exist_ok=True);rec.mkdir(parents=True,exist_ok=True)
 prev=load_prev(repo);Dex=prev.load_dex_base(repo).Dex
 artifacts=[];seen_hash=set()
 # Current PackageManager artifacts from r3.3.4.2.3 are primary.
 col=r33423/'private/device-origin-collection'
 for kind,p,remote in read_pull_manifest(col/'pull-manifest.tsv',col):
  h=sha256_file(p)
  if h not in seen_hash:seen_hash.add(h);artifacts.append((kind,p,Path(remote).name or p.name))
 # Preserved r3.3.4.1 APKs remain independent comparators.
 for p in sorted((r3341/'raw/apks').glob('hi-*.apk')):
  if p.is_file():
   h=sha256_file(p)
   if h not in seen_hash:seen_hash.add(h);artifacts.append(('PRESERVED_R3341',p,p.name))
 # Optional root-assisted recovered code artifacts.
 root_manifest=root/'root-pull-manifest.tsv'
 for kind,p,remote in read_pull_manifest(root_manifest,root):
  h=sha256_file(p)
  if h not in seen_hash:seen_hash.add(h);artifacts.append((kind,p,Path(remote).name or p.name))
 overall={t:{'class_defs':[],'type_refs':[],'string_refs':[],'raw_hits':[]} for t in TARGETS};stubsubs=[];records=[]
 totals={'zip_entries':0,'non_dex_entries':0,'native_entries':0,'nested_archives':0,'embedded_dex':0,'embedded_archives':0,'skipped_media':0}
 loader=set();protect=set();targets=set();native_targets=set();cands=set();errs=[]
 for idx,(kind,p,label) in enumerate(artifacts):
  oid=f'{kind}[{idx}]:{sanitize_id(label)}';stats,dex,subs=inspect_container(p,oid,Dex,rec)
  merge_dex(overall,dex,oid);stubsubs.extend(subs)
  for k in totals:totals[k]+=stats[k]
  loader.update(stats['loader_markers']);protect.update(stats['protector_markers']);targets.update(stats['target_refs']);native_targets.update(stats['native_target_refs']);cands.update(stats['candidate_ids']);errs.extend(stats['dex_parse_errors'])
  records.append({'origin_id':oid,'sha256':sha256_file(p),'size':p.stat().st_size,'kind':kind,'stats':stats})
 svc_origin=first_origin(overall,SERVICE_DESC);media_origin=first_origin(overall,MEDIA_DESC);stub_origin=first_origin(overall,STUB_DESC);proxy_origin=first_origin(overall,PROXY_DESC)
 onbind=[]
 for row in overall[SERVICE_DESC]['class_defs']:
  for m in row.get('methods') or []:
   if m.get('name')=='onBind':onbind.append({'origin':row['origin'],'proto':m.get('proto'),'ret':m.get('ret')})
 root_status=read_text(root/'root-status.txt').strip() or 'NOT_ATTEMPTED'
 root_maps=read_text(root/'root-process-maps-status.txt').strip() or 'NOT_ATTEMPTED'
 root_cands=len([x for x in read_text(root/'root-code-candidates.txt').splitlines() if x.strip()])
 root_rows=read_pull_manifest(root_manifest,root);root_pass=len(root_rows)
 shared=shared_library_names(read_text(col/'dumpsys-package.txt')+'\n'+read_text(col/'shared-libraries.txt'))
 # Reference-only/protected candidate is deliberately not exact origin proof.
 protected_candidate=bool(cands or (native_targets and (loader or protect)))
 exact=svc_origin!='NOT_RECOVERED'
 if exact:
  payload_origin='EXACT_DEX_CLASS_DEF:'+svc_origin;origin_disp='EXACT_SERVICE_CLASS_DEF_RECOVERED';runtime_instr='NO';gate='READY_FOR_SERVICE_IMPLEMENTATION_ENUMERATION'
 elif protected_candidate:
  payload_origin='NATIVE_OR_PROTECTED_RUNTIME_PAYLOAD_CANDIDATE';origin_disp='TARGET_REFERENCE_WITH_LOADER_OR_PROTECTED_PAYLOAD_EVIDENCE_NOT_CLASS_DEF';runtime_instr='NOT_YET_PAYLOAD_CANDIDATE_NEEDS_LOAD_PROOF';gate='PROTECTED_PAYLOAD_CANDIDATE_NEEDS_RUNTIME_LOAD_PROOF'
 elif root_status=='AVAILABLE' and root_maps=='READABLE':
  payload_origin='NOT_RECOVERED';origin_disp='PACKAGE_NON_DEX_AND_ROOT_READ_ONLY_RUNTIME_CODE_CENSUS_EXHAUSTED';runtime_instr='YES';gate='RUNTIME_CLASSLOADER_INSTRUMENTATION_REQUIRED'
 elif root_status=='AVAILABLE':
  payload_origin='NOT_RECOVERED';origin_disp='PACKAGE_NON_DEX_CENSUS_COMPLETE_ROOT_PROCESS_MAPS_UNAVAILABLE';runtime_instr='YES_BOUNDED_ROOT_RUNTIME_OBSERVATION_REQUIRED';gate='ROOT_RUNTIME_CODE_ORIGIN_OBSERVATION_REQUIRED'
 else:
  payload_origin='NOT_RECOVERED';origin_disp='PACKAGE_NON_DEX_CENSUS_COMPLETE_ROOT_ASSISTED_RUNTIME_CENSUS_NOT_AVAILABLE';runtime_instr='NO_ROOT_READ_ONLY_CENSUS_INCOMPLETE';gate='ROOT_READ_ONLY_CODE_ORIGIN_CENSUS_RECOMMENDED'
 impl_exact=exact and bool(onbind) and stub_origin!='NOT_RECOVERED'
 private={'schema':'rokid.test21-r3.3.4.2.4.private.v1','artifact_records':records,'class_evidence':overall,'stub_subclasses':stubsubs,'onbind':onbind,'root_status':root_status,'root_maps':root_maps,'shared_libraries':shared,'loader_markers':sorted(loader),'protector_markers':sorted(protect),'target_refs':sorted(targets),'native_target_refs':sorted(native_targets),'protected_candidates':sorted(cands),'service_code_payload_origin':payload_origin,'service_origin_disposition':origin_disp,'service_implementation_exact':impl_exact,'dex_parse_errors':errs}
 (priv/'r3-3-4-2-4-private.json').write_text(json.dumps(private,indent=2,sort_keys=True)+'\n')
 summary={
  'schema':'rokid.test21-r3.3.4.2.4.sanitized.v1','analysis_pass':True,'artifact_container_count':len(artifacts),**totals,
  'root_probe':root_status,'root_assisted_read_only':'YES' if root_status=='AVAILABLE' else 'NO','root_process_maps_access':root_maps,'root_code_candidate_count':root_cands,'root_code_artifact_pull_pass_count':root_pass,
  'relevant_shared_library_names':shared,'dynamic_loader_markers':sorted(loader),'protector_markers':sorted(protect),'target_reference_marker_count':len(targets),'native_target_reference_marker_count':len(native_targets),'protected_payload_candidate_count':len(cands),
  'embedded_dex_recovered_count':totals['embedded_dex'],'embedded_archive_recovered_count':totals['embedded_archives'],
  'cxrlinkservice_code_origin':svc_origin,'cxrlinkservice_code_origin_closure':'YES' if exact else 'NO','imediaservice_interface_origin':media_origin,'imediaservice_stub_origin':stub_origin,'imediaservice_proxy_origin':proxy_origin,'service_side_cxrlinkservice_onbind_count':len(onbind),'service_implementation_exact':'YES' if impl_exact else 'NO',
  'service_code_payload_origin':payload_origin,'service_implementation_origin_disposition':origin_disp,'runtime_instrumentation_required':runtime_instr,'replacement_feasibility_gate':gate,
  'proof_boundary':'OFFLINE_NON_DEX_RECURSIVE_CENSUS_PLUS_OPTIONAL_READ_ONLY_ROOT_CODE_ORIGIN_NO_PAYLOAD_EXECUTION'
 }
 (san/'test21-r3-3-4-2-4-summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
 def csv(v):return ','.join(v) if v else 'NONE'
 lines=[
  'TEST21_R3_3_4_2_4_ANALYSIS=PASS',f"ARTIFACT_CONTAINER_COUNT={summary['artifact_container_count']}",f"ZIP_ENTRY_COUNT={totals['zip_entries']}",f"NON_DEX_ENTRY_COUNT={totals['non_dex_entries']}",f"NATIVE_LIBRARY_ENTRY_COUNT={totals['native_entries']}",f"NESTED_ARCHIVE_ENTRY_COUNT={totals['nested_archives']}",f"EMBEDDED_DEX_RECOVERED_COUNT={totals['embedded_dex']}",f"EMBEDDED_ARCHIVE_RECOVERED_COUNT={totals['embedded_archives']}",
  'ROOT_PROBE='+root_status,'ROOT_ASSISTED_READ_ONLY='+summary['root_assisted_read_only'],'ROOT_PROCESS_MAPS_ACCESS='+root_maps,f'ROOT_CODE_CANDIDATE_COUNT={root_cands}',f'ROOT_CODE_ARTIFACT_PULL_PASS_COUNT={root_pass}',
  'RELEVANT_SHARED_LIBRARY_NAMES='+csv(shared),'DYNAMIC_LOADER_MARKERS='+csv(sorted(loader)),'PROTECTOR_MARKERS='+csv(sorted(protect)),f"TARGET_REFERENCE_MARKER_COUNT={len(targets)}",f"NATIVE_TARGET_REFERENCE_MARKER_COUNT={len(native_targets)}",f"PROTECTED_PAYLOAD_CANDIDATE_COUNT={len(cands)}",
  'CXRLINKSERVICE_CODE_ORIGIN='+svc_origin,'CXRLINKSERVICE_CODE_ORIGIN_CLOSURE='+summary['cxrlinkservice_code_origin_closure'],'IMEDIASTREAMSERVICE_INTERFACE_ORIGIN='+media_origin,'IMEDIASTREAMSERVICE_STUB_ORIGIN='+stub_origin,'IMEDIASTREAMSERVICE_PROXY_ORIGIN='+proxy_origin,f'CXRLINKSERVICE_ONBIND_COUNT={len(onbind)}','SERVICE_IMPLEMENTATION_EXACT='+summary['service_implementation_exact'],'SERVICE_CODE_PAYLOAD_ORIGIN='+payload_origin,'SERVICE_IMPLEMENTATION_ORIGIN_DISPOSITION='+origin_disp,'RUNTIME_INSTRUMENTATION_REQUIRED='+runtime_instr,'REPLACEMENT_FEASIBILITY_GATE='+gate,
  'PAYLOAD_EXECUTION=NONE','DEVICE_MUTATION=NONE','HI_ROKID_FORCE_STOP=NONE','CXR_L_CONNECTION_ATTEMPT=NONE','PHOTO_OPERATION=NONE','AUDIO_OPERATION=NONE']
 (san/'test21-r3-3-4-2-4-summary.txt').write_text('\n'.join(lines)+'\n')
 print('\n'.join(lines));return 0
if __name__=='__main__':raise SystemExit(main())
