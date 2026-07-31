#!/usr/bin/env python3
"""Resolve and attest Rokid CXR-M from the public Rokid Nexus repository."""
from __future__ import annotations
import argparse, hashlib, json, re, urllib.error, urllib.request, xml.etree.ElementTree as ET
from pathlib import Path

REPO = "https://maven.rokid.com/repository/maven-public/"
GROUP_PATH = "com/rokid/cxr/client-m"
METADATA = REPO + GROUP_PATH + "/maven-metadata.xml"
VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]*$")

def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024), b''): h.update(chunk)
    return h.hexdigest()

def fetch(url: str, out: Path, timeout: int) -> dict:
    req=urllib.request.Request(url, headers={"User-Agent":"rokid-ai-glasses-test19-r1/1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data=r.read(); status=getattr(r,'status',200); ctype=r.headers.get('Content-Type','')
    out.parent.mkdir(parents=True,exist_ok=True); out.write_bytes(data)
    return {"url":url,"http_status":status,"content_type":ctype,"size":len(data),"sha256":sha256(out),"file":out.name}

def parse_versions(path: Path) -> tuple[list[str], str|None, str|None]:
    root=ET.fromstring(path.read_bytes())
    versions=[(v.text or '').strip() for v in root.findall('./versioning/versions/version') if (v.text or '').strip()]
    release=(root.findtext('./versioning/release') or '').strip() or None
    latest=(root.findtext('./versioning/latest') or '').strip() or None
    return versions, release, latest

def choose(versions:list[str], release:str|None, latest:str|None, requested:str|None)->str:
    if requested:
        if requested not in versions: raise ValueError(f"requested version not listed in metadata: {requested}")
        return requested
    if release in versions: return release  # type: ignore[arg-type]
    if latest in versions: return latest  # type: ignore[arg-type]
    if not versions: raise ValueError('metadata contains no versions')
    return versions[-1]

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--output',required=True)
    ap.add_argument('--version')
    ap.add_argument('--timeout',type=int,default=30)
    ap.add_argument('--metadata-url',default=METADATA,help=argparse.SUPPRESS)
    ap.add_argument('--repository-url',default=REPO,help=argparse.SUPPRESS)
    args=ap.parse_args()
    out=Path(args.output).resolve(); out.mkdir(parents=True,exist_ok=True)
    report={"schema":"rokid.test19-r1.maven-resolution.v1","repository":args.repository_url,"metadata_url":args.metadata_url,"working":False,"files":[]}
    try:
        md=out/'maven-metadata.xml'; report['files'].append(fetch(args.metadata_url,md,args.timeout))
        versions,release,latest=parse_versions(md)
        version=choose(versions,release,latest,args.version)
        if not VERSION_RE.fullmatch(version): raise ValueError('unsafe version token')
        base=f"{args.repository_url.rstrip('/')}/{GROUP_PATH}/{version}/client-m-{version}"
        pom=out/f"client-m-{version}.pom"; aar=out/f"client-m-{version}.aar"
        report['files'].append(fetch(base+'.pom',pom,args.timeout))
        report['files'].append(fetch(base+'.aar',aar,args.timeout))
        report.update({"working":True,"version":version,"metadata_release":release,"metadata_latest":latest,"versions":versions,"coordinate":f"com.rokid.cxr:client-m:{version}","aar":str(aar),"pom":str(pom)})
    except Exception as e:
        report.update({"error_class":type(e).__name__,"error":str(e)})
    (out/'resolution.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2,sort_keys=True))
    return 0 if report['working'] else 3
if __name__=='__main__': raise SystemExit(main())
