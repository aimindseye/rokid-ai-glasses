#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, importlib.util, json, re, struct, sys, zipfile
from collections import defaultdict, deque
from pathlib import Path

HI_GLOBAL='com.rokid.sprite.global.aiapp'
HI_LEGACY='com.rokid.sprite.aiapp'
CUSTOM='org.aimindseye.rokid.cxrphotoqualification'
SERVICE_DOT='com.rokid.sprite.aiapp.externalapp.service.CXRLinkService'
SERVICE_DESC='Lcom/rokid/sprite/aiapp/externalapp/service/CXRLinkService;'
MEDIA_ACTION='com.rokid.sprite.aiapp.externalapp.MEDIA_STREAM_SERVICE'
MEDIA_IFACE='com.rokid.sprite.aiapp.externalapp.IMediaStreamService'
MEDIA_IFACE_DESC='Lcom/rokid/sprite/aiapp/externalapp/IMediaStreamService;'
MEDIA_STUB='Lcom/rokid/sprite/aiapp/externalapp/IMediaStreamService$Stub;'
EXT_CLIENT='Lcom/rokid/sprite/aiapp/externalapp/example/ExternalAppClient;'
CUSTOM_ROOT='Lorg/aimindseye/rokid/cxrphotoqualification/'
EXPECTED_AAR='c23d34b3adc60d3fa16001645ce6172eaf4554173e7ef9c078595e672d50824e'


def sha256(p:Path)->str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()


def load_prev(repo:Path):
    p=repo/'scripts/tests/analyze_test21_r3_3_4_2_static_contract.py'
    if not p.is_file(): raise SystemExit('ERROR: r3.3.4.2 analyzer missing')
    spec=importlib.util.spec_from_file_location('r3342_prev',p)
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


def apk_set(apkdir:Path,prefix:str):
    xs=sorted(apkdir.glob(prefix+'-*.apk'))
    if not xs: xs=sorted(apkdir.glob(prefix+'*.apk'))
    return [p for p in xs if p.is_file()]


def load_model(prev, apks):
    m=prev.Model()
    for p in apks: m.add_apk(p)
    return m


def method_key(prev,m): return prev.Model.key(m)


def method_by_substring(model,needle):
    return [m for m in model.methods if needle in method_key(None,m) if False]


def keys_matching(prev,model,class_desc=None,name=None,proto=None):
    out=[]
    for m in model.methods:
        if class_desc is not None and m['class']!=class_desc: continue
        if name is not None and m['name']!=name: continue
        if proto is not None and m['proto']!=proto: continue
        out.append(prev.Model.key(m))
    return sorted(set(out))


def class_assignable(model,child,target):
    if child==target:return True
    seen=set();q=deque([child])
    while q:
        c=q.popleft()
        if c in seen:continue
        seen.add(c);meta=model.classes.get(c)
        if not meta:continue
        parents=[]
        if meta.get('super'):parents.append(meta['super'])
        parents.extend(meta.get('interfaces') or [])
        if target in parents:return True
        q.extend(x for x in parents if x not in seen)
    return False


def expanded_edges(prev,model):
    by_sig=defaultdict(list)
    for m in model.methods: by_sig[(m['name'],m['proto'])].append(m)
    edges=defaultdict(set)
    dispatch=[]
    for caller,ins in model.method_ins.items():
        for x in ins:
            if x.get('kind')!='invoke':continue
            t=x['method'];tk=prev.Model.key(t);edges[caller].add(tk)
            candidates=[]
            for cm in by_sig.get((t['name'],t['proto']),[]):
                if cm.get('code_off') and class_assignable(model,cm['class'],t['class']):
                    ck=prev.Model.key(cm);edges[caller].add(ck)
                    if ck!=tk:candidates.append(ck)
            if candidates:dispatch.append({'caller':caller,'declared_target':tk,'resolved_overrides':sorted(set(candidates))})
    return edges,dispatch


def shortest(edges,roots,targets,max_depth=14):
    target=set(targets);q=deque();seen=set()
    for r in roots:q.append((r,[r]));seen.add(r)
    while q:
        cur,path=q.popleft()
        if cur in target:return path
        if len(path)>=max_depth:continue
        for n in sorted(edges.get(cur,())):
            if n not in seen:seen.add(n);q.append((n,path+[n]))
    return []


