#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import struct
import zipfile
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

SCHEMA = 'rokid.test21-r3-3-4-2-6-1.aar-binder-contract.v1'
EXPECTED_AAR_SHA256 = 'c23d34b3adc60d3fa16001645ce6172eaf4554173e7ef9c078595e672d50824e'
EXPECTED_COORDINATE = 'com.rokid.cxr:client-l:1.0.1'
IFACE = 'com/rokid/sprite/aiapp/externalapp/IMediaStreamService'
IFACE_DOT = IFACE.replace('/', '.')
STUB = IFACE + '$Stub'
PROXY = STUB + '$Proxy'
DESCRIPTOR = IFACE_DOT
ACC_PUBLIC = 0x0001
ACC_STATIC = 0x0008
ACC_ABSTRACT = 0x0400

EXPECTED_METHODS = {
    'closeCustomView()Z',
    'getCurrentCustomViewData()Ljava/lang/String;',
    'getCurrentIcons()Ljava/lang/String;',
    'getServiceVersion()Ljava/lang/String;',
    'getServiceVersionCode()I',
    'isAudioStreaming()Z',
    'isCustomViewOpened()Z',
    'isDeviceConnected()Z',
    'openApp(Ljava/lang/String;Ljava/lang/String;Lcom/rokid/sprite/aiapp/externalapp/IGlassAppCallback;)V',
    'openCustomView(Ljava/lang/String;)Z',
    'queryGlassAppInstalled(Ljava/lang/String;Lcom/rokid/sprite/aiapp/externalapp/IGlassAppCallback;)V',
    'registAiEventCallback(Lcom/rokid/sprite/aiapp/externalapp/IAiEventCallback;)Z',
    'registerAudioCallback(Lcom/rokid/sprite/aiapp/externalapp/IAudioStreamCallback;)Z',
    'registerCustomCmdCallback(Lcom/rokid/sprite/aiapp/externalapp/ICustomCmdCallback;)Z',
    'registerCustomViewCallback(Lcom/rokid/sprite/aiapp/externalapp/ICustomViewCallback;)Z',
    'registerDeviceStatusCallback(Lcom/rokid/sprite/aiapp/externalapp/IDeviceStatusCallback;)Z',
    'registerImageCallback(Lcom/rokid/sprite/aiapp/externalapp/IImageStreamCallback;)Z',
    'sendCustomCmd(Ljava/lang/String;[B)I',
    'sendExit(Z)Z',
    'setIcons(Ljava/lang/String;)Z',
    'startAudioStream(I)Z',
    'stopApp(Ljava/lang/String;Lcom/rokid/sprite/aiapp/externalapp/IGlassAppCallback;)V',
    'stopAudioStream()Z',
    'takePhoto(III)Z',
    'uninstallApp(Ljava/lang/String;Lcom/rokid/sprite/aiapp/externalapp/IGlassAppCallback;)V',
    'unregistAiEventCallback(Lcom/rokid/sprite/aiapp/externalapp/IAiEventCallback;)Z',
    'unregisterAudioCallback(Lcom/rokid/sprite/aiapp/externalapp/IAudioStreamCallback;)Z',
    'unregisterCustomCmdCallback(Lcom/rokid/sprite/aiapp/externalapp/ICustomCmdCallback;)Z',
    'unregisterCustomViewCallback(Lcom/rokid/sprite/aiapp/externalapp/ICustomViewCallback;)Z',
    'unregisterDeviceStatusCallback(Lcom/rokid/sprite/aiapp/externalapp/IDeviceStatusCallback;)Z',
    'unregisterImageCallback(Lcom/rokid/sprite/aiapp/externalapp/IImageStreamCallback;)Z',
    'updateCustomView(Ljava/lang/String;)Z',
    'uploadAndInstallApk(Ljava/lang/String;Landroid/os/ParcelFileDescriptor;Lcom/rokid/sprite/aiapp/externalapp/IGlassAppCallback;)V',
}
EXPECTED_METHOD_COUNT = 33


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


class Reader:
    def __init__(self, data: bytes):
        self.data = data
        self.p = 0
    def u1(self) -> int:
        v = self.data[self.p]
        self.p += 1
        return v
    def u2(self) -> int:
        v = struct.unpack_from('>H', self.data, self.p)[0]
        self.p += 2
        return v
    def u4(self) -> int:
        v = struct.unpack_from('>I', self.data, self.p)[0]
        self.p += 4
        return v
    def take(self, n: int) -> bytes:
        b = self.data[self.p:self.p+n]
        if len(b) != n:
            raise ValueError('truncated class file')
        self.p += n
        return b


@dataclass
class FieldInfo:
    access: int
    name: str
    desc: str
    const: Any = None


@dataclass
class MethodInfo:
    owner: str
    access: int
    name: str
    desc: str
    code: bytes | None

    @property
    def key(self) -> str:
        return f'{self.owner}->{self.name}{self.desc}'


