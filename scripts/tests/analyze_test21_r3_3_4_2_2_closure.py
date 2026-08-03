#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, importlib.util, json, re, struct, zipfile
from collections import defaultdict
from pathlib import Path

HI_GLOBAL='com.rokid.sprite.global.aiapp'
CUSTOM='org.aimindseye.rokid.cxrphotoqualification'
SERVICE_DOT='com.rokid.sprite.aiapp.externalapp.service.CXRLinkService'
SERVICE_DESC='Lcom/rokid/sprite/aiapp/externalapp/service/CXRLinkService;'
MEDIA_ACTION='com.rokid.sprite.aiapp.externalapp.MEDIA_STREAM_SERVICE'
MEDIA_IFACE='com.rokid.sprite.aiapp.externalapp.IMediaStreamService'
MEDIA_IFACE_DESC='Lcom/rokid/sprite/aiapp/externalapp/IMediaStreamService;'
MEDIA_STUB='Lcom/rokid/sprite/aiapp/externalapp/IMediaStreamService$Stub;'
MEDIA_PROXY='Lcom/rokid/sprite/aiapp/externalapp/IMediaStreamService$Stub$Proxy;'
CONTROLLER='Lorg/aimindseye/rokid/cxrphotoqualification/CxrLPhotoController;'
STRING='Ljava/lang/String;'; INTENT='Landroid/content/Intent;'; COMPONENT='Landroid/content/ComponentName;'
TARGETS=[SERVICE_DESC,MEDIA_IFACE_DESC,MEDIA_STUB,MEDIA_PROXY]


def sha256(p:Path)->str:
 h=hashlib.sha256();
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()

def load_prev21(repo:Path):
 p=repo/'scripts/tests/analyze_test21_r3_3_4_2_1_closure.py'
 if not p.is_file():raise SystemExit('ERROR: r3.3.4.2.1 analyzer missing')
 sp=importlib.util.spec_from_file_location('prev21',p);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m

def apk_set(apkdir:Path,prefix:str):
 xs=sorted(apkdir.glob(prefix+'-*.apk')) or sorted(apkdir.glob(prefix+'*.apk'))
 return [p for p in xs if p.is_file()]

def field_key(f):return f['class']+'->'+f['name']+':'+f['type']

def static_string_fields(model):
 """Resolve const-string -> sput-object assignments in class initializers."""
 out={}; evidence=[]
 for m in model.methods:
  if m['name']!='<clinit>' or not m.get('code_off'):continue
  regs={}
  for x in model.method_ins.get(model.key(m),[]):
   k=x.get('kind')
   if k=='string':regs[x['dst']]={'kind':'string','value':x['value'],'pc':x['pc'],'source':'const-string'}
   elif k=='moveobj':regs[x['dst']]=regs.get(x['src'])
   elif x.get('op')==0x69 and len(x.get('raw',[]))>=2: # sput-object vAA, field@BBBB
    src=(x['raw'][0]>>8)&0xff; idx=x['raw'][1]
    try:f=m['dex'].fields[idx]
    except Exception:continue
    v=regs.get(src)
    if isinstance(v,dict) and v.get('kind')=='string':
     out[field_key(f)]=v['value'];evidence.append({'field':field_key(f),'value':v['value'],'method':model.key(m),'pc':x['pc']})
 return out,evidence

