#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re, struct, zipfile
from collections import defaultdict, deque
from pathlib import Path

HI_PACKAGE='com.rokid.sprite.global.aiapp'
CUSTOM_PACKAGE='org.aimindseye.rokid.cxrphotoqualification'
CUSTOM_PREFIX='Lorg/aimindseye/rokid/'
CXR_PREFIX='Lcom/rokid/cxr/'
SERVICE='Lcom/rokid/sprite/aiapp/externalapp/service/CXRLinkService;'
SERVICE_DOT='com.rokid.sprite.aiapp.externalapp.service.CXRLinkService'
KNOWN_ACTION='rokid.sprite.aiapp.externalapp.MEDIA_STREAM_SERVICE'
EXPECTED_AAR_SHA='c23d34b3adc60d3fa16001645ce6172eaf4554173e7ef9c078595e672d50824e'
SERVICE_CONNECTION='Landroid/content/ServiceConnection;'
IBINDER='Landroid/os/IBinder;'
INTENT='Landroid/content/Intent;'
COMPONENT='Landroid/content/ComponentName;'

ACC_PUBLIC=0x1; ACC_STATIC=0x8; ACC_INTERFACE=0x200; ACC_ABSTRACT=0x400

def sha256(p:Path)->str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def u16(b,o):return struct.unpack_from('<H',b,o)[0]
def u32(b,o):return struct.unpack_from('<I',b,o)[0]
def sleb_sign(v,bits): return v-(1<<bits) if v&(1<<(bits-1)) else v

def uleb(b,o):
    v=0;s=0
    for _ in range(5):
        x=b[o];o+=1;v|=(x&0x7f)<<s
        if not x&0x80:return v,o
        s+=7
    raise ValueError('bad uleb128')

def desc_to_dot(s):
    if s and s.startswith('L') and s.endswith(';'):return s[1:-1].replace('/','.')
    return s

def proto_desc(ret,params):return '('+''.join(params)+')'+ret

def width(op):
    if op in (0x02,0x05,0x08,0x13,0x15,0x16,0x19,0x1a,0x1c,0x1f,0x20,0x22,0x23):return 2
    if op in (0x03,0x06,0x09,0x14,0x17,0x1b,0x24,0x25,0x26,0x2a,0x2b,0x2c):return 3
    if op==0x18:return 5
    if 0x2d<=op<=0x3d:return 2
    if 0x44<=op<=0x6d:return 2
    if 0x6e<=op<=0x72 or 0x74<=op<=0x78:return 3
    if 0x90<=op<=0xaf:return 2
    if 0xd0<=op<=0xe2:return 2
    if op in (0xfa,0xfb):return 4
    if op in (0xfc,0xfd):return 3
    return 1

