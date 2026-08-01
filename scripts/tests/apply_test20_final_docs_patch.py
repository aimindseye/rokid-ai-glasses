#!/usr/bin/env python3
from __future__ import annotations
import argparse, os, re, shutil, sys, tempfile
from pathlib import Path

FILES=[
 Path('docs/developer/current-status.md'),
 Path('docs/developer/companion-app/requirements.md'),
 Path('docs/research/connection-protocol/README.md'),
 Path('docs/research/README.md'),
 Path('docs/README.md'),
 Path('docs/tests/README.md'),
 Path('docs/tests/test-matrix.md'),
]
MARK='TEST20_FINAL_STATUS=ACCEPTED_CLOSED_IMPLEMENTATION_RULE_PUBLISHED'
class PatchError(RuntimeError): pass

def insert_before(text, marker, block, label):
    if block.strip() in text: return text
    c=text.count(marker)
    if c!=1: raise PatchError(f'{label}: expected one insertion marker, found {c}')
    return text.replace(marker,block+marker,1)

def replace_regex_once(text, pattern, replacement, label, flags=0):
    out,n=re.subn(pattern,replacement,text,count=1,flags=flags)
    if n!=1: raise PatchError(f'{label}: expected one match, found {n}')
    return out

def patch_status(text):
    if MARK in text: return text
    if '# Developer Current Status' not in text: raise PatchError('current-status heading missing')
    predecessor_rows=(
      '| CXR-L one-shot photo qualification | Not started; requires a separately governed r3.2 single-operation design |',
      '| CXR-L one-shot photo qualification | Test 20 r3.2 implementation ready for governed build and one physical attempt; exactly one bounded photo request, no payload persistence |',
    )
    final_row='| CXR-L one-shot photo qualification | Test 20 final accepted: two-phase one-shot gate and image callback path proven; post-service-status callback re-registration is the canonical tested lifecycle |'
    if final_row not in text:
        matches=[row for row in predecessor_rows if row in text]
        if len(matches)!=1:
            raise PatchError(f'current-status one-shot row not at a governed pre-final state (matches={len(matches)})')
        text=text.replace(matches[0],final_row,1)
    old2='| Independent camera capture | Not yet tested |'
    new2='| Independent camera capture | Qualified only through the custom CXR-L + Hi Rokid authorization/media-service path; direct/no-Hi-Rokid capture remains unqualified |'
    if old2 in text: text=text.replace(old2,new2,1)
    elif new2 not in text: raise PatchError('current-status camera row not at expected pre-final state')
    text=text.replace('last_reviewed=2026-07-31','last_reviewed=2026-08-01',1)
    text=text.replace('| Last reviewed | 2026-07-31 |','| Last reviewed | 2026-08-01 |',1)
    stale=(
      r'The accepted runtime-qualified delta is limited to\n'
      r'`setCXRImageCbk\(IImageStreamCbk\)`, `setCXRAudioCbk\(IAudioStreamCbk\)`,\n'
      r'`getServiceVersion\(\)`, `getServiceVersionCode\(\)`, and\n'
      r'`isGlassBtConnected\(\)`. Photo capture, audio streaming, payload formats,\n'
      r'parameter semantics, and media transport behavior remain unqualified\. The next\n'
      r'bounded gate is Test 20 r3\.2, a separately governed one-shot photo design\.\n'
    )
    final=(
      'Test 20 r3.2.1.3 subsequently proves the synchronized two-phase host-tokenized one-shot photo gate: '
      'zero requests before arm, zero before the operator tap, exactly one accepted request afterward, no audio operation, and successful Hi Rokid recovery.\n'
      'Test 20 r3.3 closes the remaining image-callback boundary. A strong callback retained and registered only before connection still timed out with the service stable; re-registering the same retained callback after successful connection/service-status qualification delivered one image payload callback with the unchanged `takePhoto(1920,1080,80)` request.\n'
      'The accepted implementation rule for the tested firmware/Hi Rokid/`client-l:1.0.1` environment is therefore strong callback retention plus mandatory post-service-status re-registration before photo readiness. This is a behavioral qualification and does not prove the SDK internal mechanism. Audio streaming, direct/no-Hi-Rokid camera capture, and generalized third-argument semantics remain unqualified.\n'
      f'`{MARK}`\n'
    )
    text=replace_regex_once(text,stale,final,'current-status stale Test20 next-gate paragraph',re.M)
    evidence=(
      '- [Test 20 r3.2.1.3 two-phase one-shot qualification](../tests/test-20-r3-2-1-3-two-phase-one-shot-photo-qualification.md)\n'
      '- [Test 20 r3.3 callback non-delivery closure](../tests/test-20-r3-3-post-takephoto-image-callback-closure.md)\n'
      '- [Test 20 final photo publication](../tests/test-20-final-photo-control-callback-publication.md)\n'
      '- [Published final photo/callback summary](../research/connection-protocol/publication/test20-final-cxr-l-one-shot-photo-and-callback-closure.md)\n'
    )
    text=text.replace('## Evidence\n','## Evidence\n'+evidence,1)
    return text