def string_return_summaries(model,static_fields):
 sums={}
 for _ in range(5):
  changed=False
  for m in model.methods:
   if m.get('ret')!=STRING or not m.get('code_off'):continue
   regs={};pending=None;ret=None
   for x in model.method_ins.get(model.key(m),[]):
    k=x.get('kind')
    if k=='string':regs[x['dst']]={'kind':'string','value':x['value'],'origin_pc':x['pc'],'origin':'const-string'}
    elif k=='moveobj':regs[x['dst']]=regs.get(x['src'])
    elif k=='fieldobj':
     fk=field_key(x['field']);val=static_fields.get(fk)
     regs[x['dst']]={'kind':'string','value':val,'origin_pc':x['pc'],'origin':'static-field:'+fk} if val is not None else {'kind':'field','field':fk,'type':x['field']['type']}
    elif k=='invoke':
     pending=sums.get(model.key(x['method']))
    elif k=='moveresultobj':
     if pending is not None:regs[x['dst']]=pending
     pending=None
    elif k=='returnobj':ret=regs.get(x['src'])
   if isinstance(ret,dict) and ret.get('kind')=='string' and ret.get('value') is not None:
    k=model.key(m)
    if sums.get(k)!=ret:sums[k]=ret;changed=True
  if not changed:break
 return sums

def safe_value(v):
 if not isinstance(v,dict):return None
 if v.get('kind')=='string':return {'kind':'string','value':v.get('value'),'origin':v.get('origin'),'origin_pc':v.get('origin_pc')}
 if v.get('kind') in ('field','param','object','component'):
  return {k:v.get(k) for k in ('kind','type','field','name','owner','package','class','param_index','origin','origin_pc') if v.get(k) is not None}
 if v.get('kind')=='int':return {'kind':'int','value':v.get('value'),'origin_pc':v.get('origin_pc')}
 return {'kind':v.get('kind'),'type':v.get('type'),'origin':v.get('origin')}

def init_params(m):
 """Label incoming parameter registers using DEX code_item registers/ins sizes."""
 co=m.get('code_off') or 0
 if not co:return {}
 d=m['dex'].data;regs_size=struct.unpack_from('<H',d,co)[0];ins_size=struct.unpack_from('<H',d,co+2)[0]
 start=regs_size-ins_size;regs={};cur=start;idx=-1
 if not (m.get('access',0)&0x8):
  regs[cur]={'kind':'param','param_index':-1,'type':m['class'],'name':'this'};cur+=1
 for i,t in enumerate(m.get('params') or []):
  regs[cur]={'kind':'param','param_index':i,'type':t,'name':'arg'+str(i)};cur+=2 if t in ('J','D') else 1
 return regs