class ClassFile:
    def __init__(self, data: bytes):
        r = Reader(data)
        if r.u4() != 0xCAFEBABE:
            raise ValueError('bad class magic')
        self.minor = r.u2(); self.major = r.u2()
        cp_count = r.u2()
        self.cp: list[Any] = [None] * cp_count
        i = 1
        while i < cp_count:
            tag = r.u1()
            if tag == 1:
                n = r.u2(); self.cp[i] = ('Utf8', r.take(n).decode('utf-8', 'replace'))
            elif tag == 3:
                self.cp[i] = ('Integer', struct.unpack('>i', r.take(4))[0])
            elif tag == 4:
                self.cp[i] = ('Float', struct.unpack('>f', r.take(4))[0])
            elif tag == 5:
                self.cp[i] = ('Long', struct.unpack('>q', r.take(8))[0]); i += 1
            elif tag == 6:
                self.cp[i] = ('Double', struct.unpack('>d', r.take(8))[0]); i += 1
            elif tag in (7, 8, 16, 19, 20):
                self.cp[i] = (tag, r.u2())
            elif tag in (9, 10, 11, 12, 17, 18):
                self.cp[i] = (tag, r.u2(), r.u2())
            elif tag == 15:
                self.cp[i] = (tag, r.u1(), r.u2())
            else:
                raise ValueError(f'unsupported constant-pool tag {tag}')
            i += 1
        self.access = r.u2()
        self.this_class = r.u2(); self.super_class = r.u2()
        self.name = self.class_name(self.this_class)
        interfaces_count = r.u2(); self.interfaces = [self.class_name(r.u2()) for _ in range(interfaces_count)]
        self.fields: list[FieldInfo] = []
        for _ in range(r.u2()):
            access = r.u2(); name = self.utf8(r.u2()); desc = self.utf8(r.u2())
            const = None
            for _a in range(r.u2()):
                aname = self.utf8(r.u2()); alen = r.u4(); payload = r.take(alen)
                if aname == 'ConstantValue' and len(payload) == 2:
                    const = self.const_value(struct.unpack('>H', payload)[0])
            self.fields.append(FieldInfo(access, name, desc, const))
        self.methods: list[MethodInfo] = []
        for _ in range(r.u2()):
            access = r.u2(); name = self.utf8(r.u2()); desc = self.utf8(r.u2())
            code = None
            for _a in range(r.u2()):
                aname = self.utf8(r.u2()); alen = r.u4(); payload = r.take(alen)
                if aname == 'Code':
                    cr = Reader(payload)
                    cr.u2(); cr.u2(); clen = cr.u4(); code = cr.take(clen)
            self.methods.append(MethodInfo(self.name, access, name, desc, code))
        for _ in range(r.u2()):
            r.u2(); r.take(r.u4())

    def utf8(self, idx: int) -> str:
        item = self.cp[idx]
        if item is None or item[0] != 'Utf8':
            raise ValueError('expected Utf8')
        return item[1]

    def class_name(self, idx: int) -> str:
        item = self.cp[idx]
        if item is None or item[0] != 7:
            raise ValueError('expected Class')
        return self.utf8(item[1])

    def const_value(self, idx: int) -> Any:
        item = self.cp[idx]
        if item is None:
            return None
        if item[0] in ('Integer', 'Float', 'Long', 'Double'):
            return item[1]
        if item[0] == 8:
            return self.utf8(item[1])
        return None

    def member_ref(self, idx: int) -> tuple[str, str, str, str] | None:
        item = self.cp[idx]
        if item is None or item[0] not in (9, 10, 11):
            return None
        owner = self.class_name(item[1])
        nat = self.cp[item[2]]
        if nat is None or nat[0] != 12:
            return None
        return owner, self.utf8(nat[1]), self.utf8(nat[2]), {9:'field',10:'method',11:'interface'}[item[0]]


# Fixed instruction operand sizes excluding tableswitch/lookupswitch/wide.
OPLEN = {i:0 for i in range(256)}
for op in (0x10,0x12,0x15,0x16,0x17,0x18,0x19,0x36,0x37,0x38,0x39,0x3a,0xa9,0xbc): OPLEN[op]=1
for op in (0x11,0x13,0x14,0x84,0x99,0x9a,0x9b,0x9c,0x9d,0x9e,0x9f,0xa0,0xa1,0xa2,0xa3,0xa4,0xa5,0xa6,0xa7,0xa8,0xc6,0xc7,
           0xb2,0xb3,0xb4,0xb5,0xb6,0xb7,0xb8,0xbb,0xbd,0xc0,0xc1): OPLEN[op]=2
OPLEN[0xb9]=4; OPLEN[0xba]=4; OPLEN[0xc5]=3; OPLEN[0xc8]=4; OPLEN[0xc9]=4


