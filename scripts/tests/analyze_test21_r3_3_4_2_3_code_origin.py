#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, importlib.util, json, re, zipfile
from pathlib import Path

HI_PACKAGE='com.rokid.sprite.global.aiapp'
SERVICE_DOT='com.rokid.sprite.aiapp.externalapp.service.CXRLinkService'
SERVICE_DESC='Lcom/rokid/sprite/aiapp/externalapp/service/CXRLinkService;'
MEDIA_DOT='com.rokid.sprite.aiapp.externalapp.IMediaStreamService'
MEDIA_DESC='Lcom/rokid/sprite/aiapp/externalapp/IMediaStreamService;'
STUB_DESC='Lcom/rokid/sprite/aiapp/externalapp/IMediaStreamService$Stub;'
PROXY_DESC='Lcom/rokid/sprite/aiapp/externalapp/IMediaStreamService$Stub$Proxy;'
TARGETS=(SERVICE_DESC,MEDIA_DESC,STUB_DESC,PROXY_DESC)

def sha256(p:Path)->str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def load_dex_base(repo:Path):
    p=repo/'scripts/tests/analyze_test21_r3_3_4_2_static_contract.py'
    if not p.is_file(): raise SystemExit('ERROR: prerequisite DEX parser missing')
    sp=importlib.util.spec_from_file_location('r3342base',p)
    m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m

def parse_pm_paths(text:str):
    out=[]
    for line in text.splitlines():
        line=line.strip()
        if line.startswith('package:'):
            p=line[8:].strip()
            if p and p not in out: out.append(p)
    return out

def absolute_artifact_paths(text:str):
    # Read-only discovery input. Keep candidates bounded to executable/code containers.
    rx=re.compile(r'/(?:[^\s\],;"\']+/)*[^\s\],;"\']+\.(?:apk|jar|dex)')
    out=[]
    for p in rx.findall(text):
        p=p.rstrip(':)')
        if p not in out: out.append(p)
    return out

def relevant_library_names(text:str):
    out=[]
    for line in text.splitlines():
        s=line.strip()
        low=s.lower()
        if ('rokid' in low or 'cxr' in low or 'sprite' in low or 'aiapp' in low) and len(s)<500:
            if s not in out: out.append(s)
    return out[:64]

def read_pull_manifest(path:Path):
    rows=[]
    if not path.is_file(): return rows
    for line in path.read_text(errors='replace').splitlines():
        if not line.strip() or line.startswith('KIND\t'): continue
        parts=line.split('\t')
        if len(parts)<5: continue
        rows.append({'kind':parts[0],'remote':parts[1],'local_rel':parts[2],'status':parts[3],'sha256':parts[4]})
    return rows

def _empty_target():
    return {'class_defs':[],'type_refs':[],'string_refs':[],'raw_hits':[]}

def scan_dex_bytes(data:bytes,label:str,DexClass):
    hit={t:_empty_target() for t in TARGETS};subs=[];parse_error=None
    # Raw/reference evidence survives a parser limitation, but never counts as a class definition.
    for t in TARGETS:
        for needle in (t, t[1:-1].replace('/','.') if t.startswith('L') else t):
            if needle.encode() in data:
                hit[t]['raw_hits'].append({'dex':label,'needle':needle})
                break
    try:
        d=DexClass(data,label)
        for t in TARGETS:
            c=d.classes.get(t)
            if c:
                methods=[]
                for idx in c.get('methods') or []:
                    try:
                        m=d.methods[idx];methods.append({'name':m.get('name'),'proto':m.get('proto'),'ret':m.get('ret')})
                    except Exception: pass
                hit[t]['class_defs'].append({'dex':label,'super':c.get('super'),'interfaces':c.get('interfaces') or [],'methods':methods})
            if t in d.types: hit[t]['type_refs'].append({'dex':label})
            dot=t[1:-1].replace('/','.') if t.startswith('L') else t
            if t in d.strings or dot in d.strings: hit[t]['string_refs'].append({'dex':label})
        for desc,c in d.classes.items():
            if c.get('super')==STUB_DESC:
                subs.append({'dex':label,'class':desc,'super':STUB_DESC,'interfaces':c.get('interfaces') or []})
    except Exception as e:
        parse_error=type(e).__name__+': '+str(e)[:200]
    return hit,subs,parse_error

def merge_target(dst,src):
    for t in TARGETS:
        for k in dst[t]: dst[t][k].extend(src[t][k])