def trace_fallback(model,key,static_fields,string_summaries):
 m=model.by_key.get(key)
 if not m:return {'method':key,'found':False,'bind_events':[]}
 regs=init_params(m);pending=None;events=[];intents={}
 def mutate(reg,fn):
  obj=regs.get(reg)
  if isinstance(obj,dict) and obj.get('kind')=='intent':
   obj=dict(obj);fn(obj);regs[reg]=obj;intents[obj['object_id']]=obj
   return obj
  return None
 for x in model.method_ins.get(key,[]):
  k=x.get('kind')
  if k=='string':regs[x['dst']]={'kind':'string','value':x['value'],'origin':'const-string','origin_pc':x['pc']}
  elif k=='const':regs[x['dst']]={'kind':'int','value':x['value'],'origin_pc':x['pc']}
  elif k=='class':regs[x['dst']]={'kind':'class','value':x['value'],'origin_pc':x['pc']}
  elif k=='new':
   if x['value']==INTENT:
    obj={'kind':'intent','type':INTENT,'object_id':'intent@'+str(x['pc']),'created_pc':x['pc'],'action':None,'package':None,'component':None,'extras':{}}
    regs[x['dst']]=obj;intents[obj['object_id']]=obj
   else:regs[x['dst']]={'kind':'object','type':x['value'],'origin_pc':x['pc']}
  elif k=='moveobj':regs[x['dst']]=regs.get(x['src'])
  elif k=='fieldobj':
   fk=field_key(x['field']);val=static_fields.get(fk)
   regs[x['dst']]={'kind':'string','value':val,'origin':'static-field:'+fk,'origin_pc':x['pc']} if val is not None and x['field']['type']==STRING else {'kind':'field','field':fk,'type':x['field']['type'],'name':x['field']['name'],'owner':x['field']['class'],'origin_pc':x['pc']}
  elif k=='invoke':
   im=x['method'];ik=model.key(im);args=[regs.get(r) for r in x.get('regs',[])];pending=None
   if im['class']==INTENT and im['name']=='<init>' and x.get('regs'):
    r0=x['regs'][0];obj=regs.get(r0)
    if not (isinstance(obj,dict) and obj.get('kind')=='intent'):
     obj={'kind':'intent','type':INTENT,'object_id':'intent-init@'+str(x['pc']),'created_pc':x['pc'],'action':None,'package':None,'component':None,'extras':{}}
    obj=dict(obj);obj['constructor_pc']=x['pc']
    if len(args)>1 and isinstance(args[1],dict) and args[1].get('kind')=='string':obj['action']=args[1].get('value');obj['action_origin']=safe_value(args[1])
    regs[r0]=obj;intents[obj['object_id']]=obj
   elif im['class']==COMPONENT and im['name']=='<init>' and x.get('regs'):
    if len(args)>=3 and all(isinstance(a,dict) and a.get('kind')=='string' for a in args[1:3]):
     regs[x['regs'][0]]={'kind':'component','type':COMPONENT,'package':args[1]['value'],'class':args[2]['value'],'origin_pc':x['pc']}
   elif im['class']==INTENT and im['name'] in ('setAction','setPackage','setComponent','setClassName') and x.get('regs'):
    def fn(obj):
     if im['name']=='setAction' and len(args)>1 and isinstance(args[1],dict):obj['action']=args[1].get('value');obj['action_origin']=safe_value(args[1])
     elif im['name']=='setPackage' and len(args)>1 and isinstance(args[1],dict):obj['package']=args[1].get('value');obj['package_origin']=safe_value(args[1])
     elif im['name']=='setComponent' and len(args)>1 and isinstance(args[1],dict):obj['component']=safe_value(args[1]);obj['component_origin_pc']=x['pc']
     elif im['name']=='setClassName' and len(args)>2 and all(isinstance(a,dict) for a in args[1:3]):obj['component']={'kind':'component','package':args[1].get('value'),'class':args[2].get('value'),'origin_pc':x['pc']}
    obj=mutate(x['regs'][0],fn);pending=obj
   elif im['class']==INTENT and im['name']=='putExtra' and x.get('regs'):
    obj=regs.get(x['regs'][0])
    if isinstance(obj,dict) and obj.get('kind')=='intent' and len(args)>=3 and isinstance(args[1],dict) and args[1].get('kind')=='string':
     obj=dict(obj);ex=dict(obj.get('extras') or {});keyname=args[1].get('value');ex[keyname]={'value_source':safe_value(args[2]),'put_pc':x['pc']};obj['extras']=ex;regs[x['regs'][0]]=obj;intents[obj['object_id']]=obj;pending=obj
   elif im['name']=='bindService' and im['class'].startswith('Landroid/content/'):
    intent=None;conn=None;flags=None
    for a in args:
     if isinstance(a,dict) and a.get('kind')=='intent':intent=a
    if len(args)>=3 and isinstance(args[-2],dict):conn=args[-2]
    if args and isinstance(args[-1],dict) and args[-1].get('kind')=='int':flags=args[-1].get('value')
    events.append({'pc':x['pc'],'invoke':ik,'intent':intent,'service_connection':safe_value(conn),'flags':flags,'args':[safe_value(a) for a in args]})
   elif ik in string_summaries:pending=string_summaries[ik]
   elif im.get('ret')!= 'V':pending={'kind':'invoke_result','type':im.get('ret'),'origin':ik,'origin_pc':x['pc']}
  elif k=='moveresultobj':
   if pending is not None:regs[x['dst']]=pending
   pending=None
 return {'method':key,'found':True,'bind_events':events,'static_field_count':len(static_fields)}