class Dex:
    def __init__(self,data:bytes,name='classes.dex'):
        self.data=data;self.name=name
        if len(data)<0x70 or not data.startswith(b'dex\n'):raise ValueError('not dex')
        self.strings=self._strings();self.types=self._types();self.protos=self._protos();self.fields=self._fields();self.methods=self._methods();self.classes=self._classes();self.code={};self._class_data()
    def _strings(self):
        n,o=u32(self.data,0x38),u32(self.data,0x3c);out=[]
        for i in range(n):
            p=u32(self.data,o+4*i);_,p=uleb(self.data,p);e=self.data.find(b'\0',p)
            raw=self.data[p:e if e>=0 else len(self.data)]
            try:s=raw.decode('utf-8','replace')
            except:s=''
            out.append(s)
        return out
    def _types(self):
        n,o=u32(self.data,0x40),u32(self.data,0x44);return [self.strings[u32(self.data,o+4*i)] for i in range(n)]
    def _type_list(self,o):
        if not o:return []
        n=u32(self.data,o);return [self.types[u16(self.data,o+4+2*i)] for i in range(n)]
    def _protos(self):
        n,o=u32(self.data,0x48),u32(self.data,0x4c);out=[]
        for i in range(n):
            shorty,ret,po=struct.unpack_from('<III',self.data,o+12*i);ps=self._type_list(po);out.append({'ret':self.types[ret],'params':ps,'desc':proto_desc(self.types[ret],ps)})
        return out
    def _fields(self):
        n,o=u32(self.data,0x50),u32(self.data,0x54);out=[]
        for i in range(n):
            c,t,nm=struct.unpack_from('<HHI',self.data,o+8*i);out.append({'class':self.types[c],'type':self.types[t],'name':self.strings[nm]})
        return out
    def _methods(self):
        n,o=u32(self.data,0x58),u32(self.data,0x5c);out=[]
        for i in range(n):
            c,p,nm=struct.unpack_from('<HHI',self.data,o+8*i);q=self.protos[p];out.append({'idx':i,'class':self.types[c],'name':self.strings[nm],'proto':q['desc'],'ret':q['ret'],'params':q['params'],'access':0,'code_off':0})
        return out
    def _classes(self):
        n,o=u32(self.data,0x60),u32(self.data,0x64);out={}
        for i in range(n):
            vals=struct.unpack_from('<IIIIIIII',self.data,o+32*i);ci,acc,sup,io,src,ann,cd,sv=vals
            d=self.types[ci];out[d]={'desc':d,'access':acc,'super':None if sup==0xffffffff else self.types[sup],'interfaces':self._type_list(io),'class_data_off':cd,'methods':[]}
        return out
    def _class_data(self):
        for c in self.classes.values():
            p=c['class_data_off']
            if not p:continue
            sf,p=uleb(self.data,p);inf,p=uleb(self.data,p);dm,p=uleb(self.data,p);vm,p=uleb(self.data,p)
            idx=0
            for _ in range(sf+inf):d,p=uleb(self.data,p);_,p=uleb(self.data,p);idx+=d
            idx=0
            for _ in range(dm):
                d,p=uleb(self.data,p);acc,p=uleb(self.data,p);co,p=uleb(self.data,p);idx+=d;self.methods[idx]['access']=acc;self.methods[idx]['code_off']=co;c['methods'].append(idx)
            idx=0
            for _ in range(vm):
                d,p=uleb(self.data,p);acc,p=uleb(self.data,p);co,p=uleb(self.data,p);idx+=d;self.methods[idx]['access']=acc;self.methods[idx]['code_off']=co;c['methods'].append(idx)
    def insns(self,midx):
        m=self.methods[midx];co=m.get('code_off') or 0
        if not co:return []
        sz=u32(self.data,co+12);base=co+16;units=list(struct.unpack_from('<'+'H'*sz,self.data,base));out=[];i=0
        while i<len(units):
            u=units[i];op=u&0xff;w=width(op);raw=units[i:i+w];item={'pc':i,'op':op,'raw':raw}
            try:
                if op==0x12:
                    a=(u>>8)&0xf;lit=(u>>12)&0xf;item.update(kind='const',dst=a,value=sleb_sign(lit,4))
                elif op==0x13:item.update(kind='const',dst=(u>>8)&0xff,value=sleb_sign(raw[1],16))
                elif op==0x14:item.update(kind='const',dst=(u>>8)&0xff,value=sleb_sign(raw[1]|(raw[2]<<16),32))
                elif op==0x1a:item.update(kind='string',dst=(u>>8)&0xff,value=self.strings[raw[1]])
                elif op==0x1b:item.update(kind='string',dst=(u>>8)&0xff,value=self.strings[raw[1]|(raw[2]<<16)])
                elif op==0x1c:item.update(kind='class',dst=(u>>8)&0xff,value=self.types[raw[1]])
                elif op==0x22:item.update(kind='new',dst=(u>>8)&0xff,value=self.types[raw[1]])
                elif op==0x07:item.update(kind='moveobj',dst=(u>>8)&0xf,src=(u>>12)&0xf)
                elif op==0x08:item.update(kind='moveobj',dst=(u>>8)&0xff,src=raw[1])
                elif op==0x09:item.update(kind='moveobj',dst=(u>>8)&0xff,src=raw[1]|(raw[2]<<16))
                elif op==0x54:
                    a=(u>>8)&0xf;b=(u>>12)&0xf;f=self.fields[raw[1]];item.update(kind='fieldobj',dst=a,src=b,field=f)
                elif op==0x62:
                    f=self.fields[raw[1]];item.update(kind='fieldobj',dst=(u>>8)&0xff,src=None,field=f)
                elif 0x6e<=op<=0x72:
                    cnt=(u>>12)&0xf;g=(u>>8)&0xf;mr=self.methods[raw[1]];x=raw[2];regs=[x&0xf,(x>>4)&0xf,(x>>8)&0xf,(x>>12)&0xf,g][:cnt];item.update(kind='invoke',method=mr,regs=regs)
                elif 0x74<=op<=0x78:
                    cnt=(u>>8)&0xff;mr=self.methods[raw[1]];start=raw[2];item.update(kind='invoke',method=mr,regs=list(range(start,start+cnt)))
                elif op==0x0c:item.update(kind='moveresultobj',dst=(u>>8)&0xff)
                elif op==0x11:item.update(kind='returnobj',src=(u>>8)&0xff)
            except Exception:item['decode_error']=True
            out.append(item);i+=max(w,1)
        return out

