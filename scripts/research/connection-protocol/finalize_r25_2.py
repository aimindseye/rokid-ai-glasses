#!/usr/bin/env python3
from pathlib import Path
import argparse,hashlib,json,zipfile

def sha(p):
 h=hashlib.sha256(); h.update(p.read_bytes()); return h.hexdigest()
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--run',type=Path,required=True); a=ap.parse_args(); run=a.run.resolve()
 files=sorted(p for p in run.rglob('*') if p.is_file() and p.name not in {'SHA256SUMS-r25.2.json'})
 manifest={str(p.relative_to(run)):sha(p) for p in files}
 (run/'SHA256SUMS-r25.2.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
 files.append(run/'SHA256SUMS-r25.2.json')
 out=run.with_name(run.name+'-private-evidence.zip')
 with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
  for p in files:z.write(p,arcname=f'{run.name}/{p.relative_to(run)}')
 digest=sha(out); out.with_suffix(out.suffix+'.sha256').write_text(f'{digest}  {out.name}\n')
 print(f'R1_3_3_2_25_2_MANIFEST_COUNT={len(files)}')
 print(f'R1_3_3_2_25_2_PRIVATE_EVIDENCE_ZIP={out}')
 print(f'R1_3_3_2_25_2_PRIVATE_EVIDENCE_SHA256={digest}')
 print('R1_3_3_2_25_2_FINALIZE=PASS')
if __name__=='__main__': main()
