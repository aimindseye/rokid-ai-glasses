#!/usr/bin/env python3
import argparse
import re
from pathlib import Path

REQUIRED_FILES = [
    'docs/research/cxr/test21-static-binder-boundary-overview.md',
    'docs/research/cxr/test21-static-binder-boundary-findings.md',
    'docs/research/cxr/test21-static-binder-boundary-diagrams.md',
    'docs/research/cxr/test21-callback-transaction-reference.md',
    'docs/research/cxr/test21-publication-checklist.md',
]

REQUIRED_OVERVIEW_PHRASES = [
    'static clean-room Binder boundary',
    'callback interfaces: **7/7**',
    'callback methods: **21/21**',
    'CLEAN_ROOM_FULL_BINDER_BOUNDARY_READY=YES',
    'FUNCTIONAL_BEHAVIOR_COMPATIBILITY_PROVEN=NO',
]

REQUIRED_FINDINGS_PHRASES = [
    '14/21',
    '7 methods',
    '21/21',
    'mismatches: **0**',
    'AUTHORIZATION_SEMANTICS_RECOVERED=NO',
    'SERVICE_IMPLEMENTATION_RECOVERED=NO',
]

REQUIRED_CHECKLIST_PHRASES = [
    'Claims allowed',
    'Not allowed',
    'Mermaid diagrams render correctly on GitHub',
]

EXPECTED_CALLBACK_ROWS = 21


def count_callback_rows(text: str) -> int:
    count = 0
    for line in text.splitlines():
        if line.startswith('| ') and '`com.rokid.sprite.aiapp.externalapp.' in line and not line.startswith('| Interface label '):
            count += 1
    return count


def verify(repo: Path) -> int:
    rc = 0
    for rel in REQUIRED_FILES:
        path = repo / rel
        if not path.is_file():
            print(f'MISSING={rel}')
            rc = 1
    if rc:
        return rc

    overview = (repo / REQUIRED_FILES[0]).read_text(encoding='utf-8')
    findings = (repo / REQUIRED_FILES[1]).read_text(encoding='utf-8')
    diagrams = (repo / REQUIRED_FILES[2]).read_text(encoding='utf-8')
    callback_ref = (repo / REQUIRED_FILES[3]).read_text(encoding='utf-8')
    checklist = (repo / REQUIRED_FILES[4]).read_text(encoding='utf-8')

    for phrase in REQUIRED_OVERVIEW_PHRASES:
        if phrase not in overview:
            print(f'OVERVIEW_MISSING_PHRASE={phrase}')
            rc = 1
    for phrase in REQUIRED_FINDINGS_PHRASES:
        if phrase not in findings:
            print(f'FINDINGS_MISSING_PHRASE={phrase}')
            rc = 1
    for phrase in REQUIRED_CHECKLIST_PHRASES:
        if phrase not in checklist:
            print(f'CHECKLIST_MISSING_PHRASE={phrase}')
            rc = 1

    mermaid_blocks = diagrams.count('```mermaid')
    if mermaid_blocks < 5:
        print(f'MERMAID_BLOCK_COUNT_TOO_LOW={mermaid_blocks}')
        rc = 1

    callback_rows = count_callback_rows(callback_ref)
    if callback_rows != EXPECTED_CALLBACK_ROWS:
        print(f'CALLBACK_ROW_COUNT_MISMATCH={callback_rows}')
        rc = 1

    if 'FULL_STATIC_BINDER_BOUNDARY_CLOSED' not in findings:
        print('FINDINGS_DISPOSITION_MISSING=FULL_STATIC_BINDER_BOUNDARY_CLOSED')
        rc = 1

    # simple broken-link lint for the overview cross-links
    overview_links = re.findall(r'\]\((\./[^)]+)\)', overview)
    for link in overview_links:
        target = (repo / 'docs/research/cxr' / link[2:]).resolve()
        if not target.is_file():
            print(f'BROKEN_OVERVIEW_LINK={link}')
            rc = 1

    if rc == 0:
        print('TEST21_GITHUB_PUBLICATION_DOCS_VERIFY=PASS')
        print(f'MERMAID_BLOCK_COUNT={mermaid_blocks}')
        print(f'CALLBACK_TABLE_ROWS={callback_rows}')
    return rc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', required=True, help='Repository root or overlay root')
    args = parser.parse_args()
    return verify(Path(args.repo))

if __name__ == '__main__':
    raise SystemExit(main())