def patch_requirements(text):
    if '## Qualified CXR-L photo lifecycle' in text: return text
    if '# Companion-App Requirements' not in text: raise PatchError('requirements heading missing')
    text=text.replace('last_reviewed=2026-07-30','last_reviewed=2026-08-01',1)
    text=text.replace('| Last reviewed | 2026-07-30 |','| Last reviewed | 2026-08-01 |',1)
    block='''## Qualified CXR-L photo lifecycle\n\nFor the tested Rokid AI Glasses Style environment, HUB-04 now has a device-qualified CXR-L implementation rule:\n\n- retain one strong `IImageStreamCbk` object for the connection attempt;\n- register it before connection;\n- after CXR-L connected, glasses Bluetooth connected, and successful service-status qualification, re-register that same callback object;\n- do not expose photo readiness until the post-connect registration succeeds;\n- preserve a host-controlled two-phase one-shot gate and consume the arm atomically before `takePhoto()`;\n- keep payload preview/persistence and audio operations disabled unless separately qualified.\n\nThis rule is validated for firmware `1.23.009-20260725-151201`, Hi Rokid `G1.11.11.0727`, and `com.rokid.cxr:client-l:1.0.1`. It is not yet generalized to other versions or to direct capture without Hi Rokid.\n\n'''
    return insert_before(text,'## Safety and privacy requirements\n',block,'requirements lifecycle')

def patch_connection(text):
    if MARK in text: return text
    if '# Stock Connection Protocol and Minimal Companion Research' not in text: raise PatchError('connection README heading missing')
    block='''\n## Test 20 final CXR-L one-shot photo and callback closure\n\nTest 20 r3.2.1.3 and r3.3 close the bounded one-shot photo and image-callback path for the tested environment. r3.2.1.3 proves the two-phase host-tokenized one-shot gate. r3.3 shows that pre-connect-only image callback registration can accept the photo request yet deliver no callback while the service remains stable, whereas re-registering the same retained callback after successful service-status qualification delivers one image payload callback with the unchanged `takePhoto(1920,1080,80)` request.\n\nThe canonical implementation therefore retains the callback strongly, registers it pre-connect, re-registers the same object post-service-status, and only then permits photo readiness. `ARG3_ZERO_DIAGNOSTIC` was not run because callback delivery was already proven with the original third argument. The result is bounded to the tested firmware, Hi Rokid version, and `client-l:1.0.1`; it does not establish the SDK's internal mechanism.\n\n- [r3.2.1.3 two-phase one-shot qualification](../../tests/test-20-r3-2-1-3-two-phase-one-shot-photo-qualification.md)\n- [r3.3 callback closure](../../tests/test-20-r3-3-post-takephoto-image-callback-closure.md)\n- [final Test 20 publication](../../tests/test-20-final-photo-control-callback-publication.md)\n- [final machine publication](publication/test20-final-cxr-l-one-shot-photo-and-callback-closure.json)\n- [final human-readable publication](publication/test20-final-cxr-l-one-shot-photo-and-callback-closure.md)\n\n`'''+MARK+'''`\n'''
    return text.rstrip()+block+'\n'

def patch_research(text):
    if '### Test 20 final photo path' in text: return text
    if '# Research Index' not in text: raise PatchError('research README heading missing')
    block='''### Test 20 final photo path\n\n[Test 20 final photo control and callback publication](../tests/test-20-final-photo-control-callback-publication.md) closes the governed CXR-L one-shot photo work. The accepted implementation retains the image callback strongly and re-registers the same callback after successful service-status qualification before allowing photo arming.\n\n'''
    return insert_before(text,'## Current boundary\n',block,'research final block')

