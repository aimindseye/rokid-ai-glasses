#!/usr/bin/env python3
from __future__ import annotations
import csv
from pathlib import Path
try:
    from .primitives import read_json
except ImportError:
    try:
        from scripts.research.canonical.primitives import read_json
    except ImportError:
        from primitives import read_json
BASE=Path(__file__).resolve().parent
PROFILES=BASE/'profiles'
EXCLUDE_PREFIXES=('scripts/research/canonical/','docs/research/r27.1.')
EXCLUDE_PATHS={'scripts/research/verify_r25_3_1_4_publication.py'}

def inbound_references(repo:Path, legacy_path:str)->list[str]:
    base=Path(legacy_path).name
    refs=[]
    for rootname in ('scripts','docs'):
        root=repo/rootname
        if not root.is_dir(): continue
        for p in root.rglob('*'):
            if not p.is_file(): continue
            rel=p.relative_to(repo).as_posix()
            if rel==legacy_path or rel in EXCLUDE_PATHS or rel.startswith(EXCLUDE_PREFIXES): continue
            try: text=p.read_text(encoding='utf-8',errors='ignore')
            except Exception: continue
            if legacy_path in text or base in text: refs.append(rel)
    return sorted(set(refs))

def rows(repo:Path)->list[dict]:
    out=[]
    r25=read_json(PROFILES/'r25-package-validators.json')['profiles']
    for rev,p in sorted(r25.items()):
        refs=inbound_references(repo,p['legacy_validator'])
        out.append({'family':'r25-package-validators','revision':rev,'legacy_path':p['legacy_validator'],'retirement_state':p.get('retirement_state','UNCLASSIFIED'),'inbound_reference_count':len(refs),'compatible_inbound_reference_count':0,'blocking_inbound_reference_count':len(refs),'inbound_references':';'.join(refs),'blocking_inbound_references':';'.join(refs)})
    packs=read_json(PROFILES/'test21-sanitized-packagers.json')['profiles']
    for rev,p in sorted(packs.items()):
        refs=inbound_references(repo,p['legacy_packager'])
        state=p.get('retirement_state','UNCLASSIFIED')
        compatible=list(refs) if state=='COMPATIBILITY_SHIM' else []
        blocking=[r for r in refs if r not in compatible]
        out.append({'family':'test21-sanitized-packagers','revision':rev,'legacy_path':p['legacy_packager'],'retirement_state':state,'inbound_reference_count':len(refs),'compatible_inbound_reference_count':len(compatible),'blocking_inbound_reference_count':len(blocking),'inbound_references':';'.join(refs),'blocking_inbound_references':';'.join(blocking)})
    return out

def emit(repo:Path,output:Path)->int:
    rs=rows(repo); output.parent.mkdir(parents=True,exist_ok=True)
    fields=['family','revision','legacy_path','retirement_state','inbound_reference_count','compatible_inbound_reference_count','blocking_inbound_reference_count','inbound_references','blocking_inbound_references']
    with output.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,delimiter='\t',lineterminator='\n'); w.writeheader(); w.writerows(rs)
    print('R27_1_10_RETIREMENT_DEPENDENCY_SCAN=PASS')
    print(f'RETIREMENT_DEPENDENCY_ENTRY_COUNT={len(rs)}')
    return 0