def scan_artifact(path:Path,DexClass):
    result={'targets':{t:_empty_target() for t in TARGETS},'stub_subclasses':[],'dex_count':0,'dex_parse_errors':[],'container_error':None}
    try:
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as z:
                names=[n for n in z.namelist() if re.fullmatch(r'(?:.*/)?classes(?:\d+)?\.dex',n) or n.lower().endswith('.dex')]
                for n in sorted(set(names)):
                    data=z.read(n);result['dex_count']+=1
                    h,s,e=scan_dex_bytes(data,n,DexClass);merge_target(result['targets'],h);result['stub_subclasses'].extend(s)
                    if e: result['dex_parse_errors'].append({'dex':n,'error':e})
        elif path.suffix.lower()=='.dex':
            data=path.read_bytes();result['dex_count']=1
            h,s,e=scan_dex_bytes(data,path.name,DexClass);merge_target(result['targets'],h);result['stub_subclasses'].extend(s)
            if e: result['dex_parse_errors'].append({'dex':path.name,'error':e})
        else:
            # A non-zip .jar should still be recorded as unparseable rather than absence.
            result['container_error']='UNSUPPORTED_OR_NON_ZIP_CODE_CONTAINER'
    except Exception as e:
        result['container_error']=type(e).__name__+': '+str(e)[:200]
    return result

def artifact_origin_id(row,index):
    base=Path(row.get('remote') or row.get('local_rel') or 'artifact').name or 'artifact'
    return f"{row.get('kind','ARTIFACT')}[{index}]:{base}"

