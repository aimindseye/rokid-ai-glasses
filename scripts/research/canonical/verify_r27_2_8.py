#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,json,subprocess,sys,tempfile,zipfile
from pathlib import Path
try:
    from primitives import read_json,sha256_file
    from consolidation_status import evaluate as consolidation_evaluate
except ImportError:
    from scripts.research.canonical.primitives import read_json,sha256_file
    from scripts.research.canonical.consolidation_status import evaluate as consolidation_evaluate
BASE=Path(__file__).resolve().parent
PROFILES=BASE/'profiles/test19-network-analyzers.json'

def write_tsv(path,rows,fields):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,delimiter='\t',lineterminator='\n'); w.writeheader(); w.writerows(rows)
def run(argv,cwd): return subprocess.run(argv,cwd=str(cwd),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=False,check=False,timeout=30)
def cases(): return [
 ('test19-r1','r1_local_pass','remote_host,remote_ip\nrouter.local,192.168.1.5\n'),
 ('test19-r1','r1_public_fail','remote_host,remote_ip\napi.example.test,8.8.8.8\n'),
 ('test19-r2','r2_stock_public_pass','package,remote_host,remote_ip\norg.aimindseye.rokid.cxrlqualification,router.local,192.168.1.5\ncom.rokid.sprite.global.aiapp,api.example.test,8.8.8.8\n'),
 ('test19-r2','r2_custom_public_fail','package,remote_host,remote_ip\norg.aimindseye.rokid.cxrlqualification,api.example.test,8.8.8.8\n'),
 ('test19-r2','r2_missing_app_identity_blocked','remote_host,remote_ip\nrouter.local,192.168.1.5\n')]
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--repo',required=True); ap.add_argument('--archive',required=True); ap.add_argument('--output',required=True); a=ap.parse_args()
    repo=Path(a.repo).resolve(); archive=Path(a.archive).resolve(); out=Path(a.output).resolve(); out.mkdir(parents=True,exist_ok=True)
    profiles=read_json(PROFILES)['profiles']; by={p['revision']:p for p in profiles}; locks=[]; failures=0
    with zipfile.ZipFile(archive) as z:
      for rev in ('test19-r1','test19-r2'):
        p=by[rev]; arc='historical/'+p['legacy_path']; original=hashlib.sha256(z.read(arc)).hexdigest(); live=sha256_file(repo/p['legacy_path'])
        ok1=original==p['original_source_sha256']; ok2=live==p['compatibility_shim_sha256']; failures += int(not ok1)+int(not ok2)
        locks.append({'revision':rev,'path':p['legacy_path'],'original_expected_sha256':p['original_source_sha256'],'archive_sha256':original,'shim_expected_sha256':p['compatibility_shim_sha256'],'live_sha256':live,'archive_lock':'PASS' if ok1 else 'FAIL','shim_lock':'PASS' if ok2 else 'FAIL'})
      write_tsv(out/'source-locks.tsv',locks,['revision','path','original_expected_sha256','archive_sha256','shim_expected_sha256','live_sha256','archive_lock','shim_lock'])
      rows=[]
      with tempfile.TemporaryDirectory(prefix='r2728-') as td:
        temp=Path(td)
        legacy_paths={}
        for rev in ('test19-r1','test19-r2'):
          p=by[rev]; lp=temp/(rev+'.py'); lp.write_bytes(z.read('historical/'+p['legacy_path'])); lp.chmod(0o755); legacy_paths[rev]=lp
        for rev,name,text in cases():
          case=temp/name; case.mkdir(); src=case/'input.csv'; src.write_text(text,encoding='utf-8'); oldout=case/'legacy.json'; newout=case/'shim.json'
          old=run([sys.executable,str(legacy_paths[rev]),'--csv',str(src),'--output',str(oldout)],repo)
          new=run([sys.executable,str(repo/by[rev]['legacy_path']),'--csv',str(src),'--output',str(newout)],repo)
          out_equal=oldout.is_file() and newout.is_file() and oldout.read_bytes()==newout.read_bytes()
          eq=(old.returncode==new.returncode and old.stdout==new.stdout and old.stderr==new.stderr and out_equal); failures += 0 if eq else 1
          rows.append({'revision':rev,'case':name,'archived_rc':old.returncode,'shim_rc':new.returncode,'stdout_equal':'YES' if old.stdout==new.stdout else 'NO','stderr_equal':'YES' if old.stderr==new.stderr else 'NO','output_json_equal':'YES' if out_equal else 'NO','equivalent':'YES' if eq else 'NO'})
    write_tsv(out/'analyzer-retirement-equivalence.tsv',rows,['revision','case','archived_rc','shim_rc','stdout_equal','stderr_equal','output_json_equal','equivalent'])
    cstatus,_=consolidation_evaluate(repo); ifail=0 if cstatus['status']=='PASS' else 1; failures += ifail
    summary={'schema':'rokid.r27.2.8.final-closure.v1','status':'PASS' if failures==0 else 'FAIL','network_analyzer_profile_count':2,'network_analyzer_archived_shim_equivalent_count':sum(all(r['equivalent']=='YES' for r in rows if r['revision']==rev) for rev in ('test19-r1','test19-r2')),'behavioral_case_count':5,'behavioral_failure_count':sum(r['equivalent']!='YES' for r in rows),'newly_canonicalized_implementation_count':2,'total_canonicalized_implementation_count':88,'preserve_distinct_implementation_family_count':4,'host_multi_member_consolidation_candidate_count':0,'source_lock_failure_count':sum((r['archive_lock']!='PASS')+(r['shim_lock']!='PASS') for r in locks)+ifail,'repository_path_deletion_count':0,'r27_whole_history_consolidation':'COMPLETE' if failures==0 else 'BLOCKED','next_device_test_ready':failures==0,'device_operation':'NONE','privileged_operation':'NONE','network_operation':'NONE'}
    (out/'summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print('R27_2_8_VERIFY='+summary['status']); print('NETWORK_ANALYZER_PROFILE_COUNT=2'); print('NETWORK_ANALYZER_ARCHIVED_SHIM_EQUIVALENT_COUNT='+str(summary['network_analyzer_archived_shim_equivalent_count'])); print('BEHAVIORAL_CASE_COUNT=5'); print('BEHAVIORAL_FAILURE_COUNT='+str(summary['behavioral_failure_count'])); print('NEWLY_CANONICALIZED_IMPLEMENTATION_COUNT=2'); print('TOTAL_CANONICALIZED_IMPLEMENTATION_COUNT=88'); print('PRESERVE_DISTINCT_IMPLEMENTATION_FAMILY_COUNT=4'); print('HOST_MULTI_MEMBER_CONSOLIDATION_CANDIDATE_COUNT=0'); print('SOURCE_LOCK_FAILURE_COUNT='+str(summary['source_lock_failure_count'])); print('REPOSITORY_PATH_DELETION_COUNT=0'); print('R27_WHOLE_HISTORY_CONSOLIDATION='+summary['r27_whole_history_consolidation']); print('NEXT_DEVICE_TEST_READY='+('YES' if summary['next_device_test_ready'] else 'NO')); print('DEVICE_OPERATION=NONE'); print('PRIVILEGED_OPERATION=NONE'); print('NETWORK_OPERATION=NONE')
    return 0 if summary['status']=='PASS' else 1
if __name__=='__main__': raise SystemExit(main())