class Model:
    def __init__(self):self.dexes=[];self.methods=[];self.classes={};self.fields=[];self.invoke_edges=defaultdict(set);self.reverse=defaultdict(set);self.method_ins={}
    @staticmethod
    def key(m):return m['class']+'->'+m['name']+m['proto']
    def add_apk(self,p:Path):
        with zipfile.ZipFile(p) as z:
            for n in sorted(z.namelist()):
                if re.fullmatch(r'classes(?:\d+)?\.dex',Path(n).name):
                    d=Dex(z.read(n),n);self.dexes.append(d)
                    for c,v in d.classes.items():self.classes[c]=dict(v,dex=d)
                    for f in d.fields:self.fields.append(dict(f,dex=d))
                    for m in d.methods:
                        mm=dict(m,dex=d);self.methods.append(mm)
        self._index()
    def _index(self):
        self.by_key={self.key(m):m for m in self.methods}
        for m in self.methods:
            if not m.get('code_off'):continue
            ins=m['dex'].insns(m['idx']);self.method_ins[self.key(m)]=ins
            for x in ins:
                if x.get('kind')=='invoke':
                    k=self.key(x['method']);self.invoke_edges[self.key(m)].add(k);self.reverse[k].add(self.key(m))
    def methods_of(self,cls,name=None):return [m for m in self.methods if m['class']==cls and (name is None or m['name']==name)]

def val_type(v):
    if isinstance(v,dict):return v.get('type')
    return None