def source_decisions(repo:Path,prev21):
 p=prev21.find_controller_source(repo);out={'available':False,'reasons':[],'reason_callers':{},'success_bypass_corroboration':False}
 if not p:return out
 t=p.read_text(errors='replace');out['available']=True
 for reason in re.findall(r'bindServiceFallback\s*\(\s*"([^"]+)"',t):
  if reason not in out['reasons']:out['reasons'].append(reason)
 for name in ('invokeSdkConnect','startConnection'):
  b=prev21.extract_method_body(t,name) or ''
  rs=re.findall(r'bindServiceFallback\s*\(\s*"([^"]+)"',b)
  if rs:out['reason_callers'][name]=sorted(set(rs))
 # Bounded lexical corroboration only.
 b=prev21.extract_method_body(t,'invokeSdkConnect') or ''
 out['success_bypass_corroboration']=bool(re.search(r'if\s*\([^)]*(?:connected|result|success)[^)]*\)\s*\{?\s*return\s+true\s*;',b,re.S|re.I))
 return out

def census_apks(apks,base):
 hits={t:{'class_defs':[],'type_refs':[],'string_refs':[],'raw_entry_hits':[]} for t in TARGETS};stub_sub=[];dex_count=0
 for ai,apk in enumerate(apks,1):
  with zipfile.ZipFile(apk) as z:
   for name in sorted(z.namelist()):
    try:data=z.read(name)
    except Exception:continue
    # Raw entry reference census is bounded to exact service/interface textual forms.
    for t in TARGETS:
     variants=[t.encode(), base.desc_to_dot(t).encode()]
     if any(v in data for v in variants):hits[t]['raw_entry_hits'].append({'apk_index':ai,'entry':name})
    if not re.fullmatch(r'classes(?:\d+)?\.dex',Path(name).name):continue
    dex_count+=1
    try:d=base.Dex(data,Path(name).name)
    except Exception:continue
    for t in TARGETS:
     if t in d.classes:
      c=d.classes[t];hits[t]['class_defs'].append({'apk_index':ai,'dex':name,'super':c.get('super'),'interfaces':c.get('interfaces') or [],'method_count':len(c.get('methods') or [])})
     if t in d.types:hits[t]['type_refs'].append({'apk_index':ai,'dex':name})
     if t in d.strings or base.desc_to_dot(t) in d.strings:hits[t]['string_refs'].append({'apk_index':ai,'dex':name})
    for desc,c in d.classes.items():
     if c.get('super')==MEDIA_STUB:stub_sub.append({'apk_index':ai,'dex':name,'class':desc,'super':MEDIA_STUB,'interfaces':c.get('interfaces') or []})
 # de-duplicate raw entry hits
 for t in TARGETS:
  for k in hits[t]:
   seen=set();new=[]
   for x in hits[t][k]:
    sig=json.dumps(x,sort_keys=True)
    if sig not in seen:seen.add(sig);new.append(x)
   hits[t][k]=new
 return {'apk_count':len(apks),'dex_count':dex_count,'targets':hits,'stub_subclasses':stub_sub}

def location_disposition(item):
 if item['class_defs']:return 'CLASS_DEF_FOUND'
 if item['type_refs'] or item['string_refs'] or item['raw_entry_hits']:return 'REFERENCE_ONLY_NO_CLASS_DEF'
 return 'NOT_PRESENT_IN_PRESERVED_APK_SET'