def custom_roots(prev,model):
    # Prefer the controller's explicit SDK entry point; fall back to all custom methods.
    exact=[k for k in model.by_key if k.startswith(CUSTOM_ROOT) and 'CxrLPhotoController;->invokeSdkConnect' in k]
    return exact or sorted(k for k in model.by_key if k.startswith(CUSTOM_ROOT))


def invocation_args_to(prev,model,target_prefix):
    out=[]
    sums=prev.intent_summaries(model)
    for m in model.methods:
        if not m.get('code_off'):continue
        sim=prev.simulate(model,m,sums)
        for e in sim['events']:
            if e['invoke'].startswith(target_prefix):
                clean=[]
                for a in e.get('args',[]):
                    if isinstance(a,dict):
                        clean.append({k:a.get(k) for k in ('kind','value','type','name','owner','action','package') if a.get(k) is not None})
                    else: clean.append(None)
                out.append({'caller':prev.Model.key(m),'target':e['invoke'],'pc':e['pc'],'args':clean})
    return out


def method_facts(prev,model,key):
    m=model.by_key.get(key)
    if not m:return None
    strings=[];inv=[];ops=[]
    for x in model.method_ins.get(key,[]):
        ops.append({'pc':x.get('pc'),'op':x.get('op'),'kind':x.get('kind')})
        if x.get('kind')=='string':strings.append(x.get('value'))
        elif x.get('kind')=='invoke':inv.append(prev.Model.key(x['method']))
    return {'method':key,'strings':sorted(set(s for s in strings if s)),'invokes':inv,
            'conditional_opcode_count':sum(1 for x in ops if x['op'] is not None and 0x32<=x['op']<=0x3d),
            'throw_or_move_exception_count':sum(1 for x in ops if x['op'] in (0x0d,0x27))}


def find_controller_source(repo:Path):
    candidates=[]
    for root in [repo/'app/src',repo/'tests',repo]:
        if not root.exists():continue
        try:
            for p in root.rglob('CxrLPhotoController.java'):
                if '/build/' not in str(p) and '/.git/' not in str(p):candidates.append(p)
            for p in root.rglob('CxrLPhotoController.kt'):
                if '/build/' not in str(p) and '/.git/' not in str(p):candidates.append(p)
        except OSError:pass
        if candidates:break
    return sorted(set(candidates))[0] if candidates else None


def extract_method_body(text,name):
    m=re.search(r'\b'+re.escape(name)+r'\s*\([^)]*\)\s*(?:throws\s+[^\{]+)?\{',text)
    if not m:return None
    start=text.find('{',m.start());depth=0
    for i in range(start,len(text)):
        if text[i]=='{':depth+=1
        elif text[i]=='}':
            depth-=1
            if depth==0:return text[start+1:i]
    return None


def source_role(repo:Path):
    p=find_controller_source(repo)
    out={'available':False,'file_sha256':None,'invoke_calls_fallback':False,'fallback_call_in_catch':False,'fallback_call_in_if':False,'known_action_present':False,'global_package_present':False,'legacy_package_present':False}
    if not p:return out
    t=p.read_text(errors='replace');body=extract_method_body(t,'invokeSdkConnect') or ''
    out.update(available=True,file_sha256=sha256(p),invoke_calls_fallback='bindServiceFallback(' in body,
               known_action_present=MEDIA_ACTION in t,global_package_present=HI_GLOBAL in t,legacy_package_present=HI_LEGACY in t)
    pos=body.find('bindServiceFallback(')
    if pos>=0:
        prefix=body[:pos]
        # Conservative lexical evidence only; not a full Java parser.
        last_catch=prefix.rfind('catch');last_if=prefix.rfind('if')
        last_close=prefix.rfind('}')
        out['fallback_call_in_catch']=last_catch>last_close
        out['fallback_call_in_if']=last_if>last_close
    return out

# ---- Android binary XML ----
def _u32(b,o):return struct.unpack_from('<I',b,o)[0]
def _u16(b,o):return struct.unpack_from('<H',b,o)[0]

def _len8(b,o):
    x=b[o];o+=1
    if x&0x80:y=b[o];o+=1;return ((x&0x7f)<<8)|y,o
    return x,o

def _len16(b,o):
    x=_u16(b,o);o+=2
    if x&0x8000:y=_u16(b,o);o+=2;return ((x&0x7fff)<<16)|y,o
    return x,o