@dataclass
class Insn:
    off: int
    op: int
    raw: bytes
    cp_index: int | None = None
    int_value: int | None = None
    switch_pairs: list[tuple[int,int]] | None = None


def decode(code: bytes, cf: ClassFile) -> list[Insn]:
    out: list[Insn] = []
    p = 0
    while p < len(code):
        off = p; op = code[p]; p += 1
        if op == 0xaa:  # tableswitch
            while p % 4: p += 1
            default = struct.unpack_from('>i', code, p)[0]; p += 4
            low = struct.unpack_from('>i', code, p)[0]; p += 4
            high = struct.unpack_from('>i', code, p)[0]; p += 4
            pairs=[]
            for key in range(low, high+1):
                rel=struct.unpack_from('>i', code, p)[0]; p += 4
                pairs.append((key, off+rel))
            out.append(Insn(off,op,b'',switch_pairs=pairs)); continue
        if op == 0xab:  # lookupswitch
            while p % 4: p += 1
            default = struct.unpack_from('>i', code, p)[0]; p += 4
            n = struct.unpack_from('>i', code, p)[0]; p += 4
            pairs=[]
            for _ in range(n):
                key=struct.unpack_from('>i', code, p)[0]; p+=4
                rel=struct.unpack_from('>i', code, p)[0]; p+=4
                pairs.append((key,off+rel))
            out.append(Insn(off,op,b'',switch_pairs=pairs)); continue
        if op == 0xc4:  # wide
            sub = code[p]; p += 1
            n = 4 if sub == 0x84 else 2
            raw = bytes([sub]) + code[p:p+n]; p += n
            out.append(Insn(off,op,raw)); continue
        n = OPLEN.get(op, 0)
        raw = code[p:p+n]; p += n
        cp_index=None; int_value=None
        if op == 0x02: int_value=-1
        elif 0x03 <= op <= 0x08: int_value=op-0x03
        elif op == 0x10: int_value=struct.unpack('>b',raw)[0]
        elif op == 0x11: int_value=struct.unpack('>h',raw)[0]
        elif op in (0x12,0x13):
            cp_index = raw[0] if op==0x12 else struct.unpack('>H',raw)[0]
            v=cf.const_value(cp_index)
            if isinstance(v,int): int_value=v
        if op in (0xb2,0xb3,0xb4,0xb5,0xb6,0xb7,0xb8,0xb9,0xba,0xbb,0xbd,0xc0,0xc1,0xc5):
            cp_index = struct.unpack('>H', raw[:2])[0]
        out.append(Insn(off,op,raw,cp_index,int_value))
    return out


def load_aar(aar: Path) -> tuple[dict[str,ClassFile], str]:
    with zipfile.ZipFile(aar,'r') as z:
        if 'classes.jar' not in z.namelist():
            raise ValueError('AAR has no classes.jar')
        jar_bytes=z.read('classes.jar')
    classes={}
    with zipfile.ZipFile(io.BytesIO(jar_bytes),'r') as j:
        for name in j.namelist():
            if not name.endswith('.class'):
                continue
            cf=ClassFile(j.read(name))
            classes[cf.name]=cf
    return classes, hashlib.sha256(jar_bytes).hexdigest()


def resolve_aar(explicit: str | None, home: Path) -> list[Path]:
    if explicit:
        return [Path(explicit).expanduser().resolve()]
    candidates=[]
    roots=[
        home/'.gradle/caches/modules-2/files-2.1/com.rokid.cxr/client-l/1.0.1',
        home/'.m2/repository/com/rokid/cxr/client-l/1.0.1',
    ]
    for root in roots:
        if root.exists():
            candidates.extend(root.rglob('*.aar'))
    return sorted({p.resolve() for p in candidates})


def interface_methods(classes: dict[str,ClassFile]) -> list[dict[str,Any]]:
    cf=classes.get(IFACE)
    if not cf: return []
    out=[]
    for m in cf.methods:
        if m.name.startswith('<') or m.name == 'asBinder':
            continue
        out.append({'name':m.name,'proto':m.desc,'signature':m.name+m.desc,'access':m.access})
    return sorted(out,key=lambda x:(x['name'],x['proto']))


def transaction_constants(classes: dict[str,ClassFile]) -> dict[str,int]:
    cf=classes.get(STUB)
    out={}
    if not cf: return out
    for f in cf.fields:
        if f.name.startswith('TRANSACTION_') and f.desc=='I' and isinstance(f.const,int):
            out[f.name[len('TRANSACTION_'):]]=f.const
    return out


def descriptor_evidence(classes: dict[str,ClassFile]) -> list[str]:
    hits=[]
    for cname in (IFACE,STUB,PROXY):
        cf=classes.get(cname)
        if not cf: continue
        for f in cf.fields:
            if f.name=='DESCRIPTOR' and isinstance(f.const,str): hits.append(f.const)
        for item in cf.cp:
            if item and item[0]=='Utf8' and item[1]==DESCRIPTOR: hits.append(item[1])
            elif item and item[0]==8:
                try:
                    if cf.utf8(item[1])==DESCRIPTOR: hits.append(DESCRIPTOR)
                except Exception: pass
    return sorted(set(hits))


