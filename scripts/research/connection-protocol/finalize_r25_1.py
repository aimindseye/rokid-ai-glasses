#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,zipfile
from pathlib import Path

def sha(p:Path)->str:
    h=hashlib.sha256();
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--run',type=Path,required=True); args=ap.parse_args()
    run=args.run.resolve(); files=[p for p in run.rglob('*') if p.is_file() and p.name not in {'SHA256SUMS-r25.1.json'}]
    manifest={str(p.relative_to(run)):sha(p) for p in sorted(files)}
    (run/'SHA256SUMS-r25.1.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    out=run.parent/(run.name+'-private-analysis.zip')
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted([q for q in run.rglob('*') if q.is_file()]): z.write(p,Path(run.name)/p.relative_to(run))
    digest=sha(out); (Path(str(out)+'.sha256')).write_text(f'{digest}  {out.name}\n')
    print(f'R1_3_3_2_25_1_MANIFEST_COUNT={len(manifest)+1}')
    print(f'R1_3_3_2_25_1_PRIVATE_ANALYSIS_ZIP={out}')
    print(f'R1_3_3_2_25_1_PRIVATE_ANALYSIS_SHA256={digest}')
    print('R1_3_3_2_25_1_FINALIZE=PASS')
    return 0
if __name__=='__main__': raise SystemExit(main())