def parse_string_pool(chunk):
    hdr=_u16(chunk,2);count=_u32(chunk,8);flags=_u32(chunk,16);start=_u32(chunk,20);utf8=bool(flags&0x100)
    offs=[_u32(chunk,hdr+4*i) for i in range(count)];out=[]
    for off in offs:
        p=start+off
        try:
            if utf8:
                _,p=_len8(chunk,p);bl,p=_len8(chunk,p);raw=chunk[p:p+bl];s=raw.decode('utf-8','replace')
            else:
                n,p=_len16(chunk,p);raw=chunk[p:p+n*2];s=raw.decode('utf-16le','replace')
        except Exception:s=''
        out.append(s)
    return out

def axml_events(data:bytes):
    if data.lstrip().startswith(b'<'):
        import xml.etree.ElementTree as ET
        root=ET.fromstring(data.decode('utf-8','replace'));events=[]
        def walk(e):
            attrs={k.split('}')[-1]:v for k,v in e.attrib.items()};events.append(('start',e.tag.split('}')[-1],attrs))
            for c in e:walk(c)
            events.append(('end',e.tag.split('}')[-1],{}))
        walk(root);return events
    if len(data)<8 or _u16(data,0)!=0x0003:raise ValueError('not binary Android XML')
    total=_u32(data,4);pos=_u16(data,2);strings=[];events=[]
    while pos+8<=min(total,len(data)):
        typ=_u16(data,pos);hdr=_u16(data,pos+2);size=_u32(data,pos+4)
        if size<8 or pos+size>len(data):break
        ch=data[pos:pos+size]
        if typ==0x0001:strings=parse_string_pool(ch)
        elif typ==0x0102 and strings:
            # ResXMLTree_node(16) + attrExt; attrStart is relative to attrExt start.
            ext=16;name_idx=_u32(ch,ext+4);astart=_u16(ch,ext+8);asize=_u16(ch,ext+10);acount=_u16(ch,ext+12)
            name=strings[name_idx] if name_idx<len(strings) else ''
            attrs={};base=ext+astart
            for i in range(acount):
                a=base+i*asize
                if a+20>len(ch):break
                nidx=_u32(ch,a+4);raw=_u32(ch,a+8);dtype=ch[a+15];dval=_u32(ch,a+16)
                an=strings[nidx] if nidx<len(strings) else ''
                if raw!=0xffffffff and raw<len(strings):val=strings[raw]
                elif dtype==0x03 and dval<len(strings):val=strings[dval]
                elif dtype==0x12:val='true' if dval else 'false'
                elif dtype in (0x10,0x11):val=str(dval)
                else:val='0x%x'%dval
                attrs[an]=val
            events.append(('start',name,attrs))
        elif typ==0x0103 and strings:
            ext=16;name_idx=_u32(ch,ext+4);name=strings[name_idx] if name_idx<len(strings) else '';events.append(('end',name,{}))
        pos+=size
    return events

def normalize_component(pkg,name):
    if not name:return None
    if name.startswith('.'):return pkg+name
    if '.' not in name:return pkg+'.'+name
    return name

def manifest_contract(apks):
    manifests=[];services=[]
    for apk in apks:
        try:
            with zipfile.ZipFile(apk) as z:data=z.read('AndroidManifest.xml')
            ev=axml_events(data)
        except Exception as e:
            manifests.append({'apk_sha256':sha256(apk),'parse':'FAIL','error_type':type(e).__name__});continue
        pkg=None;stack=[];current=None;in_filter=False
        for typ,name,attrs in ev:
            if typ=='start':
                stack.append(name)
                if name=='manifest':pkg=attrs.get('package') or pkg
                elif name=='service':
                    current={'name_raw':attrs.get('name'),'name':normalize_component(pkg,attrs.get('name')) if pkg else attrs.get('name'),'exported':attrs.get('exported'),'permission':attrs.get('permission'),'actions':[],'apk_sha256':sha256(apk)}
                elif name=='intent-filter' and current is not None:in_filter=True
                elif name=='action' and current is not None and in_filter:
                    a=attrs.get('name')
                    if a:current['actions'].append(a)
            else:
                if name=='intent-filter':in_filter=False
                elif name=='service' and current is not None:
                    current['actions']=sorted(set(current['actions']));services.append(current);current=None
                if stack:stack.pop()
        manifests.append({'apk_sha256':sha256(apk),'parse':'PASS','package':pkg,'service_count':sum(1 for s in services if s['apk_sha256']==sha256(apk))})
    target=[s for s in services if s.get('name')==SERVICE_DOT]
    packages=sorted(set(m.get('package') for m in manifests if m.get('package')))
    return {'manifests':manifests,'packages':packages,'services':services,'cxrlinkservice':target,
            'known_action_resolves_to_cxrlinkservice':any(MEDIA_ACTION in (s.get('actions') or []) for s in target)}


