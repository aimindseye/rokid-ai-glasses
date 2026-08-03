#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re, zipfile, hashlib
from pathlib import Path

SERVICE='com.rokid.sprite.aiapp.externalapp.service.CXRLinkService'
PROVIDER='com.rokid.sprite.aiapp.external.CXRLinkProvider'
PRINTABLE=re.compile(rb'[\x20-\x7e]{4,320}')
FQCN=re.compile(r'(?<![A-Za-z0-9_$])(?:[a-zA-Z_$][\w$]*\.){2,}[A-Za-z_$][\w$]*(?![A-Za-z0-9_$])')
ACTIONISH=re.compile(r'^[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*){2,}$')

def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def strings_from_apk(p:Path):
    out=[]
    with zipfile.ZipFile(p) as z:
        for n in z.namelist():
            if not re.fullmatch(r'classes(?:\d+)?\.dex',Path(n).name):continue
            data=z.read(n)
            vals=[]
            for m in PRINTABLE.finditer(data):
                try:s=m.group().decode('ascii')
                except Exception:continue
                vals.append(s)
            out.append((n,vals))
    return out

def classify(vals):
    allv=[]
    for dex,ss in vals: allv.extend(ss)
    unique=sorted(set(allv))
    binder=[];actions=[];markers=[]
    for s in unique:
        low=s.lower()
        if SERVICE in s or PROVIDER in s or 'cxrlink' in low or 'bindservice' in low or 'onserviceconnected' in low:
            markers.append(s)
        # Binder/AIDL descriptor candidates. Keep candidate status; do not claim xref.
        fq=FQCN.findall(s)
        for c in fq:
            tail=c.rsplit('.',1)[-1];clow=c.lower()
            if ('rokid' in clow or 'cxr' in clow) and (re.match(r'^I[A-Z]',tail) or 'binder' in tail.lower() or 'aidl' in clow):
                binder.append(c)
            if ('rokid' in clow or 'cxr' in clow or 'link' in clow) and c not in {SERVICE,PROVIDER} and not c.endswith('CXRLinkService') and not c.endswith('CXRLinkProvider') and not re.match(r'^I[A-Z]',tail):
                actions.append(c)
        if ACTIONISH.fullmatch(s) and ('rokid' in low or 'cxr' in low or 'link' in low):
            if s not in {SERVICE,PROVIDER} and not s.endswith('CXRLinkService') and not s.endswith('CXRLinkProvider'):
                actions.append(s)
    return sorted(set(binder)),sorted(set(actions)),sorted(set(markers))

def main():
    a=argparse.ArgumentParser();a.add_argument('--apk-dir',required=True);a.add_argument('--output',required=True);x=a.parse_args()
    d=Path(x.apk_dir).resolve();o=Path(x.output).resolve();o.parent.mkdir(parents=True,exist_ok=True)
    result={'schema':'rokid.test21-r3-3-4-1.apk-string-census.v1','apks':[],'binder_interface_descriptor_candidates':[],'intent_action_string_candidates':[],'cxr_marker_strings':[]}
    for p in sorted(d.glob('*.apk')):
        try:
            vals=strings_from_apk(p);b,a2,m=classify(vals)
            result['apks'].append({'name':p.name,'sha256':sha(p),'dex_count':len(vals),'binder_candidates':b,'action_candidates':a2,'marker_count':len(m)})
            result['binder_interface_descriptor_candidates']+=b;result['intent_action_string_candidates']+=a2;result['cxr_marker_strings']+=m
        except Exception as e:
            result['apks'].append({'name':p.name,'sha256':sha(p),'error':str(e)})
    for k in ('binder_interface_descriptor_candidates','intent_action_string_candidates','cxr_marker_strings'):
        result[k]=sorted(set(result[k]))
    o.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print('TEST21_R3_3_4_1_APK_STRING_CENSUS=PASS')
    print('APK_COUNT='+str(len(result['apks'])))
    print('BINDER_DESCRIPTOR_CANDIDATE_COUNT='+str(len(result['binder_interface_descriptor_candidates'])))
    print('INTENT_ACTION_STRING_CANDIDATE_COUNT='+str(len(result['intent_action_string_candidates'])))
    return 0
if __name__=='__main__':raise SystemExit(main())
