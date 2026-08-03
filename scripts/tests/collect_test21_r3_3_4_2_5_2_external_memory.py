#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, math, os, re, struct, subprocess, sys
from pathlib import Path

PKG='com.rokid.sprite.global.aiapp'
DEX_MAGICS=tuple(b'dex\n'+f'{v:03d}'.encode('ascii')+b'\0' for v in range(35,42))
CDEX_MAGIC=b'cdex001\x00'
PAGE=4096
DEFAULT_CHUNK=8*1024*1024
DEFAULT_TOTAL=256*1024*1024
MAX_DEX=64*1024*1024
MAX_RECOVERED=256*1024*1024
MAX_CANDIDATES=64

def sha_bytes(b:bytes)->str:return hashlib.sha256(b).hexdigest()

def run_text(cmd:list[str],timeout=15):
 cp=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
 return cp.returncode,cp.stdout.decode('utf-8','replace').replace('\r',''),cp.stderr.decode('utf-8','replace').replace('\r','')

def parse_maps(text:str):
 rows=[]
 rx=re.compile(r'^([0-9a-fA-F]+)-([0-9a-fA-F]+)\s+(\S+)\s+\S+\s+\S+\s+\S+(?:\s+(.*))?$')
 for line in text.splitlines():
  m=rx.match(line.strip())
  if not m:continue
  start,end=int(m.group(1),16),int(m.group(2),16);perms=m.group(3);path=(m.group(4) or '').strip()
  if end<=start:continue
  rows.append({'start':start,'end':end,'size':end-start,'perms':perms,'path':path})
 return rows

def bucket(row):
 p=row['path'].lower();perms=row['perms']
 if not perms.startswith('r'):return 99
 if any(k in p for k in ('dalvik','dex','jit','memfd','ashmem','code_cache','rokid','sprite','aiapp')):return 0
 if not p or p.startswith('['):return 1
 if p.startswith('/data/user/') or p.startswith('/data/data/'):return 1
 if p.startswith('/data/'):return 2
 return 3

def plan_chunks(rows,chunk_size=DEFAULT_CHUNK,max_total=DEFAULT_TOTAL):
 out=[];used=0
 for row in sorted(rows,key=lambda r:(bucket(r),r['start'])):
  b=bucket(row)
  if b>=99:continue
  # Static /system library mappings are lowest value; only reached after runtime/app mappings.
  pos=row['start']
  while pos<row['end'] and used<max_total:
   n=min(chunk_size,row['end']-pos,max_total-used)
   if n<=0:break
   out.append({'start':pos,'size':n,'bucket':b,'path':row['path'],'perms':row['perms']})
   used+=n;pos+=n
  if used>=max_total:break
 return out

def validate_dex_header(data:bytes,off:int=0):
 if off<0 or off+0x70>len(data):return None
 magic=data[off:off+8]
 if magic not in DEX_MAGICS:return None
 file_size=struct.unpack_from('<I',data,off+0x20)[0]
 header_size=struct.unpack_from('<I',data,off+0x24)[0]
 endian=struct.unpack_from('<I',data,off+0x28)[0]
 if header_size!=0x70 or endian not in (0x12345678,0x78563412):return None
 if file_size<0x70 or file_size>MAX_DEX:return None
 return {'magic':magic.decode('latin1'),'file_size':file_size,'header_size':header_size,'endian_tag':endian}

def magic_offsets(data:bytes):
 out=[]
 for magic in DEX_MAGICS:
  p=0
  while True:
   i=data.find(magic,p)
   if i<0:break
   out.append(('DEX',i,magic));p=i+1
 p=0
 while True:
  i=data.find(CDEX_MAGIC,p)
  if i<0:break
  out.append(('CDEX',i,CDEX_MAGIC));p=i+1
 return sorted(out,key=lambda x:x[1])