def service_side(prev,hi):
    svc=hi.classes.get(SERVICE_DESC)
    stub_sub=[]
    for d,c in hi.classes.items():
        if c.get('super')==MEDIA_STUB:stub_sub.append(d)
    onbind=[]
    if svc:
        for m in hi.methods_of(SERVICE_DESC,'onBind'):
            refs=[];news=[];fields=[]
            for x in hi.method_ins.get(prev.Model.key(m),[]):
                if x.get('kind')=='invoke':refs.append(prev.Model.key(x['method']))
                elif x.get('kind')=='new':news.append(x.get('value'))
                elif x.get('kind')=='fieldobj':fields.append(x.get('field',{}).get('type'))
            related=sorted(set([x for x in stub_sub if x in news or any(x in r for r in refs)] + [x for x in fields if x in stub_sub]))
            onbind.append({'method':prev.Model.key(m),'stub_lineage':related,'invokes':refs})
    # Search any onBind that statically touches the media stub or its subclasses.
    other=[]
    for m in hi.methods:
        if m['name']!='onBind' or not m.get('code_off'):continue
        k=prev.Model.key(m);refs=[];types=[]
        for x in hi.method_ins.get(k,[]):
            if x.get('kind')=='invoke':refs.append(prev.Model.key(x['method']))
            elif x.get('kind')=='new':types.append(x.get('value'))
            elif x.get('kind')=='fieldobj':types.append(x.get('field',{}).get('type'))
        if any(MEDIA_STUB in r or MEDIA_IFACE_DESC in r for r in refs) or any(t in stub_sub or t in (MEDIA_STUB,MEDIA_IFACE_DESC) for t in types):other.append({'method':k,'invokes':refs})
    descriptor_refs=[]
    for m in hi.methods:
        k=prev.Model.key(m)
        if MEDIA_IFACE_DESC in k or MEDIA_STUB in k:descriptor_refs.append(k)
    exact=bool(svc and onbind and any(x['stub_lineage'] for x in onbind))
    if exact:disp='EXACT_CXRLINKSERVICE_ONBIND_TO_IMEDIASTREAMSERVICE_STUB'
    elif svc and onbind and stub_sub:disp='CXRLINKSERVICE_ONBIND_AND_IMEDIASTREAMSERVICE_STUB_PRESENT_LINK_UNRESOLVED'
    elif stub_sub:disp='IMEDIASTREAMSERVICE_STUB_IMPLEMENTATION_PRESENT_SERVICE_LINK_UNRESOLVED'
    elif descriptor_refs:disp='IMEDIASTREAMSERVICE_DESCRIPTOR_REFERENCED_SERVICE_IMPLEMENTATION_UNRESOLVED'
    else:disp='SERVICE_SIDE_IMEDIASTREAMSERVICE_CORROBORATION_UNRESOLVED'
    return {'cxrlinkservice_class_found':bool(svc),'cxrlinkservice_onbind':onbind,'stub_subclasses':sorted(stub_sub),'other_onbind_candidates':other,'descriptor_reference_count':len(set(descriptor_refs)),'exact':exact,'disposition':disp}