def service_impl(base,hm,census):
 svc=hm.classes.get(SERVICE_DESC);subs=[d for d,c in hm.classes.items() if c.get('super')==MEDIA_STUB];on=[]
 if svc:
  for m in hm.methods_of(SERVICE_DESC,'onBind'):
   sim=base.simulate(hm,m,{})
   ret=sim.get('return');refs=[e['invoke'] for e in sim.get('events',[])]
   types=[]
   if isinstance(ret,dict) and ret.get('type'):types.append(ret.get('type'))
   for x in hm.method_ins.get(hm.key(m),[]):
    if x.get('kind')=='new':types.append(x.get('value'))
    elif x.get('kind')=='fieldobj':types.append(x.get('field',{}).get('type'))
   related=sorted({t for t in types if t and (t==MEDIA_STUB or t in subs)})
   for r in refs:
    for s in subs:
     if s in r:related.append(s)
   related=sorted(set(related));on.append({'method':hm.key(m),'return_value':safe_value(ret),'stub_lineage':related,'invoke_count':len(refs)})
 exact=bool(svc and on and any(x['stub_lineage'] for x in on))
 if exact:disp='EXACT_CXRLINKSERVICE_ONBIND_TO_IMEDIASTREAMSERVICE_STUB_IMPLEMENTATION'
 elif svc and on and subs:disp='SERVICE_AND_ONBIND_AND_STUB_IMPLEMENTATION_PRESENT_LINK_UNRESOLVED'
 elif svc and on:disp='SERVICE_ONBIND_FOUND_BINDER_IMPLEMENTATION_UNRESOLVED'
 elif svc:disp='CXRLINKSERVICE_CLASS_FOUND_ONBIND_NOT_RECOVERED'
 elif subs:disp='IMEDIASTREAMSERVICE_STUB_IMPLEMENTATION_FOUND_CXRLINKSERVICE_CLASS_ABSENT'
 else:disp='SERVICE_IMPLEMENTATION_NOT_RECOVERED_FROM_PRESERVED_DEX_SET'
 return {'cxrlinkservice_class_found':bool(svc),'onbind':on,'stub_subclasses':sorted(subs),'exact':exact,'disposition':disp,
         'service_location_disposition':location_disposition(census['targets'][SERVICE_DESC]),'stub_location_disposition':location_disposition(census['targets'][MEDIA_STUB])}