def simulate(model:Model,m, summaries=None):
    summaries=summaries or {};regs={};pending=None;events=[];ret=None
    for x in model.method_ins.get(Model.key(m),[]):
        k=x.get('kind')
        if k=='string':regs[x['dst']]={'kind':'string','value':x['value']}
        elif k=='const':regs[x['dst']]={'kind':'int','value':x['value']}
        elif k=='class':regs[x['dst']]={'kind':'class','value':x['value']}
        elif k=='new':regs[x['dst']]={'kind':'object','type':x['value']}
        elif k=='moveobj':regs[x['dst']]=regs.get(x['src'])
        elif k=='fieldobj':regs[x['dst']]={'kind':'field','type':x['field']['type'],'name':x['field']['name'],'owner':x['field']['class']}
        elif k=='invoke':
            im=x['method'];args=[regs.get(r) for r in x['regs']];ik=Model.key(im);pending=None
            events.append({'pc':x['pc'],'invoke':ik,'args':args})
            if im['class']==INTENT and im['name']=='<init>' and args:
                obj=args[0]
                if isinstance(obj,dict):
                    obj=dict(obj);obj['kind']='intent';obj.setdefault('action',None);obj.setdefault('package',None);obj.setdefault('component',None);obj.setdefault('flags',None);regs[x['regs'][0]]=obj
                    if len(args)>=2 and isinstance(args[1],dict) and args[1].get('kind')=='string':obj['action']=args[1]['value']
            elif im['class']==COMPONENT and im['name']=='<init>' and args:
                if len(args)>=3 and all(isinstance(a,dict) and a.get('kind')=='string' for a in args[1:3]):
                    regs[x['regs'][0]]={'kind':'component','package':args[1]['value'],'class':args[2]['value'],'type':COMPONENT}
            elif im['class']==INTENT and im['name'] in ('setAction','setPackage','setComponent','setClassName','setClass') and args:
                obj=args[0]
                if isinstance(obj,dict):
                    obj=dict(obj);obj['kind']='intent'
                    if im['name']=='setAction' and len(args)>1 and isinstance(args[1],dict):obj['action']=args[1].get('value')
                    elif im['name']=='setPackage' and len(args)>1 and isinstance(args[1],dict):obj['package']=args[1].get('value')
                    elif im['name']=='setComponent' and len(args)>1 and isinstance(args[1],dict):obj['component']=args[1]
                    elif im['name']=='setClassName' and len(args)>2 and all(isinstance(a,dict) for a in args[1:3]):obj['component']={'kind':'component','package':args[1].get('value'),'class':args[2].get('value'),'type':COMPONENT}
                    elif im['name']=='setClass' and len(args)>2 and isinstance(args[2],dict):obj['component']={'kind':'component','package':None,'class':desc_to_dot(args[2].get('value')),'type':COMPONENT}
                    regs[x['regs'][0]]=obj;pending=obj
            elif ik in summaries:pending=summaries[ik]
            elif im['ret']!='V':pending={'kind':'invoke_result','type':im['ret'],'source':ik}
        elif k=='moveresultobj':
            if pending is not None:regs[x['dst']]=pending
            pending=None
        elif k=='returnobj':ret=regs.get(x['src'])
    return {'events':events,'return':ret,'regs':regs}

def intent_summaries(model):
    sums={}
    for _ in range(5):
        changed=False
        for m in model.methods:
            if m['ret']!=INTENT or not m.get('code_off'):continue
            r=simulate(model,m,sums)['return'];k=Model.key(m)
            if isinstance(r,dict) and r.get('kind')=='intent' and sums.get(k)!=r:sums[k]=r;changed=True
        if not changed:break
    return sums

def bind_sites(model):
    sums=intent_summaries(model);out=[]
    for m in model.methods:
        if not m.get('code_off'):continue
        sim=simulate(model,m,sums)
        for e in sim['events']:
            ik=e['invoke']; im=model.by_key.get(ik)
            if not im or im['name']!='bindService' or not im['class'].startswith('Landroid/content/') :continue
            args=e['args'];intent=None;conn=None;flags=None
            for a in args:
                if isinstance(a,dict) and a.get('kind')=='intent':intent=a
            # Expected argument layout is receiver, Intent, ServiceConnection, flags; retain a bounded fallback.
            if len(args)>=3:conn=args[-2] if isinstance(args[-2],dict) else None
            if len(args)>=1 and isinstance(args[-1],dict) and args[-1].get('kind')=='int':flags=args[-1]['value']
            out.append({'caller':Model.key(m),'invoke':ik,'intent':intent,'service_connection_value':conn,'flags':flags,'pc':e['pc']})
    return out

def service_connection_classes(model):
    out=[]
    for d,c in model.classes.items():
        if SERVICE_CONNECTION not in c.get('interfaces',[]):continue
        on=[]
        for m in model.methods_of(d,'onServiceConnected'):
            refs=[];asif=[]
            for x in model.method_ins.get(Model.key(m),[]):
                if x.get('kind')=='invoke':
                    k=Model.key(x['method']);refs.append(k)
                    if x['method']['name']=='asInterface' and x['method']['class'].endswith('$Stub;'):asif.append(k)
            on.append({'method':Model.key(m),'as_interface_calls':asif,'invokes':refs})
        out.append({'class':d,'on_service_connected':on})
    return out