def invoke_refs(cf: ClassFile, method: MethodInfo) -> list[dict[str,Any]]:
    if not method.code: return []
    out=[]
    for ins in decode(method.code,cf):
        if ins.op not in (0xb6,0xb7,0xb8,0xb9): continue
        if ins.cp_index is None: continue
        ref=cf.member_ref(ins.cp_index)
        if ref:
            owner,name,desc,kind=ref
            out.append({'off':ins.off,'owner':owner,'name':name,'desc':desc,'kind':kind})
    return out


def proxy_map(classes: dict[str,ClassFile], methods: list[dict[str,Any]]) -> tuple[dict[str,list[int]], dict[str,list[str]], dict[str,bool]]:
    cf=classes.get(PROXY)
    code_map={}; parcel_map={}; found={}
    if not cf:
        return code_map,parcel_map,found
    by_sig={(m.name,m.desc):m for m in cf.methods}
    for item in methods:
        key=item['signature']; m=by_sig.get((item['name'],item['proto']))
        found[key]=bool(m)
        if not m or not m.code:
            code_map[key]=[]; parcel_map[key]=[]; continue
        insns=decode(m.code,cf)
        codes=[]; parcel=[]
        for idx,ins in enumerate(insns):
            if ins.op in (0xb6,0xb7,0xb8,0xb9) and ins.cp_index is not None:
                ref=cf.member_ref(ins.cp_index)
                if not ref: continue
                owner,name,desc,kind=ref
                if owner=='android/os/Parcel':
                    parcel.append(name+desc)
                if owner=='android/os/IBinder' and name=='transact':
                    start=max(0,idx-16)
                    # Prefer first integer after mRemote field access in the local window.
                    field_pos=None
                    for j in range(idx-1,start-1,-1):
                        x=insns[j]
                        if x.op in (0xb2,0xb3,0xb4,0xb5) and x.cp_index is not None:
                            rr=cf.member_ref(x.cp_index)
                            if rr and rr[1]=='mRemote': field_pos=j; break
                    vals=[]
                    lo=(field_pos+1) if field_pos is not None else start
                    for x in insns[lo:idx]:
                        if x.int_value is not None: vals.append(x.int_value)
                    if vals:
                        # Standard AIDL has [transactionCode, flags]; choose the first.
                        codes.append(vals[0])
        code_map[key]=sorted(set(codes)); parcel_map[key]=parcel
    return code_map,parcel_map,found


def ontransact_map(classes: dict[str,ClassFile], methods: list[dict[str,Any]]) -> dict[str,list[int]]:
    cf=classes.get(STUB)
    out=defaultdict(list)
    if not cf: return {}
    candidates=[m for m in cf.methods if m.name=='onTransact' and m.code]
    valid={(x['name'],x['proto']):x['signature'] for x in methods}
    for m in candidates:
        insns=decode(m.code or b'',cf)
        off_to_index={x.off:i for i,x in enumerate(insns)}
        switches=[x for x in insns if x.switch_pairs]
        for sw in switches:
            targets=sorted({target for _,target in sw.switch_pairs or []})
            for code,target in sw.switch_pairs or []:
                if code <= 0 or code > 65535: continue
                idx=off_to_index.get(target)
                if idx is None: continue
                next_targets=[t for t in targets if t>target]
                end=next_targets[0] if next_targets else len(m.code or b'')
                for x in insns[idx:]:
                    if x.off>=end: break
                    if x.op not in (0xb6,0xb7,0xb8,0xb9) or x.cp_index is None: continue
                    ref=cf.member_ref(x.cp_index)
                    if not ref: continue
                    owner,name,desc,kind=ref
                    sig=valid.get((name,desc))
                    if sig:
                        out[sig].append(code); break
    return {k:sorted(set(v)) for k,v in out.items()}


def build_call_graph(classes: dict[str,ClassFile]) -> tuple[dict[str,set[str]],dict[str,MethodInfo]]:
    edges=defaultdict(set); info={}
    for cf in classes.values():
        for m in cf.methods:
            info[m.key]=m
            for ref in invoke_refs(cf,m):
                target=f"{ref['owner']}->{ref['name']}{ref['desc']}"
                edges[m.key].add(target)
    return edges,info