def classify_maps(status_text:str,maps_text:str,pid_text:str):
    s=status_text.upper()
    if 'READABLE' in s: return 'READABLE'
    if 'PERMISSION' in s or 'DENIED' in s: return 'DENIED_BY_ANDROID'
    if not pid_text.strip(): return 'PROCESS_NOT_RUNNING'
    if maps_text.strip(): return 'READABLE'
    return 'UNAVAILABLE'

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--repo',required=True);ap.add_argument('--r3341-evidence',required=True);ap.add_argument('--collection',required=True);ap.add_argument('--output',required=True)
    a=ap.parse_args();repo=Path(a.repo).resolve();r3341=Path(a.r3341_evidence).resolve();col=Path(a.collection).resolve();out=Path(a.output).resolve();(out/'sanitized').mkdir(parents=True,exist_ok=True)
    base=load_dex_base(repo)
    def rt(name):
        p=col/name
        return p.read_text(errors='replace') if p.is_file() else ''
    pm_paths=parse_pm_paths(rt('package-paths.txt'))
    dumpsys=rt('dumpsys-package.txt');libs=rt('shared-libraries.txt');maps=rt('process-maps.txt');pid=rt('process-id.txt').strip();maps_status=rt('process-maps-status.txt')
    pull_rows=read_pull_manifest(col/'pull-manifest.tsv')
    artifacts=[]
    for i,row in enumerate(pull_rows):
        if row['status']!='PASS': continue
        p=col/row['local_rel']
        if not p.is_file(): continue
        scan=scan_artifact(p,base.Dex)
        artifacts.append({'origin_id':artifact_origin_id(row,i),'kind':row['kind'],'basename':Path(row['remote']).name,'sha256':sha256(p),'size':p.stat().st_size,'scan':scan,'remote_private':row['remote']})
    # Preserved APK set is an independent historical comparator.
    preserved=[]
    apkdir=r3341/'raw/apks'
    for p in sorted(apkdir.glob('hi-*.apk')):
        if p.is_file(): preserved.append({'origin_id':'PRESERVED_R3341:'+p.name,'kind':'PRESERVED_R3341','basename':p.name,'sha256':sha256(p),'size':p.stat().st_size,'scan':scan_artifact(p,base.Dex),'remote_private':None})
    target_origins={t:[] for t in TARGETS}
    reference_origins={t:[] for t in TARGETS}
    stub_sub=[]
    for art in artifacts:
        for t in TARGETS:
            h=art['scan']['targets'][t]
            if h['class_defs']: target_origins[t].append({'origin_id':art['origin_id'],'sha256':art['sha256'],'basename':art['basename'],'class_defs':h['class_defs']})
            elif h['type_refs'] or h['string_refs'] or h['raw_hits']: reference_origins[t].append({'origin_id':art['origin_id'],'sha256':art['sha256'],'basename':art['basename']})
        if art['scan']['stub_subclasses']: stub_sub.append({'origin_id':art['origin_id'],'sha256':art['sha256'],'subclasses':art['scan']['stub_subclasses']})
    svc=target_origins[SERVICE_DESC];iface=target_origins[MEDIA_DESC];stub=target_origins[STUB_DESC];proxy=target_origins[PROXY_DESC]
    service_onbind=[]
    for o in svc:
        for c in o['class_defs']:
            for m in c.get('methods') or []:
                if m.get('name')=='onBind': service_onbind.append({'origin_id':o['origin_id'],'sha256':o['sha256'],'proto':m.get('proto'),'ret':m.get('ret')})
    maps_access=classify_maps(maps_status,maps,pid)
    mapped_paths=absolute_artifact_paths(maps) if maps_access=='READABLE' else []
    map_relevant=[p for p in mapped_paths if any(k in p.lower() for k in ('rokid','cxr','sprite','aiapp','externalapp'))]
    declared_paths=absolute_artifact_paths(dumpsys)
    relevant_libs=relevant_library_names(dumpsys+'\n'+libs)
    if svc:
        svc_origin=svc[0];origin_disp='EXACT_CLASS_DEF_RECOVERED_FROM_READ_ONLY_PULLED_ARTIFACT';origin_close=True
    elif reference_origins[SERVICE_DESC]:
        svc_origin=None;origin_disp='SERVICE_DESCRIPTOR_REFERENCE_RECOVERED_BUT_CLASS_DEF_NOT_FOUND';origin_close=False
    elif maps_access=='DENIED_BY_ANDROID':
        svc_origin=None;origin_disp='SERVICE_CLASS_NOT_FOUND_IN_READABLE_ARTIFACTS_PROCESS_MAPS_BLOCKED';origin_close=False
    elif maps_access=='PROCESS_NOT_RUNNING':
        svc_origin=None;origin_disp='SERVICE_CLASS_NOT_FOUND_IN_READABLE_ARTIFACTS_HI_PROCESS_NOT_RUNNING';origin_close=False
    else:
        svc_origin=None;origin_disp='SERVICE_CLASS_NOT_FOUND_IN_READABLE_ARTIFACTS';origin_close=False
    # Binder service-side corroboration is separately gated.
    if svc and (stub or stub_sub) and service_onbind:
        impl_disp='SERVICE_CLASS_AND_ONBIND_AND_IMEDIASTREAMSERVICE_IMPLEMENTATION_ARTIFACTS_RECOVERED'
    elif svc:
        impl_disp='SERVICE_CLASS_ARTIFACT_RECOVERED_BINDER_IMPLEMENTATION_LINEAGE_PARTIAL'
    else:
        impl_disp='SERVICE_IMPLEMENTATION_ARTIFACT_NOT_RECOVERED'
    result={
      'schema':'rokid.test21-r3-3-4-2-3.runtime-code-origin.v1','analysis':'PASS','mode':'READ_ONLY_DEVICE_AND_EXISTING_PRIVATE_EVIDENCE',
      'device_collection':{'pm_code_paths':pm_paths,'pm_code_path_count':len(pm_paths),'process_visible':bool(pid),'process_maps_access':maps_access,'process_mapped_artifact_count':len(mapped_paths),'process_mapped_relevant_paths':map_relevant,'declared_artifact_paths':declared_paths,'relevant_shared_library_lines':relevant_libs},
      'artifact_collection':{'pull_manifest_rows':pull_rows,'pulled_artifact_count':len(artifacts),'artifacts':artifacts,'preserved_r3341_artifacts':preserved},
      'origins':{'cxrlinkservice':svc,'imedia_interface':iface,'imedia_stub':stub,'imedia_proxy':proxy,'stub_subclasses':stub_sub,'service_onbind':service_onbind,'reference_only':reference_origins},
      'closure':{'cxrlinkservice_code_origin_exact':origin_close,'cxrlinkservice_origin_disposition':origin_disp,'service_implementation_disposition':impl_disp},
      'proof_boundary':'READ_ONLY_PACKAGE_MANAGER_PLUS_ACCESSIBLE_PROCESS_MAPS_PLUS_CLASS_DEF_CENSUS_NO_ROOT_NO_INSTRUMENTATION_NO_CONNECTION_ATTEMPT',
      'device_mutation':'NONE'}
    (out/'r3-3-4-2-3-private.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    # Sanitized structure removes install paths, PIDs, raw maps/dumpsys, and local filenames. Exact recovered artifacts are represented by bounded origin IDs + hashes.
    san={
      'schema':result['schema'],'analysis':'PASS','mode':result['mode'],
      'device_collection':{'pm_code_path_count':len(pm_paths),'process_visible':bool(pid),'process_maps_access':maps_access,'process_mapped_artifact_count':len(mapped_paths),'process_mapped_relevant_artifact_count':len(map_relevant),'relevant_shared_library_line_count':len(relevant_libs)},
      'artifact_collection':{'pull_attempt_count':len(pull_rows),'pulled_artifact_count':len(artifacts),'preserved_r3341_artifact_count':len(preserved),'pulled_artifacts':[{'origin_id':x['origin_id'],'basename':x['basename'],'sha256':x['sha256'],'size':x['size'],'dex_count':x['scan']['dex_count'],'dex_parse_error_count':len(x['scan']['dex_parse_errors'])} for x in artifacts]},
      'origins':{'cxrlinkservice':[{'origin_id':x['origin_id'],'basename':x['basename'],'sha256':x['sha256'],'class_def_count':len(x['class_defs'])} for x in svc],
                 'imedia_interface':[{'origin_id':x['origin_id'],'basename':x['basename'],'sha256':x['sha256'],'class_def_count':len(x['class_defs'])} for x in iface],
                 'imedia_stub':[{'origin_id':x['origin_id'],'basename':x['basename'],'sha256':x['sha256'],'class_def_count':len(x['class_defs'])} for x in stub],
                 'imedia_proxy':[{'origin_id':x['origin_id'],'basename':x['basename'],'sha256':x['sha256'],'class_def_count':len(x['class_defs'])} for x in proxy],
                 'service_onbind':service_onbind,'stub_subclass_origin_count':len(stub_sub)},
      'closure':result['closure'],'proof_boundary':result['proof_boundary'],'device_mutation':'NONE'}
    (out/'sanitized/test21-r3-3-4-2-3-summary.json').write_text(json.dumps(san,indent=2,sort_keys=True)+'\n')
    def origin_line(xs):
        if not xs:return 'NOT_RECOVERED'
        return ','.join(x['origin_id'] for x in xs)
    def origin_sha(xs):
        if not xs:return 'NONE'
        return ','.join(x['sha256'] for x in xs)
    lines=[
      'TEST21_R3_3_4_2_3_ANALYSIS=PASS','MODE=READ_ONLY_DEVICE_AND_EXISTING_PRIVATE_EVIDENCE',
      'PM_CODE_PATH_COUNT='+str(len(pm_paths)),'HI_ROKID_PROCESS_VISIBLE='+('YES' if pid else 'NO'),'PROCESS_MAPS_ACCESS='+maps_access,
      'PROCESS_MAPPED_CODE_ARTIFACT_COUNT='+str(len(mapped_paths)),'PROCESS_MAPPED_RELEVANT_ARTIFACT_COUNT='+str(len(map_relevant)),
      'RELEVANT_SHARED_LIBRARY_LINE_COUNT='+str(len(relevant_libs)),'RUNTIME_ARTIFACT_PULL_ATTEMPT_COUNT='+str(len(pull_rows)),'RUNTIME_ARTIFACT_PULL_PASS_COUNT='+str(len(artifacts)),
      'CXRLINKSERVICE_CODE_ORIGIN='+origin_line(svc),'CXRLINKSERVICE_CODE_ORIGIN_SHA256='+origin_sha(svc),'CXRLINKSERVICE_CODE_ORIGIN_CLOSURE='+('YES' if origin_close else 'NO'),
      'IMEDIASTREAMSERVICE_INTERFACE_ORIGIN='+origin_line(iface),'IMEDIASTREAMSERVICE_INTERFACE_ORIGIN_SHA256='+origin_sha(iface),
      'IMEDIASTREAMSERVICE_STUB_ORIGIN='+origin_line(stub),'IMEDIASTREAMSERVICE_STUB_ORIGIN_SHA256='+origin_sha(stub),
      'IMEDIASTREAMSERVICE_PROXY_ORIGIN='+origin_line(proxy),'SERVICE_SIDE_CXRLINKSERVICE_ONBIND_COUNT='+str(len(service_onbind)),
      'SERVICE_IMPLEMENTATION_ORIGIN_DISPOSITION='+origin_disp,'SERVICE_IMPLEMENTATION_DISPOSITION='+impl_disp,
      'SERVICE_IMPLEMENTATION_ORIGIN_CLOSURE='+('YES' if origin_close else 'NO'),
      'PROOF_BOUNDARY='+result['proof_boundary'],'ADB_READ_ONLY=YES','DEVICE_MUTATION=NONE','HI_ROKID_FORCE_STOP=NONE','CXR_L_CONNECTION_ATTEMPT=NONE','PHOTO_OPERATION=NONE','AUDIO_OPERATION=NONE']
    txt='\n'.join(lines)+'\n';(out/'sanitized/test21-r3-3-4-2-3-summary.txt').write_text(txt);print(txt,end='');return 0
if __name__=='__main__': raise SystemExit(main())