def shortest_path(model,target,root_prefix=CUSTOM_PREFIX,max_depth=10):
    q=deque([(target,[target])]);seen={target}
    while q:
        cur,path=q.popleft()
        if len(path)>1 and cur.startswith(root_prefix):return list(reversed(path))
        if len(path)>max_depth:continue
        for p in sorted(model.reverse.get(cur,())):
            if p not in seen:seen.add(p);q.append((p,path+[p]))
    return []

def interface_from_stub(stub):
    if stub.endswith('$Stub;'):return stub[:-6]+';'
    return None

def descriptor_candidates_from_sc(sc):
    out=[]
    for c in sc:
        for o in c['on_service_connected']:
            for k in o['as_interface_calls']:
                cls=k.split('->',1)[0];iface=interface_from_stub(cls)
                if iface:out.append({'service_connection_class':c['class'],'stub_class':cls,'interface':iface,'descriptor':desc_to_dot(iface),'call':k})
    return out

def service_binder_lineage(hi:Model):
    svc=hi.classes.get(SERVICE);out={'service_class_found':bool(svc),'on_bind_methods':[],'stub_subclasses':[],'interface_candidates':[]}
    if not svc:return out
    stub_classes=[]
    for d,c in hi.classes.items():
        sup=c.get('super') or ''
        if sup.endswith('$Stub;') and ('externalapp/' in sup or 'rokid/' in sup):
            iface=interface_from_stub(sup);stub_classes.append({'class':d,'super':sup,'interface':iface,'descriptor':desc_to_dot(iface)})
    out['stub_subclasses']=stub_classes
    for m in hi.methods_of(SERVICE,'onBind'):
        sim=simulate(hi,m,{})
        refs=[e['invoke'] for e in sim['events']]
        ret=sim['return'];related=[]
        if isinstance(ret,dict):
            t=ret.get('type')
            if t:related=[x for x in stub_classes if x['class']==t or x['super']==t]
        for x in stub_classes:
            if any(x['class'] in r or x['super'] in r for r in refs) and x not in related:related.append(x)
        out['on_bind_methods'].append({'method':Model.key(m),'return_value':ret,'invokes':refs,'stub_lineage':related})
    desc=sorted({x['descriptor'] for x in stub_classes if x.get('descriptor')})
    out['interface_candidates']=desc
    return out

def interface_methods(model,iface_desc):
    out=[]
    for m in model.methods_of(iface_desc):
        if m['name'] in ('<init>','<clinit>'):continue
        out.append({'name':m['name'],'proto':m['proto'],'signature':m['name']+m['proto'],'access':m.get('access',0)})
    return sorted(out,key=lambda x:x['signature'])

def aar_find(explicit,repo):
    cand=[]
    if explicit:cand.append(Path(explicit).expanduser())
    home=Path.home()
    cand += list((home/'.gradle/caches/modules-2/files-2.1/com.rokid.cxr/client-l/1.0.1').glob('**/*.aar')) if (home/'.gradle/caches/modules-2/files-2.1/com.rokid.cxr/client-l/1.0.1').exists() else []
    cand += list(Path(repo).glob('**/*.aar'))
    for p in cand:
        try:
            if p.is_file() and sha256(p)==EXPECTED_AAR_SHA:return p
        except:pass
    return None

def apk_pick(apkdir,prefix):
    xs=sorted(apkdir.glob(prefix+'-*.apk'))
    if not xs:xs=sorted(apkdir.glob(prefix+'*.apk'))
    return xs[0] if xs else None