def wrapper_bridges(classes: dict[str,ClassFile], methods: list[dict[str,Any]]) -> list[dict[str,Any]]:
    valid={(x['name'],x['proto']):x['signature'] for x in methods}
    bridges=[]
    for cf in classes.values():
        if cf.name in (IFACE,STUB,PROXY) or cf.name.startswith(STUB+'$'):
            continue
        for m in cf.methods:
            for ref in invoke_refs(cf,m):
                if ref['owner']!=IFACE: continue
                sig=valid.get((ref['name'],ref['desc']))
                if not sig: continue
                bridges.append({
                    'caller_class':cf.name.replace('/','.'),
                    'caller_method':m.name,
                    'caller_proto':m.desc,
                    'caller_public':bool(m.access & ACC_PUBLIC),
                    'caller_sdk_namespace':cf.name.startswith('com/rokid/cxr/'),
                    'binder_signature':sig,
                })
    unique={(b['caller_class'],b['caller_method'],b['caller_proto'],b['binder_signature']):b for b in bridges}
    return sorted(unique.values(),key=lambda b:(b['binder_signature'],b['caller_class'],b['caller_method']))


def nearest_public_sdk_roots(classes: dict[str,ClassFile], methods: list[dict[str,Any]], bridges: list[dict[str,Any]], max_depth:int=8) -> dict[str,list[str]]:
    edges,info=build_call_graph(classes)
    reverse=defaultdict(set)
    for src,targets in edges.items():
        for t in targets: reverse[t].add(src)
    direct_by_sig=defaultdict(list)
    for b in bridges:
        node=f"{b['caller_class'].replace('.','/')}->{b['caller_method']}{b['caller_proto']}"
        direct_by_sig[b['binder_signature']].append(node)
    roots={}
    for item in methods:
        sig=item['signature']; q=deque((n,[n]) for n in direct_by_sig.get(sig,[])); seen={n for n,_ in q}; best=[]
        while q:
            node,path=q.popleft(); mi=info.get(node)
            if mi and mi.owner.startswith('com/rokid/cxr/') and (mi.access & ACC_PUBLIC):
                best=list(reversed(path)); break
            if len(path)>=max_depth: continue
            for parent in sorted(reverse.get(node,())):
                if parent not in seen:
                    seen.add(parent); q.append((parent,path+[parent]))
        roots[sig]=best
    return roots


def merge_contract(methods, constants, proxy_codes, on_codes, parcel_ops, proxy_found, bridges, roots):
    rows=[]; mismatches=[]; source_agreement=0; canonical_codes=[]; parcel_recovered=0
    const_by_sig={}
    for m in methods:
        if m['name'] in constants: const_by_sig[m['signature']]=constants[m['name']]
    bridge_targets={b['binder_signature'] for b in bridges}
    for m in methods:
        sig=m['signature']; src={}
        if sig in const_by_sig: src['constant']=[const_by_sig[sig]]
        if proxy_codes.get(sig): src['proxy']=proxy_codes[sig]
        if on_codes.get(sig): src['onTransact']=on_codes[sig]
        flat={v for vals in src.values() for v in vals}
        mismatch=len(flat)>1 or any(len(vals)!=1 for vals in src.values())
        if mismatch:
            mismatches.append({'signature':sig,'sources':src})
        independent=len(src)
        if independent>=2 and not mismatch: source_agreement+=1
        code=next(iter(flat)) if len(flat)==1 else None
        if code is not None: canonical_codes.append(code)
        ops=parcel_ops.get(sig,[])
        parcel_ok=bool(proxy_found.get(sig)) and bool(proxy_codes.get(sig)) and any(x.startswith('writeInterfaceToken') for x in ops) and any(x.startswith('readException') for x in ops)
        if parcel_ok: parcel_recovered+=1
        rows.append({
            'name':m['name'],'proto':m['proto'],'signature':sig,
            'transaction_code':code,
            'constant_code':const_by_sig.get(sig),
            'proxy_codes':proxy_codes.get(sig,[]),
            'ontransact_codes':on_codes.get(sig,[]),
            'independent_source_count':independent,
            'source_agreement':independent>=2 and not mismatch,
            'proxy_method_found':bool(proxy_found.get(sig)),
            'parcel_contract_recovered':parcel_ok,
            'parcel_operations':ops,
            'sdk_direct_bridge':sig in bridge_targets,
            'sdk_public_root_found':bool(roots.get(sig)),
            'sdk_public_root':roots.get(sig,[None])[0] if roots.get(sig) else None,
            'sdk_path_depth':len(roots.get(sig,[])) if roots.get(sig) else 0,
        })
    unique=len(set(canonical_codes))==len(canonical_codes)
    complete=len(rows)==EXPECTED_METHOD_COUNT and all(r['transaction_code'] is not None for r in rows) and unique and not mismatches
    exact_sources=source_agreement==EXPECTED_METHOD_COUNT
    proxy_complete=sum(1 for r in rows if len(r['proxy_codes'])==1)==EXPECTED_METHOD_COUNT
    on_complete=sum(1 for r in rows if len(r['ontransact_codes'])==1)==EXPECTED_METHOD_COUNT
    transaction_ready=complete and exact_sources and (proxy_complete or on_complete)
    return rows,{
        'transaction_map_complete':complete,
        'transaction_unique_code_count':len(set(canonical_codes)),
        'transaction_source_agreement_count':source_agreement,
        'transaction_source_mismatch_count':len(mismatches),
        'transaction_source_mismatches':mismatches,
        'proxy_transaction_method_count':sum(1 for r in rows if len(r['proxy_codes'])==1),
        'ontransact_transaction_method_count':sum(1 for r in rows if len(r['ontransact_codes'])==1),
        'parcel_contract_recovered_method_count':parcel_recovered,
        'transaction_contract_ready':transaction_ready,
    }