def main():
 a=argparse.ArgumentParser();a.add_argument('--repo',required=True);a.add_argument('--r3341-evidence',required=True);a.add_argument('--output',required=True);x=a.parse_args()
 repo=Path(x.repo).resolve();ev=Path(x.r3341_evidence).resolve();out=Path(x.output).resolve();(out/'sanitized').mkdir(parents=True,exist_ok=True)
 prev21=load_prev21(repo);base=prev21.load_prev(repo);apkdir=ev/'raw/apks';custom=apk_set(apkdir,'custom');hi=apk_set(apkdir,'hi')
 if not custom or not hi:raise SystemExit('ERROR: preserved r3.3.4.1 APK set unavailable')
 cm=prev21.load_model(base,custom);hm=prev21.load_model(base,hi)
 sf,sfe=static_string_fields(cm);ss=string_return_summaries(cm,sf)
 fallback_keys=sorted(k for k in cm.by_key if k.startswith(CONTROLLER+'->bindServiceFallback'))
 traces=[trace_fallback(cm,k,sf,ss) for k in fallback_keys]
 bind_events=[e for t in traces for e in t['bind_events']]
 # retain only events carrying an Intent
 bind_events=[e for e in bind_events if isinstance(e.get('intent'),dict)]
 exact_events=[]
 for e in bind_events:
  i=e['intent'];extras=sorted((i.get('extras') or {}).keys())
  if i.get('action')==MEDIA_ACTION and i.get('package')==HI_GLOBAL and e.get('flags')==1:exact_events.append(e)
 chosen=exact_events[0] if len(exact_events)==1 else (exact_events[0] if exact_events and all((q['intent'].get('action'),q['intent'].get('package'),q.get('flags'))==(MEDIA_ACTION,HI_GLOBAL,1) for q in exact_events) else None)
 intent_exact=chosen is not None
 extras=sorted((chosen['intent'].get('extras') or {}).keys()) if chosen else []
 srcdec=source_decisions(repo,prev21)
 # DEX callsite reason labels from previous bounded simulator.
 fallback_calls=[]
 for fk in fallback_keys:fallback_calls.extend(prev21.invocation_args_to(base,cm,fk.split('->',1)[0]+'->'+fk.split('->',1)[1].split('(')[0]))
 reason_pairs=[]
 for c in fallback_calls:
  vals=[z.get('value') for z in c.get('args',[]) if isinstance(z,dict) and z.get('kind')=='string']
  reasons=[v for v in vals if v in ('sdk_connect_returned_false','sdk_connect_method_missing','delayed_fallback')]
  for r in reasons:reason_pairs.append({'caller':c['caller'],'reason':r})
 census=census_apks(hi,base);impl=service_impl(base,hm,census)
 service_loc=location_disposition(census['targets'][SERVICE_DESC]);iface_loc=location_disposition(census['targets'][MEDIA_IFACE_DESC]);stub_loc=location_disposition(census['targets'][MEDIA_STUB]);proxy_loc=location_disposition(census['targets'][MEDIA_PROXY])
 if intent_exact and impl['exact']:gate='READY_FOR_MINIMUM_COMPATIBLE_SERVICE_SURFACE_ENUMERATION'
 elif intent_exact:gate='INTENT_CONTRACT_CLOSED_SERVICE_IMPLEMENTATION_STILL_UNRESOLVED'
 else:gate='NOT_READY_FALLBACK_INTENT_DATAFLOW_OR_SERVICE_IMPLEMENTATION_INCOMPLETE'
 if intent_exact:intent_disp='EXACT_REGISTER_DATAFLOW_TO_BIND_SERVICE'
 elif bind_events:intent_disp='BIND_EVENT_RECOVERED_REGISTER_DATAFLOW_PARTIAL'
 else:intent_disp='FALLBACK_BIND_EVENT_NOT_RECOVERED'
 result={'schema':'rokid.test21-r3-3-4-2-2.fallback-dataflow-class-location.v1','analysis':'PASS','mode':'OFFLINE_EXISTING_EVIDENCE_ONLY',
  'inputs':{'custom_apk_count':len(custom),'hi_apk_count':len(hi)},
  'fallback':{'method_keys':fallback_keys,'static_string_field_evidence':sfe,'string_return_summary_count':len(ss),'bind_events':bind_events,'exact_event_count':len(exact_events),'intent_disposition':intent_disp,
              'action':chosen['intent'].get('action') if chosen else None,'package':chosen['intent'].get('package') if chosen else None,'flags':chosen.get('flags') if chosen else None,'extra_keys':extras,
              'service_connection':chosen.get('service_connection') if chosen else None},
  'sdk_decisions':{'source':srcdec,'dex_reason_callsites':reason_pairs},
  'class_location':census,
  'service_implementation':impl,
  'closure':{'fallback_intent_exact':intent_exact,'service_implementation_exact':impl['exact'],'replacement_feasibility_gate':gate},
  'proof_boundary':'OFFLINE_REGISTER_ORIGIN_TRACE_PLUS_ALL_PRESERVED_APK_DEX_CLASS_DEF_CENSUS_NO_RUNTIME_NO_NATIVE_CALLSTACK','device_operation':'NONE'}
 (out/'r3-3-4-2-2-private.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
 # sanitize: do not expose hashes, local filenames or actual auth/token values. Only structural values and APK indices/DEX names.
 san=json.loads(json.dumps(result));san['fallback'].pop('static_string_field_evidence',None)
 for e in san['fallback'].get('bind_events',[]):
  i=e.get('intent') or {};ex=i.get('extras') or {}
  i['extras']={k:{'value_source_kind':((v.get('value_source') or {}).get('kind') if isinstance(v,dict) else None)} for k,v in ex.items()}
 (out/'sanitized/test21-r3-3-4-2-2-summary.json').write_text(json.dumps(san,indent=2,sort_keys=True)+'\n')
 reasons=sorted(set(x['reason'] for x in reason_pairs) | set(srcdec.get('reasons') or []))
 svcdefs=census['targets'][SERVICE_DESC]['class_defs'];stubdefs=census['targets'][MEDIA_STUB]['class_defs'];subdefs=census['stub_subclasses']
 lines=[
 'TEST21_R3_3_4_2_2_ANALYSIS=PASS','MODE=OFFLINE_EXISTING_EVIDENCE_ONLY',
 'CUSTOM_APK_SPLIT_COUNT='+str(len(custom)),'HI_ROKID_APK_SPLIT_COUNT='+str(len(hi)),'HI_ROKID_DEX_COUNT='+str(census['dex_count']),
 'FALLBACK_METHOD_COUNT='+str(len(fallback_keys)),'FALLBACK_BIND_EVENT_COUNT='+str(len(bind_events)),'FALLBACK_INTENT_DATAFLOW_DISPOSITION='+intent_disp,
 'FALLBACK_INTENT_ACTION='+(result['fallback']['action'] or 'UNRESOLVED'),'FALLBACK_INTENT_PACKAGE='+(result['fallback']['package'] or 'UNRESOLVED'),'FALLBACK_BIND_FLAGS='+(str(result['fallback']['flags']) if result['fallback']['flags'] is not None else 'UNRESOLVED'),
 'FALLBACK_EXTRA_KEYS='+(','.join(extras) if extras else 'NONE'),'FALLBACK_AUTH_PACKAGE_EXTRA='+('YES' if 'auth_package' in extras else 'NO'),'FALLBACK_AUTH_TOKEN_EXTRA='+('YES' if 'auth_token' in extras else 'NO'),
 'SDK_CONNECT_FALLBACK_REASONS='+(','.join(reasons) if reasons else 'UNRESOLVED'),'SDK_CONNECT_RETURNED_FALSE_BRANCH='+('PROVEN' if 'sdk_connect_returned_false' in reasons else 'UNRESOLVED'),'SDK_CONNECT_METHOD_MISSING_BRANCH='+('PROVEN' if 'sdk_connect_method_missing' in reasons else 'UNRESOLVED'),'DELAYED_FALLBACK_BRANCH='+('PROVEN' if 'delayed_fallback' in reasons else 'UNRESOLVED'),
 'CXR_LINK_SERVICE_CLASS_LOCATION='+service_loc,'CXR_LINK_SERVICE_CLASS_DEF_COUNT='+str(len(svcdefs)),
 'IMEDIASTREAMSERVICE_INTERFACE_LOCATION='+iface_loc,'IMEDIASTREAMSERVICE_STUB_LOCATION='+stub_loc,'IMEDIASTREAMSERVICE_STUB_CLASS_DEF_COUNT='+str(len(stubdefs)),'IMEDIASTREAMSERVICE_PROXY_LOCATION='+proxy_loc,
 'IMEDIASTREAMSERVICE_STUB_SUBCLASS_COUNT='+str(len(subdefs)),'SERVICE_SIDE_CXRLINKSERVICE_ONBIND_COUNT='+str(len(impl['onbind'])),'SERVICE_IMPLEMENTATION_DISPOSITION='+impl['disposition'],'SERVICE_IMPLEMENTATION_EXACT='+('YES' if impl['exact'] else 'NO'),
 'REPLACEMENT_FEASIBILITY_GATE='+gate,'PROOF_BOUNDARY='+result['proof_boundary'],'DEVICE_OPERATION=NONE','ADB_OPERATION=NONE','NEW_CAPTURE=NONE','HI_ROKID_FORCE_STOP=NONE','CXR_L_CONNECTION_ATTEMPT=NONE','PHOTO_OPERATION=NONE','AUDIO_OPERATION=NONE']
 (out/'sanitized/test21-r3-3-4-2-2-summary.txt').write_text('\n'.join(lines)+'\n');print('\n'.join(lines));return 0
if __name__=='__main__':raise SystemExit(main())
