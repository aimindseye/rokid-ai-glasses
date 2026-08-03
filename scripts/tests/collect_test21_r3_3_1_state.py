#!/usr/bin/env python3
import argparse, json, re, subprocess, time
from pathlib import Path

def run(cmd,timeout=12):
 try:
  p=subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
  return p.returncode,(p.stdout or '').replace('\r','')
 except subprocess.TimeoutExpired: return 124,''
def sh(adb,phone,args,timeout=12): return run([adb,'-s',phone,'shell',*args],timeout)
def dump(adb,phone,args,path):
 rc,out=sh(adb,phone,args); path.write_text(f'COLLECTION_RC={rc}\n{out}'); return out

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--adb',required=True); ap.add_argument('--phone',required=True); ap.add_argument('--hi-package',required=True); ap.add_argument('--custom-package',required=True); ap.add_argument('--output',required=True); ap.add_argument('--label',required=True)
 a=ap.parse_args(); out=Path(a.output); out.mkdir(parents=True,exist_ok=True); label=re.sub(r'[^A-Za-z0-9_.-]+','-',a.label)
 ps=dump(a.adb,a.phone,['ps','-A','-o','USER,PID,PPID,NAME,ARGS'],out/f'{label}-ps-private.txt')
 if not ps.strip(): ps=dump(a.adb,a.phone,['ps','-A'],out/f'{label}-ps-private.txt')
 dump(a.adb,a.phone,['dumpsys','activity','services',a.hi_package],out/f'{label}-hi-services-private.txt')
 dump(a.adb,a.phone,['dumpsys','activity','services',a.custom_package],out/f'{label}-custom-services-private.txt')
 dump(a.adb,a.phone,['dumpsys','activity','processes'],out/f'{label}-activity-processes-private.txt')
 acts=dump(a.adb,a.phone,['dumpsys','activity','activities'],out/f'{label}-activities-private.txt')
 hi=sh(a.adb,a.phone,['pidof',a.hi_package])[1].strip(); cu=sh(a.adb,a.phone,['pidof',a.custom_package])[1].strip()
 fg='YES' if a.custom_package in '\n'.join(x for x in acts.splitlines() if 'ResumedActivity' in x or 'topResumedActivity' in x) else 'NO'
 same=sum(1 for line in ps.splitlines() if a.hi_package in line)
 ext=[line.strip() for line in ps.splitlines() if a.hi_package not in line and a.custom_package not in line and any(t in line.lower() for t in ('rokid','cxr','aiui','sprite'))]
 (out/f'{label}-state.txt').write_text(f'LABEL={label}\nHI_PROCESS_VISIBLE={"YES" if hi else "NO"}\nCUSTOM_PROCESS_VISIBLE={"YES" if cu else "NO"}\nCUSTOM_FOREGROUND_PROVEN={fg}\nSAME_PACKAGE_PROCESS_COUNT={same}\nEXTERNAL_CANDIDATE_COUNT={len(ext)}\n')
 (out/f'{label}-external-candidates-private.txt').write_text('\n'.join(ext)+'\n' if ext else '')
 print(f'LABEL={label}'); print(f'HI_PROCESS_VISIBLE={"YES" if hi else "NO"}'); print(f'CUSTOM_PROCESS_VISIBLE={"YES" if cu else "NO"}'); print(f'CUSTOM_FOREGROUND_PROVEN={fg}')
 return 0
if __name__=='__main__': raise SystemExit(main())