def analyze_aar(aar: Path, fixture_mode: bool=False) -> dict[str,Any]:
    digest=sha256_path(aar)
    if not fixture_mode and digest != EXPECTED_AAR_SHA256:
        raise ValueError(f'AAR SHA-256 mismatch expected={EXPECTED_AAR_SHA256} actual={digest}')
    classes,classes_jar_sha=load_aar(aar)
    methods=interface_methods(classes)
    method_set={m['signature'] for m in methods}
    constants=transaction_constants(classes)
    desc_hits=descriptor_evidence(classes)
    proxy_codes,parcel_ops,proxy_found=proxy_map(classes,methods)
    on_codes=ontransact_map(classes,methods)
    bridges=wrapper_bridges(classes,methods)
    roots=nearest_public_sdk_roots(classes,methods,bridges)
    rows,closure=merge_contract(methods,constants,proxy_codes,on_codes,parcel_ops,proxy_found,bridges,roots)
    iface_exact=(method_set==EXPECTED_METHODS)
    stub_present=STUB in classes; proxy_present=PROXY in classes
    descriptor_exact=DESCRIPTOR in desc_hits
    direct_targets={b['binder_signature'] for b in bridges if b['caller_sdk_namespace']}
    root_targets={sig for sig,p in roots.items() if p}
    interface_ready=iface_exact and stub_present and proxy_present and descriptor_exact
    clean_ready=interface_ready and closure['transaction_contract_ready'] and closure['parcel_contract_recovered_method_count']==EXPECTED_METHOD_COUNT
    disposition = (
        'EXACT_INTERFACE_TRANSACTION_AND_PROXY_PARCEL_CONTRACT_CLOSED_NO_VENDOR_BEHAVIOR_CLAIM'
        if clean_ready else
        'AAR_CONTRACT_PARTIAL_CLOSURE_REQUIRES_REVIEW'
    )
    return {
        'schema':SCHEMA,
        'analysis':'PASS',
        'access_mode':'HOST_ONLY_LOCAL_AAR',
        'root_required':False,'magisk_required':False,'adb_required':False,'frida_required':False,'phone_action':'NONE',
        'network_required':False,
        'input':{
            'coordinate':EXPECTED_COORDINATE,
            'aar_sha256':digest,
            'aar_identity':'FIXTURE' if fixture_mode else 'PASS',
            'classes_jar_sha256':classes_jar_sha,
            'fixture_mode':fixture_mode,
        },
        'class_presence':{
            'interface_class_present':IFACE in classes,
            'stub_class_present':stub_present,
            'proxy_class_present':proxy_present,
            'class_count':len(classes),
        },
        'interface':{
            'descriptor':DESCRIPTOR,
            'descriptor_exact':descriptor_exact,
            'method_count':len(methods),
            'expected_method_count':EXPECTED_METHOD_COUNT,
            'signature_set_exact':iface_exact,
            'missing_signatures':sorted(EXPECTED_METHODS-method_set),
            'extra_signatures':sorted(method_set-EXPECTED_METHODS),
        },
        'transactions':{
            'constant_field_count':len(constants),
            **closure,
        },
        'sdk_wrapper_bridge':{
            'direct_bridge_count':len(bridges),
            'direct_reachable_binder_method_count':len(direct_targets),
            'public_root_reachable_binder_method_count':len(root_targets),
        },
        'method_contract':rows,
        'bridges':bridges,
        'clean_room':{
            'interface_scaffold_ready':interface_ready,
            'transaction_contract_ready':closure['transaction_contract_ready'],
            'parcel_contract_ready':closure['parcel_contract_recovered_method_count']==EXPECTED_METHOD_COUNT,
            'clean_room_contract_ready':clean_ready,
            'functional_behavior_compatibility_proven':False,
            'authorization_semantics_recovered':False,
            'session_lifecycle_semantics_recovered':False,
            'service_implementation_recovered':False,
            'replacement_boundary':'BINDER_ABI_AND_MARSHALLING_ONLY_NO_PROPRIETARY_SERVICE_BEHAVIOR',
            'disposition':disposition,
        },
        'device_operation':'NONE','photo_operation':'NONE','audio_operation':'NONE','network_capture':'NONE',
    }