def aar_find(explicit):
    cand=[]
    if explicit:cand.append(Path(explicit).expanduser())
    root=Path.home()/'.gradle/caches/modules-2/files-2.1/com.rokid.cxr/client-l/1.0.1'
    if root.exists():cand.extend(root.glob('**/*.aar'))
    for p in cand:
        try:
            if p.is_file() and sha256(p)==EXPECTED_AAR:return p
        except OSError:pass
    return None


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--repo',required=True);ap.add_argument('--r3341-evidence',required=True);ap.add_argument('--output',required=True);ap.add_argument('--cxrl-aar');x=ap.parse_args()
    repo=Path(x.repo).resolve();ev=Path(x.r3341_evidence).resolve();out=Path(x.output).resolve();(out/'sanitized').mkdir(parents=True,exist_ok=True)
    prev=load_prev(repo);apkdir=ev/'raw/apks';custom_apks=apk_set(apkdir,'custom');hi_apks=apk_set(apkdir,'hi')
    if not custom_apks or not hi_apks:raise SystemExit('ERROR: preserved r3.3.4.1 APK set unavailable')
    cm=load_model(prev,custom_apks);hm=load_model(prev,hi_apks)
    binds=prev.bind_sites(cm)
    for b in binds:
        b['call_path_exact']=prev.shortest_path(cm,b['caller'])
        b['intent']=prev.clean_intent(b.get('intent'))
        v=b.get('service_connection_value');b['service_connection_value']=None if not isinstance(v,dict) else {k:v.get(k) for k in ('kind','type','name','owner')}
    edges,dispatch=expanded_edges(prev,cm);roots=custom_roots(prev,cm)
    ext_targets=keys_matching(prev,cm,EXT_CLIENT,'a','(Ljava/lang/String;)Z') or keys_matching(prev,cm,EXT_CLIENT,'a',None)
    ext_path=shortest(edges,roots,ext_targets)
    ext_binds=[b for b in binds if b['caller'].startswith(EXT_CLIENT+'->')]
    fallback_keys=[k for k in cm.by_key if k.startswith(CUSTOM_ROOT) and 'CxrLPhotoController;->bindServiceFallback' in k]
    invoke_keys=[k for k in cm.by_key if k.startswith(CUSTOM_ROOT) and 'CxrLPhotoController;->invokeSdkConnect' in k]
    fallback_calls=[]
    for fk in fallback_keys:fallback_calls.extend(invocation_args_to(prev,cm,fk.split('->',1)[0]+'->'+fk.split('->',1)[1].split('(')[0]))
    invoke_facts=[method_facts(prev,cm,k) for k in invoke_keys]
    fallback_facts=[method_facts(prev,cm,k) for k in fallback_keys]
    src=source_role(repo)
    man=manifest_contract(hi_apks);svc=service_side(prev,hm)
    sc=prev.service_connection_classes(cm);desc=prev.descriptor_candidates_from_sc(sc);client_desc=MEDIA_IFACE if any(d.get('descriptor')==MEDIA_IFACE for d in desc) else None
    aar=aar_find(x.cxrl_aar)
    # Determine fallback intent from bind sites first, then from call-site constants if visible.
    fallback_bind=[b for b in binds if b['caller'] in fallback_keys]
    fbi=(fallback_bind[0].get('intent') if fallback_bind else None) or {}
    fb_action=fbi.get('action');fb_pkg=fbi.get('package');fb_comp=(fbi.get('component') or {})
    # Constant arguments passed into fallback can close fields that the old intra-method simulator could not.
    for call in fallback_calls:
        vals=[a.get('value') for a in call.get('args',[]) if isinstance(a,dict) and a.get('kind')=='string']
        if MEDIA_ACTION in vals and not fb_action:fb_action=MEDIA_ACTION
        if HI_GLOBAL in vals and not fb_pkg:fb_pkg=HI_GLOBAL
        if SERVICE_DOT in vals and not fb_comp.get('class'):fb_comp={'package':HI_GLOBAL,'class':SERVICE_DOT}
    ext_intent=(ext_binds[0].get('intent') if ext_binds else None) or {}
    ext_action=ext_intent.get('action');ext_pkg=ext_intent.get('package')
    global_resolves=man['known_action_resolves_to_cxrlinkservice']
    if ext_path:ext_disp='REACHABLE_FROM_CUSTOM_SDK_ROOTS'
    elif ext_targets:ext_disp='PRESENT_BUT_NO_STATIC_REACHABILITY_FROM_CUSTOM_SDK_ROOTS'
    else:ext_disp='CLASS_OR_METHOD_NOT_PRESENT'
    direct_fallback=any(any('bindServiceFallback' in i for i in (f or {}).get('invokes',[])) for f in invoke_facts)
    if src['available'] and src['fallback_call_in_catch']:fallback_role='ERROR_RECOVERY_FALLBACK_SOURCE_LEXICALLY_CORROBORATED'
    elif direct_fallback:fallback_role='DIRECTLY_INVOKED_BY_INVOKE_SDK_CONNECT_CONDITION_NOT_STatically_CLOSED'.replace('STatically','STATICALLY')
    else:fallback_role='FALLBACK_ROLE_UNRESOLVED'
    if global_resolves and fb_action==MEDIA_ACTION and (fb_pkg in (HI_GLOBAL,None) or fb_comp.get('package')==HI_GLOBAL):fb_global='KNOWN_ACTION_GLOBAL_SERVICE_RESOLUTION_CORROBORATED'
    elif global_resolves:fb_global='GLOBAL_MANIFEST_ACTION_MAPPING_PROVEN_FALLBACK_INTENT_FIELDS_PARTIAL'
    else:fb_global='GLOBAL_PACKAGE_INTENT_RESOLUTION_UNRESOLVED'
    if svc['exact']:service_gate='SERVICE_SIDE_EXACT'
    elif svc['disposition']!='SERVICE_SIDE_IMEDIASTREAMSERVICE_CORROBORATION_UNRESOLVED':service_gate='SERVICE_SIDE_PARTIAL'
    else:service_gate='SERVICE_SIDE_UNRESOLVED'
    if ext_disp.startswith('PRESENT_BUT') and fb_global.startswith('KNOWN_ACTION_GLOBAL') and client_desc==MEDIA_IFACE:
        dep='CUSTOM_FALLBACK_GLOBAL_SERVICE_PATH_CORROBORATED_EXTERNALAPPCLIENT_NOT_REACHABLE'
    elif ext_disp=='REACHABLE_FROM_CUSTOM_SDK_ROOTS' and client_desc==MEDIA_IFACE:
        dep='EXTERNALAPPCLIENT_REACHABLE_IMEDIASTREAMSERVICE_CLIENT_PATH_CORROBORATED'
    else:dep='SDK_VS_FALLBACK_DEPENDENCY_PATH_PARTIAL'
    replacement='READY_FOR_MINIMUM_BINDER_SURFACE_ENUMERATION' if client_desc==MEDIA_IFACE and global_resolves and service_gate!='SERVICE_SIDE_UNRESOLVED' else 'NOT_READY_SERVICE_OR_INTENT_CLOSURE_INCOMPLETE'
    result={
      'schema':'rokid.test21-r3-3-4-2-1.sdk-fallback-global-service.v1','analysis':'PASS',
      'inputs':{'custom_apk_count':len(custom_apks),'hi_rokid_apk_count':len(hi_apks),'custom_apk_sha256':[sha256(p) for p in custom_apks],'hi_rokid_apk_sha256':[sha256(p) for p in hi_apks],'cxrl_aar_identity':'PASS' if aar else 'NOT_LOCALLY_FOUND','cxrl_aar_sha256':sha256(aar) if aar else None},
      'sdk_vs_fallback':{'invoke_sdk_connect_methods':invoke_facts,'fallback_methods':fallback_facts,'fallback_callsites':fallback_calls,'direct_fallback_call':direct_fallback,'source_corroboration':src,'fallback_role':fallback_role},
      'external_app_client':{'target_methods':ext_targets,'expanded_call_path_from_custom_roots':ext_path,'reachability_disposition':ext_disp,'bind_sites':ext_binds,'intent_action':ext_action,'intent_package':ext_pkg},
      'dispatch_expansion_count':len(dispatch),
      'global_manifest':man,
      'fallback_intent':{'action':fb_action,'package':fb_pkg,'component_package':fb_comp.get('package'),'component_class':fb_comp.get('class'),'global_resolution_disposition':fb_global},
      'client_binder':{'descriptor':client_desc,'descriptor_exact':bool(client_desc)},
      'service_side':svc,
      'closure':{'dependency_path_disposition':dep,'service_side_gate':service_gate,'replacement_feasibility_gate':replacement},
      'proof_boundary':'OFFLINE_STATIC_APK_SET_ALL_SPLITS_PLUS_REPO_SOURCE_LEXICAL_CORROBORATION_NO_RUNTIME_NO_NATIVE_CALLSTACK',
      'device_operation':'NONE'}
    (out/'r3-3-4-2-1-private.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    san=json.loads(json.dumps(result));san['inputs'].pop('custom_apk_sha256',None);san['inputs'].pop('hi_rokid_apk_sha256',None);san['sdk_vs_fallback']['source_corroboration'].pop('file_sha256',None)
    (out/'sanitized/test21-r3-3-4-2-1-summary.json').write_text(json.dumps(san,indent=2,sort_keys=True)+'\n')
    cxr_actions=sorted({a for s in man['cxrlinkservice'] for a in s.get('actions',[])})
    lines=[
      'TEST21_R3_3_4_2_1_ANALYSIS=PASS',
      'MODE=OFFLINE_EXISTING_EVIDENCE_ONLY',
      'CUSTOM_APK_SPLIT_COUNT='+str(len(custom_apks)),
      'HI_ROKID_APK_SPLIT_COUNT='+str(len(hi_apks)),
      'CXR_L_AAR_IDENTITY='+('PASS' if aar else 'NOT_LOCALLY_FOUND_MERGED_APK_ANALYSIS_USED'),
      'INVOKE_SDK_CONNECT_TO_FALLBACK_DIRECT_CALL='+('YES' if direct_fallback else 'NO'),
      'FALLBACK_ROLE='+fallback_role,
      'EXTERNAL_APP_CLIENT_REACHABILITY='+ext_disp,
      'EXTERNAL_APP_CLIENT_CALL_PATH=' + (' -> '.join(ext_path) if ext_path else 'NONE'),
      'EXTERNAL_APP_CLIENT_INTENT_ACTION='+(ext_action or 'UNRESOLVED'),
      'EXTERNAL_APP_CLIENT_INTENT_PACKAGE='+(ext_pkg or 'UNRESOLVED'),
      'GLOBAL_MANIFEST_PACKAGES='+(','.join(man['packages']) if man['packages'] else 'UNRESOLVED'),
      'GLOBAL_CXRLINKSERVICE_DECLARED='+('YES' if man['cxrlinkservice'] else 'NO'),
      'GLOBAL_CXRLINKSERVICE_ACTIONS='+(','.join(cxr_actions) if cxr_actions else 'NONE'),
      'KNOWN_ACTION_RESOLVES_TO_GLOBAL_CXRLINKSERVICE='+('YES' if global_resolves else 'NO'),
      'FALLBACK_INTENT_ACTION='+(fb_action or 'UNRESOLVED'),
      'FALLBACK_INTENT_PACKAGE='+(fb_pkg or 'UNRESOLVED'),
      'FALLBACK_INTENT_COMPONENT_PACKAGE='+(fb_comp.get('package') or 'UNRESOLVED'),
      'FALLBACK_INTENT_COMPONENT_CLASS='+(fb_comp.get('class') or 'UNRESOLVED'),
      'FALLBACK_GLOBAL_INTENT_RESOLUTION='+fb_global,
      'CLIENT_BINDER_DESCRIPTOR='+(client_desc or 'UNRESOLVED'),
      'SERVICE_SIDE_CXRLINKSERVICE_CLASS_FOUND='+('YES' if svc['cxrlinkservice_class_found'] else 'NO'),
      'SERVICE_SIDE_CXRLINKSERVICE_ONBIND_COUNT='+str(len(svc['cxrlinkservice_onbind'])),
      'SERVICE_SIDE_IMEDIASTREAMSERVICE_STUB_SUBCLASS_COUNT='+str(len(svc['stub_subclasses'])),
      'SERVICE_SIDE_DESCRIPTOR_REFERENCE_COUNT='+str(svc['descriptor_reference_count']),
      'SERVICE_SIDE_CORROBORATION_DISPOSITION='+svc['disposition'],
      'DEPENDENCY_PATH_DISPOSITION='+dep,
      'REPLACEMENT_FEASIBILITY_GATE='+replacement,
      'PROOF_BOUNDARY='+result['proof_boundary'],
      'DEVICE_OPERATION=NONE','ADB_OPERATION=NONE','NEW_CAPTURE=NONE','HI_ROKID_FORCE_STOP=NONE','CXR_L_CONNECTION_ATTEMPT=NONE','PHOTO_OPERATION=NONE','AUDIO_OPERATION=NONE']
    (out/'sanitized/test21-r3-3-4-2-1-summary.txt').write_text('\n'.join(lines)+'\n');print('\n'.join(lines));return 0

if __name__=='__main__':raise SystemExit(main())
