#!/usr/bin/env python3
"""Conservative macOS Bash 3.2 surface checker for public shell scripts."""
from __future__ import print_function
import argparse, os, re, sys

RULES = [
    ('bash4_mapfile', re.compile(r'(^|[^A-Za-z0-9_])(mapfile|readarray)([^A-Za-z0-9_]|$)')),
    ('bash4_assoc_array', re.compile(r'\b(declare|typeset)\s+-A\b')),
    ('bash4_case_conversion', re.compile(r'\$\{[^}]+(?:,,|\^\^)')),
    ('bash4_coproc', re.compile(r'(^|[;&|[:space:]])coproc([[:space:]]|$)') if False else re.compile(r'\bcoproc\b')),
    ('bash4_append_redirect', re.compile(r'&>>')),
]

def scan(path):
    findings=[]
    try: lines=open(path,'r',errors='replace').read().splitlines()
    except TypeError: lines=open(path,'r').read().splitlines()
    for n,line in enumerate(lines,1):
        for name,rx in RULES:
            if rx.search(line): findings.append((path,n,name,line.strip()))
    return findings

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('paths',nargs='+'); a=ap.parse_args(); files=[]
    for p in a.paths:
        if os.path.isdir(p):
            for dp,_,fns in os.walk(p):
                for fn in fns:
                    fp=os.path.join(dp,fn)
                    if fn.endswith('.sh') or os.access(fp,os.X_OK): files.append(fp)
        elif os.path.isfile(p): files.append(p)
    findings=[]
    for f in sorted(set(files)): findings += scan(f)
    if findings:
        print('MACOS_BASH32_PORTABILITY=FAIL')
        for f,n,name,line in findings: print('%s:%d:%s:%s' % (f,n,name,line))
        return 1
    print('MACOS_BASH32_PORTABILITY=PASS'); print('SCANNED_FILE_COUNT='+str(len(set(files)))); return 0
if __name__=='__main__': sys.exit(main())