def sanitized(result: dict[str,Any]) -> dict[str,Any]:
    # Remove local paths/call paths. Exact API/ABI facts are retained.
    out=json.loads(json.dumps(result))
    for r in out.get('method_contract',[]):
        r.pop('sdk_public_root',None)
        r.pop('parcel_operations',None)
    out.pop('bridges',None)
    return out


def write_outputs(result: dict[str,Any], output: Path) -> None:
    output.mkdir(parents=True,exist_ok=True)
    san=output/'sanitized'; san.mkdir(exist_ok=True)
    (output/'r334261-private-analysis.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    s=sanitized(result)
    (san/'test21-r3-3-4-2-6-1-summary.json').write_text(json.dumps(s,indent=2,sort_keys=True)+'\n')
    tx=s['transactions']; iface=s['interface']; cr=s['clean_room']; bridge=s['sdk_wrapper_bridge']; cp=s['class_presence']; inp=s['input']
    lines=[
        'TEST21_R3_3_4_2_6_1_ANALYSIS=PASS',
        'ACCESS_MODE=HOST_ONLY_LOCAL_AAR','ROOT_REQUIRED=NO','MAGISK_REQUIRED=NO','ADB_REQUIRED=NO','FRIDA_REQUIRED=NO','PHONE_ACTION=NONE','NETWORK_REQUIRED=NO',
        'AAR_COORDINATE='+inp['coordinate'],'AAR_SHA256='+inp['aar_sha256'],'AAR_IDENTITY='+inp['aar_identity'],
        'INTERFACE_CLASS_PRESENT='+('YES' if cp['interface_class_present'] else 'NO'),
        'STUB_CLASS_PRESENT='+('YES' if cp['stub_class_present'] else 'NO'),
        'PROXY_CLASS_PRESENT='+('YES' if cp['proxy_class_present'] else 'NO'),
        'BINDER_INTERFACE_DESCRIPTOR='+iface['descriptor'],'BINDER_DESCRIPTOR_EXACT='+('YES' if iface['descriptor_exact'] else 'NO'),
        f"BINDER_INTERFACE_METHOD_COUNT={iface['method_count']}",'BINDER_SIGNATURE_SET_EXACT='+('YES' if iface['signature_set_exact'] else 'NO'),
        f"TRANSACTION_CONSTANT_COUNT={tx['constant_field_count']}",f"ONTRANSACT_TRANSACTION_METHOD_COUNT={tx['ontransact_transaction_method_count']}",f"PROXY_TRANSACTION_METHOD_COUNT={tx['proxy_transaction_method_count']}",
        f"TRANSACTION_UNIQUE_CODE_COUNT={tx['transaction_unique_code_count']}",f"TRANSACTION_SOURCE_AGREEMENT_COUNT={tx['transaction_source_agreement_count']}",f"TRANSACTION_SOURCE_MISMATCH_COUNT={tx['transaction_source_mismatch_count']}",
        'TRANSACTION_MAP_COMPLETE='+('YES' if tx['transaction_map_complete'] else 'NO'),
        f"PARCEL_CONTRACT_RECOVERED_METHOD_COUNT={tx['parcel_contract_recovered_method_count']}",
        f"SDK_WRAPPER_BINDER_BRIDGE_COUNT={bridge['direct_bridge_count']}",f"SDK_WRAPPER_REACHABLE_BINDER_METHOD_COUNT={bridge['direct_reachable_binder_method_count']}",f"SDK_PUBLIC_ROOT_REACHABLE_BINDER_METHOD_COUNT={bridge['public_root_reachable_binder_method_count']}",
        'CLEAN_ROOM_INTERFACE_SCAFFOLD_READY='+('YES' if cr['interface_scaffold_ready'] else 'NO'),
        'CLEAN_ROOM_TRANSACTION_CONTRACT_READY='+('YES' if cr['transaction_contract_ready'] else 'NO'),
        'CLEAN_ROOM_PARCEL_CONTRACT_READY='+('YES' if cr['parcel_contract_ready'] else 'NO'),
        'CLEAN_ROOM_CONTRACT_READY='+('YES' if cr['clean_room_contract_ready'] else 'NO'),
        'FUNCTIONAL_BEHAVIOR_COMPATIBILITY_PROVEN=NO','AUTHORIZATION_SEMANTICS_RECOVERED=NO','SESSION_LIFECYCLE_SEMANTICS_RECOVERED=NO','SERVICE_IMPLEMENTATION_RECOVERED=NO',
        'CLEAN_ROOM_DISPOSITION='+cr['disposition'],'DEVICE_OPERATION=NONE','PHOTO_OPERATION=NONE','AUDIO_OPERATION=NONE','NETWORK_CAPTURE=NONE',
    ]
    (san/'test21-r3-3-4-2-6-1-summary.txt').write_text('\n'.join(lines)+'\n')
    md=[
        '# Test 21 r3.3.4.2.6.1 — CXR-L AAR Binder contract', '',
        f"- AAR identity: **{inp['aar_identity']}** (`{inp['aar_sha256']}`)",
        f"- Exact 33-method interface signature set: **{'YES' if iface['signature_set_exact'] else 'NO'}**",
        f"- Stub / Proxy present: **{'YES' if cp['stub_class_present'] and cp['proxy_class_present'] else 'NO'}**",
        f"- Transaction-map complete: **{'YES' if tx['transaction_map_complete'] else 'NO'}**",
        f"- Independent transaction-source agreements: **{tx['transaction_source_agreement_count']} / {EXPECTED_METHOD_COUNT}**",
        f"- Proxy transaction methods recovered: **{tx['proxy_transaction_method_count']} / {EXPECTED_METHOD_COUNT}**",
        f"- onTransact methods recovered: **{tx['ontransact_transaction_method_count']} / {EXPECTED_METHOD_COUNT}**",
        f"- Parcel contracts recovered: **{tx['parcel_contract_recovered_method_count']} / {EXPECTED_METHOD_COUNT}**",
        f"- SDK wrapper → Binder direct bridges: **{bridge['direct_bridge_count']}** across **{bridge['direct_reachable_binder_method_count']}** Binder methods",
        f"- Clean-room Binder ABI/marshalling contract ready: **{'YES' if cr['clean_room_contract_ready'] else 'NO'}**", '',
        'This is host-only interface/transaction/marshalling evidence. It does not claim recovery of Hi Rokid authorization logic, session lifecycle, timing semantics, cloud behavior, or the proprietary service implementation.',
    ]
    (san/'test21-r3-3-4-2-6-1-summary.md').write_text('\n'.join(md)+'\n')
    with (san/'test21-r3-3-4-2-6-1-transaction-map.tsv').open('w') as f:
        f.write('transaction_code\tmethod_name\tproto\tconstant_code\tproxy_code\tontransact_code\tsource_count\tsource_agreement\tparcel_contract\tsdk_direct_bridge\n')
        for r in result['method_contract']:
            pc=','.join(map(str,r['proxy_codes'])); oc=','.join(map(str,r['ontransact_codes']))
            f.write(f"{'' if r['transaction_code'] is None else r['transaction_code']}\t{r['name']}\t{r['proto']}\t{'' if r['constant_code'] is None else r['constant_code']}\t{pc}\t{oc}\t{r['independent_source_count']}\t{'YES' if r['source_agreement'] else 'NO'}\t{'YES' if r['parcel_contract_recovered'] else 'NO'}\t{'YES' if r['sdk_direct_bridge'] else 'NO'}\n")
    with (san/'test21-r3-3-4-2-6-1-sdk-wrapper-bridge.tsv').open('w') as f:
        f.write('caller_class\tcaller_method\tcaller_proto\tbinder_signature\tcaller_public\tcxr_namespace\n')
        for b in result['bridges']:
            f.write(f"{b['caller_class']}\t{b['caller_method']}\t{b['caller_proto']}\t{b['binder_signature']}\t{'YES' if b['caller_public'] else 'NO'}\t{'YES' if b['caller_sdk_namespace'] else 'NO'}\n")
    with (san/'test21-r3-3-4-2-6-1-parcel-contract.tsv').open('w') as f:
        f.write('method_name\tproto\ttransaction_code\tparcel_contract_recovered\tparcel_operations\n')
        for r in result['method_contract']:
            ops=' | '.join(r['parcel_operations'])
            f.write(f"{r['name']}\t{r['proto']}\t{'' if r['transaction_code'] is None else r['transaction_code']}\t{'YES' if r['parcel_contract_recovered'] else 'NO'}\t{ops}\n")


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--aar')
    ap.add_argument('--output',required=True)
    ap.add_argument('--fixture-mode',action='store_true')
    x=ap.parse_args()
    candidates=resolve_aar(x.aar,Path.home())
    if not candidates:
        raise SystemExit('ERROR: exact client-l 1.0.1 AAR not found in local Gradle/Maven cache; pass --aar <path>. No network or device access was attempted.')
    chosen=None
    if x.fixture_mode:
        chosen=candidates[0]
    else:
        for p in candidates:
            if p.is_file() and sha256_path(p)==EXPECTED_AAR_SHA256:
                chosen=p; break
        if chosen is None:
            found=', '.join(f'{p.name}:{sha256_path(p) if p.is_file() else "MISSING"}' for p in candidates)
            raise SystemExit('ERROR: no locally resolved AAR matches exact expected SHA-256. Candidates: '+found)
    result=analyze_aar(chosen,fixture_mode=x.fixture_mode)
    write_outputs(result,Path(x.output).resolve())
    print((Path(x.output).resolve()/'sanitized/test21-r3-3-4-2-6-1-summary.txt').read_text(),end='')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