def read_mem(adb,phone,pid,address,size,timeout=30):
 page_start=address & ~(PAGE-1);lead=address-page_start;need=lead+size;pages=(need+PAGE-1)//PAGE
 cmd=[adb,'-s',phone,'exec-out','su','-c',f'dd if=/proc/{pid}/mem bs={PAGE} skip={page_start//PAGE} count={pages} status=none']
 try:
  cp=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
 except subprocess.TimeoutExpired:return None,'TIMEOUT'
 data=cp.stdout
 if len(data)<=lead:return None,('RC_%d:'%cp.returncode)+cp.stderr.decode('utf-8','replace')[:160]
 payload=data[lead:lead+size]
 if not payload:return None,('RC_%d:'%cp.returncode)+cp.stderr.decode('utf-8','replace')[:160]
 return payload,('PASS' if cp.returncode==0 and len(data)>=lead+size else 'PARTIAL')

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--phone',required=True);ap.add_argument('--output',required=True);ap.add_argument('--adb',default='adb');ap.add_argument('--chunk-size',type=int,default=DEFAULT_CHUNK);ap.add_argument('--max-total-bytes',type=int,default=DEFAULT_TOTAL);a=ap.parse_args()
 out=Path(a.output);out.mkdir(parents=True,exist_ok=True);dexdir=out/'recovered-dex';dexdir.mkdir(exist_ok=True)
 state=run_text([a.adb,'-s',a.phone,'get-state']);
 if state[0]!=0 or 'device' not in state[1]:print('ERROR: device offline',file=sys.stderr);return 2
 rc,root_id,root_err=run_text([a.adb,'-s',a.phone,'shell','su','-c','id']);root_ok=('uid=0' in root_id)
 if not root_ok:print('ROOT_PROBE=UNAVAILABLE');return 3
 print('ROOT_PROBE=AVAILABLE')
 rc,pidtxt,_=run_text([a.adb,'-s',a.phone,'shell','pidof',PKG]);pid=pidtxt.strip().split()[0] if pidtxt.strip() else ''
 if not pid:print('HI_ROKID_PROCESS_VISIBLE=NO');print('ERROR: Hi Rokid must already be running; collector will not launch it');return 4
 print('HI_ROKID_PROCESS_VISIBLE=YES')
 rc,maps,merr=run_text([a.adb,'-s',a.phone,'shell','su','-c',f'cat /proc/{pid}/maps'],timeout=20)
 if rc!=0 or not maps.strip():print('ROOT_PROCESS_MAPS_ACCESS=UNAVAILABLE');return 5
 print('ROOT_PROCESS_MAPS_ACCESS=READABLE')
 (out/'process-maps.txt').write_text(maps);rows=parse_maps(maps);plan=plan_chunks(rows,a.chunk_size,a.max_total_bytes)
 manifest=[];magic_hits=0;cdex_hits=0;valid_hits=0;read_errors=0;bytes_read=0;seen_addr=set();seen_sha={};recovered_bytes=0;probe_success=False;probe_denied=False
 for ci,ch in enumerate(plan):
  data,status=read_mem(a.adb,a.phone,pid,ch['start'],ch['size'],timeout=45)
  if data is None:
   read_errors+=1
   if 'PERMISSION' in status.upper() or 'DENIED' in status.upper():probe_denied=True
   manifest.append({'chunk':ci,'bucket':ch['bucket'],'requested_bytes':ch['size'],'bytes_read':0,'read_status':status[:180],'mapping_start':hex(ch['start']),'mapping_path':ch['path']})
   continue
  probe_success=True
  if status!='PASS':read_errors+=1
  bytes_read+=len(data);manifest.append({'chunk':ci,'bucket':ch['bucket'],'requested_bytes':ch['size'],'bytes_read':len(data),'read_status':status,'mapping_start':hex(ch['start']),'mapping_path':ch['path'],'chunk_sha256':sha_bytes(data)})
  for kind,off,magic in magic_offsets(data):
   addr=ch['start']+off
   if addr in seen_addr:continue
   seen_addr.add(addr)
   if kind=='CDEX':cdex_hits+=1;continue
   magic_hits+=1;hdr=validate_dex_header(data,off)
   if not hdr:continue
   valid_hits+=1
   if len(seen_sha)>=MAX_CANDIDATES or recovered_bytes>=MAX_RECOVERED:continue
   full,full_status=read_mem(a.adb,a.phone,pid,addr,hdr['file_size'],timeout=60)
   if full is None or len(full)<hdr['file_size'] or not validate_dex_header(full,0):
    read_errors+=1;continue
   full=full[:hdr['file_size']];h=sha_bytes(full)
   if h in seen_sha:continue
   if recovered_bytes+len(full)>MAX_RECOVERED:continue
   idx=len(seen_sha)+1;name=f'external-memory-dex-{idx:03d}.dex';(dexdir/name).write_bytes(full);recovered_bytes+=len(full);seen_sha[h]=name
   manifest.append({'recovered_dex':name,'sha256':h,'size':len(full),'source_address':hex(addr),'source_mapping_path':ch['path'],'source_bucket':ch['bucket'],'read_status':full_status})
 access='READABLE' if probe_success else ('DENIED' if probe_denied else 'UNREADABLE_OR_UNSUPPORTED')
 private={'schema':'rokid.test21-r3.3.4.2.5.2.external-memory.private.v1','root_id':root_id.strip(),'pid':pid,'process_maps_access':'READABLE','external_proc_mem_access':access,'readable_mapping_count':sum(1 for r in rows if r['perms'].startswith('r')),'selected_chunk_count':len(plan),'selected_bytes':sum(x['size'] for x in plan),'memory_bytes_read':bytes_read,'dex_magic_hit_count':magic_hits,'cdex_magic_hit_count':cdex_hits,'dex_validated_count':valid_hits,'dex_recovered_unique_count':len(seen_sha),'dex_recovered_bytes':recovered_bytes,'memory_read_error_count':read_errors,'manifest':manifest,'limits':{'chunk_size':a.chunk_size,'max_total_bytes':a.max_total_bytes,'max_dex_bytes':MAX_DEX,'max_recovered_bytes':MAX_RECOVERED,'max_candidates':MAX_CANDIDATES}}
 (out/'external-memory-private.json').write_text(json.dumps(private,indent=2,sort_keys=True)+'\n')
 print('EXTERNAL_PROC_MEM_ACCESS='+access)
 print('READABLE_MAPPING_COUNT='+str(private['readable_mapping_count']))
 print('SELECTED_MEMORY_CHUNK_COUNT='+str(len(plan)))
 print('MEMORY_BYTES_READ='+str(bytes_read))
 print('DEX_MAGIC_HIT_COUNT='+str(magic_hits))
 print('CDEX_MAGIC_HIT_COUNT='+str(cdex_hits))
 print('DEX_VALIDATED_COUNT='+str(valid_hits))
 print('DEX_RECOVERED_UNIQUE_COUNT='+str(len(seen_sha)))
 print('MEMORY_READ_ERROR_COUNT='+str(read_errors))
 print('FRIDA_SERVER_START=NONE')
 print('FRIDA_PROCESS_ATTACH=NONE')
 print('INJECTED_AGENT_LOAD=NONE')
 print('PTRACE_ATTACH=NONE')
 print('PROCESS_SIGNAL=NONE')
 return 0
if __name__=='__main__':raise SystemExit(main())