def patch_docs_index(text):
    if 'Test 20 final photo control and callback publication' in text: return text
    line='- [Test 20 final photo control and callback publication](tests/test-20-final-photo-control-callback-publication.md)\n'
    # Governed predecessor A: older documentation-index layout.
    if '# Documentation Index' in text:
        return insert_before(text,'## Protected companion research\n',line+'\n','docs index Test20 link')
    # Governed predecessor B: audience-first wiki layout introduced by r26.0 and
    # present on the Test 20 branch. Keep the link inside Research and evidence.
    if '# Documentation Home' in text:
        if '## Research and evidence\n' not in text:
            raise PatchError('docs home research-and-evidence section missing')
        return insert_before(text,'## Shared reference\n',line+'\n','docs home Test20 link')
    raise PatchError('docs index/home heading not at a governed predecessor state')

def patch_tests_readme(text):
    if '| 19–20 | CXR-L companion SDK qualification' in text: return text
    if '# Tests and Qualification History' not in text: raise PatchError('tests README heading missing')
    text=text.replace('numbered product/device tests through **Test 18**','numbered product/device tests through **Test 20**')
    marker='| 18 | Developer Mode and USB ADB control-path static/offline follow-up |\n'
    line='| 19–20 | CXR-L companion SDK qualification, one-shot photo control, and image-callback closure |\n'
    if marker not in text: raise PatchError('tests README Test18 row missing')
    return text.replace(marker,marker+line,1)

def patch_matrix(text):
    if '| 20 | CXR-L one-shot photo and callback closure' in text: return text
    if '# Test and Research Matrix' not in text: raise PatchError('test matrix heading missing')
    marker='| 18 | USB ADB control-path follow-up | 18A–18D | PASS in static/offline scope; runtime invocation unresolved | [Sanitized summary](../../evidence/sanitized/glasses-os-services/usb-adb-control-summary.txt) |\n'
    rows=(
      '| 19 | CXR-L non-display companion connection qualification | Firmware/app ownership and connection path | PASS in accepted Test 19 r2 scope | [Developer status](../developer/current-status.md) |\n'
      '| 20 | CXR-L one-shot photo and callback closure | Two-phase one-shot arm; callback lifecycle | PASS in tested environment; post-service-status callback re-registration required | [Final publication](test-20-final-photo-control-callback-publication.md) |\n'
    )
    if marker not in text: raise PatchError('test matrix Test18 row missing')
    return text.replace(marker,marker+rows,1)

PATCHERS=[patch_status,patch_requirements,patch_connection,patch_research,patch_docs_index,patch_tests_readme,patch_matrix]

def atomic(path,text):
    fd,tmp=tempfile.mkstemp(prefix='.'+path.name+'.',dir=str(path.parent),text=True)
    try:
        with os.fdopen(fd,'w',encoding='utf-8',newline='') as h: h.write(text); h.flush(); os.fsync(h.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--repo',required=True); ap.add_argument('--backup-dir'); ap.add_argument('--check-only',action='store_true'); a=ap.parse_args()
    repo=Path(a.repo).expanduser().resolve()
    if not (repo/'.git').is_dir(): print(f'ERROR: not git repo: {repo}',file=sys.stderr); return 2
    paths=[repo/p for p in FILES]
    for p in paths:
        if not p.is_file(): print(f'ERROR: required documentation path missing: {p}',file=sys.stderr); return 1
    originals={p:p.read_text(encoding='utf-8') for p in paths}
    try: updated={p:f(originals[p]) for p,f in zip(paths,PATCHERS)}
    except PatchError as e: print(f'ERROR: {e}',file=sys.stderr); print('REPOSITORY_MUTATION=NONE',file=sys.stderr); return 1
    changed=[p for p in paths if updated[p]!=originals[p]]
    if a.check_only:
        print('TEST20_FINAL_DOCS_PATCH_PREFLIGHT=PASS'); print(f'FILES_REQUIRING_PATCH={len(changed)}'); return 0
    if not changed: print('TEST20_FINAL_DOCS_PATCH=ALREADY_APPLIED'); return 0
    backup=Path(a.backup_dir).expanduser().resolve() if a.backup_dir else repo/'.git/test20-final-docs-backup'
    for p in changed:
        q=backup/p.relative_to(repo); q.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(p,q)
    try:
        for p in changed: atomic(p,updated[p])
    except Exception as e:
        for p in changed:
            q=backup/p.relative_to(repo)
            if q.is_file(): shutil.copy2(q,p)
        print(f'ERROR: docs write failed and restored: {e}',file=sys.stderr); return 1
    print('TEST20_FINAL_DOCS_PATCH=PASS'); print(f'FILES_PATCHED={len(changed)}'); print(f'BACKUP_DIR={backup}'); return 0
if __name__=='__main__': raise SystemExit(main())