def clean_intent(i):
    if not isinstance(i,dict):return None
    c=i.get('component');comp=None
    if isinstance(c,dict):comp={'package':c.get('package'),'class':c.get('class')}
    return {'action':i.get('action'),'package':i.get('package'),'component':comp}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--repo',required=True);ap.add_argument('--r3341-evidence',required=True);ap.add_argument('--output',required=True);ap.add_argument('--cxrl-aar');x=ap.parse_args()
    ev=Path(x.r3341_evidence).resolve();out=Path(x.output).resolve();out.mkdir(parents=True,exist_ok=True);(out/'sanitized').mkdir(exist_ok=True)
    apkdir=ev/'raw/apks';custom=apk_pick(apkdir,'custom');hi=apk_pick(apkdir,'hi')
    if not custom or not hi:raise SystemExit('ERROR: r3.3.4.1 private APK inputs unavailable')
    custom_sha=sha256(custom);hi_sha=sha256(hi);aar=aar_find(x.cxrl_aar,x.repo)
    cm=Model();cm.add_apk(custom);hm=Model();hm.add_apk(hi)
    binds=bind_sites(cm);sc=service_connection_classes(cm);sc_desc=descriptor_candidates_from_sc(sc);lineage=service_binder_lineage(hm)
    # Rank sites that carry exact known action/package or are reachable from custom app code.
    for b in binds:
        b['call_path_from_custom_app']=shortest_path(cm,b['caller'])
        b['intent']=clean_intent(b.get('intent'))
        v=b.get('service_connection_value')
        b['service_connection_value']=None if not isinstance(v,dict) else {'kind':v.get('kind'),'type':v.get('type'),'name':v.get('name'),'owner':v.get('owner')}
        i=b.get('intent') or {};score=0
        if i.get('action')==KNOWN_ACTION:score+=6
        if i.get('package')==HI_PACKAGE:score+=5
        c=i.get('component') or {}
        if c.get('package')==HI_PACKAGE:score+=5
        if c.get('class')==SERVICE_DOT:score+=6
        if b['call_path_from_custom_app']:score+=4
        if b['caller'].startswith(CXR_PREFIX):score+=2
        b['score']=score
    binds=sorted(binds,key=lambda z:(-z['score'],z['caller']))
    primary=binds[0] if binds else None
    # Exact descriptor requires the client ServiceConnection asInterface lineage; service-side lineage corroborates.
    exact_desc=None;desc_proof='UNRESOLVED'
    sc_unique=sorted({d['descriptor'] for d in sc_desc})
    service_desc=set(lineage.get('interface_candidates',[]))
    common=sorted(set(sc_unique)&service_desc)
    if len(common)==1:exact_desc=common[0];desc_proof='CLIENT_ASINTERFACE_AND_SERVICE_STUB_LINEAGE_EXACT'
    elif len(sc_unique)==1:exact_desc=sc_unique[0];desc_proof='CLIENT_SERVICECONNECTION_ASINTERFACE_EXACT_SERVICE_SIDE_NOT_CORROBORATED'
    binder_methods=[]
    if exact_desc:
        iface='L'+exact_desc.replace('.','/')+';';binder_methods=interface_methods(hm,iface) or interface_methods(cm,iface)
    intent=(primary or {}).get('intent') or {}
    intent_action=intent.get('action');intent_pkg=intent.get('package');comp=intent.get('component') or {};flags=(primary or {}).get('flags')
    exact_intent=bool(intent_action or intent_pkg or comp.get('class'))
    exact_bind=bool(primary)
    exact_sc=bool(sc_desc)
    exact_path=bool(primary and primary.get('call_path_from_custom_app'))
    closure=bool(exact_bind and exact_intent and exact_sc and exact_desc)
    if closure:disp='EXACT_STATIC_CXRL_TO_CXRLINKSERVICE_BINDER_CONTRACT_CLOSED'
    elif exact_bind and exact_sc:disp='BIND_CALL_AND_SERVICECONNECTION_PROVEN_CONTRACT_PARTIAL'
    else:disp='STATIC_CALL_PATH_UNRESOLVED'
    result={
      'schema':'rokid.test21-r3-3-4-2.static-contract.v1','analysis':'PASS',
      'inputs':{'custom_apk_sha256':custom_sha,'hi_rokid_apk_sha256':hi_sha,'cxrl_aar_expected_sha256':EXPECTED_AAR_SHA,'cxrl_aar_found':bool(aar),'cxrl_aar_sha256':sha256(aar) if aar else None},
      'bind_sites':binds,'primary_bind_site':primary,'service_connection_classes':sc,'service_connection_descriptor_candidates':sc_desc,'service_binder_lineage':lineage,
      'intent_contract':{'action':intent_action,'package':intent_pkg,'component_package':comp.get('package'),'component_class':comp.get('class'),'flags':flags,'exact_fields_recovered':exact_intent},
      'binder_contract':{'descriptor':exact_desc,'descriptor_disposition':desc_proof,'methods':binder_methods,'method_count':len(binder_methods)},
      'call_path_from_custom_app':(primary or {}).get('call_path_from_custom_app',[]),
      'closure':{'bind_service_callsite_proven':exact_bind,'custom_to_bind_call_path_proven':exact_path,'service_connection_asinterface_proven':exact_sc,'binder_descriptor_exact':bool(exact_desc),'static_dependency_closure_exact':closure,'disposition':disp},
      'proof_boundary':'STATIC_MERGED_CUSTOM_APK_AND_HI_ROKID_DEX_BYTECODE_NO_RUNTIME_OR_LIBRARY_INTERNAL_NATIVE_CALLSTACK',
      'device_operation':'NONE'
    }
    priv=out/'static-contract-private.json';priv.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    # Sanitized result excludes file paths and bytecode; symbols/contract metadata only.
    san=dict(result);san['inputs']=dict(result['inputs']);
    (out/'sanitized/test21-r3-3-4-2-summary.json').write_text(json.dumps(san,indent=2,sort_keys=True)+'\n')
    lines=[
      'TEST21_R3_3_4_2_ANALYSIS=PASS',
      'CXR_L_AAR_EXPECTED_SHA256='+EXPECTED_AAR_SHA,
      'CXR_L_AAR_IDENTITY=' + ('PASS' if aar else 'NOT_LOCALLY_FOUND_MERGED_APK_ANALYSIS_USED'),
      'BIND_SERVICE_CALLSITE_PROVEN='+('YES' if exact_bind else 'NO'),
      'CUSTOM_TO_BIND_CALL_PATH_PROVEN='+('YES' if exact_path else 'NO'),
      'PRIMARY_BIND_CALLER='+((primary or {}).get('caller') or 'UNRESOLVED'),
      'INTENT_ACTION='+(intent_action or 'UNRESOLVED'),
      'INTENT_PACKAGE='+(intent_pkg or 'UNRESOLVED'),
      'INTENT_COMPONENT_PACKAGE='+(comp.get('package') or 'UNRESOLVED'),
      'INTENT_COMPONENT_CLASS='+(comp.get('class') or 'UNRESOLVED'),
      'BIND_FLAGS='+(str(flags) if flags is not None else 'UNRESOLVED'),
      'SERVICECONNECTION_ASINTERFACE_PROVEN='+('YES' if exact_sc else 'NO'),
      'BINDER_INTERFACE_DESCRIPTOR='+(exact_desc or 'UNRESOLVED'),
      'BINDER_INTERFACE_DISPOSITION='+desc_proof,
      'BINDER_INTERFACE_METHOD_COUNT='+str(len(binder_methods)),
      'STATIC_DEPENDENCY_CLOSURE_EXACT='+('YES' if closure else 'NO'),
      'DEPENDENCY_DISPOSITION='+disp,
      'DEVICE_OPERATION=NONE','ADB_OPERATION=NONE','NEW_CAPTURE=NONE','PHOTO_OPERATION=NONE','AUDIO_OPERATION=NONE']
    (out/'sanitized/test21-r3-3-4-2-summary.txt').write_text('\n'.join(lines)+'\n')
    print('\n'.join(lines));return 0
if __name__=='__main__':raise SystemExit(main())
