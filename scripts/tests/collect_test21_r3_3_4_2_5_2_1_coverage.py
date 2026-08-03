#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import struct
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

PKG = 'com.rokid.sprite.global.aiapp'
PAGE = 4096
DEX_MAGICS = tuple(b'dex\n' + f'{v:03d}'.encode('ascii') + b'\0' for v in range(35, 42))
CDEX_MAGIC = b'cdex001\x00'
DEFAULT_TOP_CHUNK = 8 * 1024 * 1024
DEFAULT_TOTAL = 256 * 1024 * 1024
DEFAULT_MAX_ATTEMPTS = 8192
DEFAULT_MAX_SECONDS = 900
MAX_DEX = 64 * 1024 * 1024
MAX_RECOVERED = 256 * 1024 * 1024
MAX_CANDIDATES = 64
QUAL_SIZES = (4 * 1024, 16 * 1024, 64 * 1024, 256 * 1024, 1024 * 1024)
SHORT_OUTPUT_LIMIT = PAGE - 1


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run_text(cmd: list[str], timeout: int = 15):
    cp = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    return (
        cp.returncode,
        cp.stdout.decode('utf-8', 'replace').replace('\r', ''),
        cp.stderr.decode('utf-8', 'replace').replace('\r', ''),
    )


def parse_maps(text: str):
    rows = []
    rx = re.compile(r'^([0-9a-fA-F]+)-([0-9a-fA-F]+)\s+(\S+)\s+\S+\s+\S+\s+\S+(?:\s+(.*))?$')
    for line in text.splitlines():
        m = rx.match(line.strip())
        if not m:
            continue
        start, end = int(m.group(1), 16), int(m.group(2), 16)
        perms = m.group(3)
        path = (m.group(4) or '').strip()
        if end <= start:
            continue
        rows.append({'start': start, 'end': end, 'size': end - start, 'perms': perms, 'path': path})
    return rows


def bucket(row):
    p = row['path'].lower()
    perms = row['perms']
    if not perms.startswith('r'):
        return 99
    if any(k in p for k in ('dalvik', 'dex', 'jit', 'memfd', 'ashmem', 'code_cache', 'rokid', 'sprite', 'aiapp')):
        return 0
    if not p or p.startswith('['):
        return 1
    if p.startswith('/data/user/') or p.startswith('/data/data/'):
        return 1
    if p.startswith('/data/'):
        return 2
    return 3


def plan_chunks(rows, chunk_size=DEFAULT_TOP_CHUNK, max_total=DEFAULT_TOTAL):
    out = []
    used = 0
    for row in sorted(rows, key=lambda r: (bucket(r), r['start'])):
        b = bucket(row)
        if b >= 99:
            continue
        pos = row['start']
        while pos < row['end'] and used < max_total:
            n = min(chunk_size, row['end'] - pos, max_total - used)
            if n <= 0:
                break
            # /proc maps are page-aligned; retain exact final mapping length if unusual.
            out.append({'start': pos, 'size': n, 'bucket': b, 'path': row['path'], 'perms': row['perms']})
            used += n
            pos += n
        if used >= max_total:
            break
    return out


def validate_dex_header(data: bytes, off: int = 0):
    if off < 0 or off + 0x70 > len(data):
        return None
    magic = data[off:off + 8]
    if magic not in DEX_MAGICS:
        return None
    file_size = struct.unpack_from('<I', data, off + 0x20)[0]
    header_size = struct.unpack_from('<I', data, off + 0x24)[0]
    endian = struct.unpack_from('<I', data, off + 0x28)[0]
    if header_size != 0x70 or endian not in (0x12345678, 0x78563412):
        return None
    if file_size < 0x70 or file_size > MAX_DEX:
        return None
    return {'magic': magic.decode('latin1'), 'file_size': file_size, 'header_size': header_size, 'endian_tag': endian}


def magic_offsets(data: bytes):
    out = []
    for magic in DEX_MAGICS:
        p = 0
        while True:
            i = data.find(magic, p)
            if i < 0:
                break
            out.append(('DEX', i, magic))
            p = i + 1
    p = 0
    while True:
        i = data.find(CDEX_MAGIC, p)
        if i < 0:
            break
        out.append(('CDEX', i, CDEX_MAGIC))
        p = i + 1
    return sorted(out, key=lambda x: x[1])


def trusted_prefix_length(returned_bytes: int, requested_bytes: int) -> int:
    """Only complete pages from a short read are trusted as memory coverage."""
    if returned_bytes >= requested_bytes:
        return requested_bytes
    if returned_bytes < PAGE:
        return 0
    return min(requested_bytes, (returned_bytes // PAGE) * PAGE)


def looks_text_like_short(data: bytes) -> bool:
    if not data or len(data) > SHORT_OUTPUT_LIMIT:
        return False
    printable = sum(1 for b in data if b in (9, 10, 13) or 32 <= b <= 126)
    return printable / len(data) >= 0.80


def read_mem_once(adb: str, phone: str, pid: str, address: int, size: int, timeout: int = 30):
    page_start = address & ~(PAGE - 1)
    lead = address - page_start
    need = lead + size
    pages = (need + PAGE - 1) // PAGE
    # Remote stderr is suppressed deliberately. r3.3.4.2.5.2 counted 47-byte
    # command/error output as memory. This repair treats only stdout as candidate bytes.
    remote = f'dd if=/proc/{pid}/mem bs={PAGE} skip={page_start // PAGE} count={pages} status=none 2>/dev/null'
    cmd = [adb, '-s', phone, 'exec-out', 'su', '-c', remote]
    started = time.monotonic()
    try:
        cp = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {
            'status': 'TIMEOUT', 'requested_bytes': size, 'stdout_bytes': 0, 'payload': b'',
            'trusted_prefix_bytes': 0, 'rc': None, 'host_stderr_bytes': 0,
            'duration_ms': int((time.monotonic() - started) * 1000), 'text_like_short': False,
        }
    raw = cp.stdout
    payload = raw[lead:lead + size] if len(raw) > lead else b''
    if len(payload) >= size and cp.returncode == 0:
        status = 'FULL'
    elif payload:
        status = 'PARTIAL'
    else:
        status = 'FAILED' if cp.returncode != 0 else 'ZERO'
    return {
        'status': status,
        'requested_bytes': size,
        'stdout_bytes': len(raw),
        'payload': payload,
        'trusted_prefix_bytes': trusted_prefix_length(len(payload), size),
        'rc': cp.returncode,
        'host_stderr_bytes': len(cp.stderr),
        'duration_ms': int((time.monotonic() - started) * 1000),
        'text_like_short': looks_text_like_short(payload),
    }


def merge_segments(segments):
    """Merge adjacent non-overlapping trusted byte segments into contiguous runs."""
    if not segments:
        return []
    rows = sorted(segments, key=lambda x: x['start'])
    out = []
    for seg in rows:
        start = seg['start']
        data = seg['data']
        end = start + len(data)
        if not data:
            continue
        if not out:
            out.append({'start': start, 'data': bytearray(data), 'sources': [seg.get('source', '')]})
            continue
        prev = out[-1]
        prev_end = prev['start'] + len(prev['data'])
        if start == prev_end:
            prev['data'].extend(data)
            prev['sources'].append(seg.get('source', ''))
        elif start > prev_end:
            out.append({'start': start, 'data': bytearray(data), 'sources': [seg.get('source', '')]})
        else:
            overlap = prev_end - start
            if overlap < len(data):
                prev['data'].extend(data[overlap:])
                prev['sources'].append(seg.get('source', ''))
    return [{'start': x['start'], 'data': bytes(x['data']), 'sources': x['sources']} for x in out]


def interval_union_bytes(intervals):
    if not intervals:
        return 0
    rows = sorted((s, e) for s, e in intervals if e > s)
    total = 0
    cs, ce = rows[0]
    for s, e in rows[1:]:
        if s <= ce:
            ce = max(ce, e)
        else:
            total += ce - cs
            cs, ce = s, e
    return total + ce - cs


def characterize_prior(evidence_root: str | None):
    if not evidence_root:
        return {'available': False}
    root = Path(evidence_root)
    candidates = [
        root / 'private/external-memory/external-memory-private.json',
        root / 'external-memory-private.json',
    ]
    p = next((x for x in candidates if x.is_file()), None)
    if p is None:
        return {'available': False, 'reason': 'PRIVATE_JSON_NOT_FOUND'}
    try:
        d = json.loads(p.read_text())
    except Exception:
        return {'available': False, 'reason': 'PRIVATE_JSON_PARSE_FAILED'}
    sizes = Counter()
    statuses = Counter()
    hashes = Counter()
    partial = 0
    for row in d.get('manifest') or []:
        if 'chunk' not in row:
            continue
        n = int(row.get('bytes_read') or 0)
        sizes[n] += 1
        statuses[str(row.get('read_status', 'UNRESOLVED'))] += 1
        if str(row.get('read_status')) == 'PARTIAL':
            partial += 1
        h = row.get('chunk_sha256')
        if h and n < PAGE:
            hashes[str(h)] += 1
    selected = int(d.get('selected_bytes') or 0)
    read = int(d.get('memory_bytes_read') or 0)
    mode_size, mode_count = (sizes.most_common(1)[0] if sizes else (0, 0))
    return {
        'available': True,
        'selected_bytes': selected,
        'memory_bytes_read': read,
        'coverage_percent': (100.0 * read / selected) if selected else None,
        'partial_read_count': partial,
        'returned_size_mode_bytes': mode_size,
        'returned_size_mode_count': mode_count,
        'duplicate_short_output_max_count': max(hashes.values()) if hashes else 0,
        'status_counts': dict(statuses),
    }


def choose_qualification_mapping(rows, adb, phone, pid, max_probes=64):
    probes = []
    denied = False
    for row in sorted(rows, key=lambda r: (bucket(r), r['start'])):
        if not row['perms'].startswith('r') or row['size'] < PAGE:
            continue
        result = read_mem_once(adb, phone, pid, row['start'], PAGE, timeout=12)
        probes.append({
            'bucket': bucket(row), 'mapping_size': row['size'], 'requested_bytes': PAGE,
            'returned_bytes': len(result['payload']), 'trusted_prefix_bytes': result['trusted_prefix_bytes'],
            'status': result['status'], 'rc': result['rc'], 'text_like_short': result['text_like_short'],
            'payload_sha256': sha_bytes(result['payload']) if result['payload'] else None,
        })
        if result['status'] == 'FULL':
            return row, probes, denied
        if result['status'] in ('FAILED', 'ZERO') and result['rc'] not in (None, 0):
            denied = denied or False
        if len(probes) >= max_probes:
            break
    return None, probes, denied


def qualification_ladder(row, adb, phone, pid):
    out = []
    duplicate_hashes = Counter()
    for size in QUAL_SIZES:
        n = min(size, row['size'])
        n = max(PAGE, (n // PAGE) * PAGE)
        result = read_mem_once(adb, phone, pid, row['start'], n, timeout=20)
        payload = result['payload']
        h = sha_bytes(payload) if payload and len(payload) < PAGE else None
        if h:
            duplicate_hashes[h] += 1
        out.append({
            'requested_bytes': n,
            'returned_bytes': len(payload),
            'trusted_prefix_bytes': result['trusted_prefix_bytes'],
            'status': result['status'],
            'rc': result['rc'],
            'text_like_short': result['text_like_short'],
            'short_output_sha256': h,
            'duration_ms': result['duration_ms'],
        })
        if n >= row['size']:
            break
    return out, (max(duplicate_hashes.values()) if duplicate_hashes else 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--phone', required=True)
    ap.add_argument('--output', required=True)
    ap.add_argument('--adb', default='adb')
    ap.add_argument('--prior-evidence')
    ap.add_argument('--top-chunk-size', type=int, default=DEFAULT_TOP_CHUNK)
    ap.add_argument('--max-total-bytes', type=int, default=DEFAULT_TOTAL)
    ap.add_argument('--max-attempts', type=int, default=DEFAULT_MAX_ATTEMPTS)
    ap.add_argument('--max-seconds', type=int, default=DEFAULT_MAX_SECONDS)
    a = ap.parse_args()

    out = Path(a.output)
    out.mkdir(parents=True, exist_ok=True)
    segdir = out / 'coverage-segments'
    dexdir = out / 'recovered-dex'
    segdir.mkdir(exist_ok=True)
    dexdir.mkdir(exist_ok=True)

    state = run_text([a.adb, '-s', a.phone, 'get-state'])
    if state[0] != 0 or 'device' not in state[1]:
        print('ERROR: device offline', file=sys.stderr)
        return 2

    rc, root_id, _ = run_text([a.adb, '-s', a.phone, 'shell', 'su', '-c', 'id'])
    if rc != 0 or 'uid=0' not in root_id:
        print('ROOT_PROBE=UNAVAILABLE')
        return 3
    print('ROOT_PROBE=AVAILABLE')

    rc, pidtxt, _ = run_text([a.adb, '-s', a.phone, 'shell', 'pidof', PKG])
    pid = pidtxt.strip().split()[0] if pidtxt.strip() else ''
    if not pid:
        print('HI_ROKID_PROCESS_VISIBLE=NO')
        print('ERROR: Hi Rokid must already be running; collector will not launch it')
        return 4
    print('HI_ROKID_PROCESS_VISIBLE=YES')

    rc, maps, _ = run_text([a.adb, '-s', a.phone, 'shell', 'su', '-c', f'cat /proc/{pid}/maps'], timeout=20)
    if rc != 0 or not maps.strip():
        print('ROOT_PROCESS_MAPS_ACCESS=UNAVAILABLE')
        return 5
    print('ROOT_PROCESS_MAPS_ACCESS=READABLE')
    (out / 'process-maps.txt').write_text(maps)

    rows = parse_maps(maps)
    readable_rows = [r for r in rows if r['perms'].startswith('r')]
    readable_bytes = sum(r['size'] for r in readable_rows)
    plan = plan_chunks(rows, a.top_chunk_size, a.max_total_bytes)
    selected_bytes = sum(x['size'] for x in plan)

    prior = characterize_prior(a.prior_evidence)

    qrow, qsearch, _ = choose_qualification_mapping(rows, a.adb, a.phone, pid)
    qladder = []
    qdup = 0
    if qrow is not None:
        qladder, qdup = qualification_ladder(qrow, a.adb, a.phone, pid)

    start_time = time.monotonic()
    attempts = 0
    attempted_bytes = 0
    full_range_count = 0
    partial_range_count = 0
    failed_range_count = 0
    zero_range_count = 0
    timeout_range_count = 0
    suspicious_subpage_count = 0
    full_read_bytes = 0
    partial_prefix_bytes = 0
    segments = []
    read_manifest = []
    stop_reason = 'COMPLETE'

    def budget_ok():
        nonlocal stop_reason
        if attempts >= a.max_attempts:
            stop_reason = 'MAX_ATTEMPTS'
            return False
        if time.monotonic() - start_time >= a.max_seconds:
            stop_reason = 'MAX_SECONDS'
            return False
        return True

    def record_segment(start: int, data: bytes, source: str, top_index: int):
        nonlocal full_read_bytes, partial_prefix_bytes
        if not data:
            return
        idx = len(segments) + 1
        name = f'segment-{idx:06d}-{start:016x}.bin'
        (segdir / name).write_bytes(data)
        segments.append({'start': start, 'end': start + len(data), 'data': data, 'source': source, 'top_index': top_index, 'name': name})
        if source == 'FULL':
            full_read_bytes += len(data)
        else:
            partial_prefix_bytes += len(data)

    sys.setrecursionlimit(max(sys.getrecursionlimit(), 10000))

    def recover_range(start: int, size: int, top_index: int, depth: int = 0):
        nonlocal attempts, attempted_bytes, full_range_count, partial_range_count
        nonlocal failed_range_count, zero_range_count, timeout_range_count, suspicious_subpage_count
        if size <= 0 or not budget_ok():
            return
        attempts += 1
        attempted_bytes += size
        timeout = 20 if size <= 1024 * 1024 else 45
        result = read_mem_once(a.adb, a.phone, pid, start, size, timeout=timeout)
        payload = result['payload']
        trusted = result['trusted_prefix_bytes']
        status = result['status']
        if status == 'FULL':
            full_range_count += 1
            record_segment(start, payload[:size], 'FULL', top_index)
        elif status == 'PARTIAL':
            partial_range_count += 1
            if len(payload) < PAGE:
                suspicious_subpage_count += 1
            if trusted:
                record_segment(start, payload[:trusted], 'PARTIAL_PREFIX', top_index)
            remaining_start = start + trusted
            remaining_size = size - trusted
            if remaining_size > 0 and budget_ok():
                if remaining_size <= PAGE:
                    failed_range_count += 1
                else:
                    half = (remaining_size // 2 // PAGE) * PAGE
                    if half < PAGE:
                        half = PAGE
                    if half >= remaining_size:
                        half = remaining_size - PAGE
                    if half > 0:
                        recover_range(remaining_start, half, top_index, depth + 1)
                        recover_range(remaining_start + half, remaining_size - half, top_index, depth + 1)
                    else:
                        failed_range_count += 1
        elif status == 'ZERO':
            zero_range_count += 1
            if size > PAGE and budget_ok():
                half = (size // 2 // PAGE) * PAGE
                if half < PAGE:
                    half = PAGE
                if half < size:
                    recover_range(start, half, top_index, depth + 1)
                    recover_range(start + half, size - half, top_index, depth + 1)
                else:
                    failed_range_count += 1
            else:
                failed_range_count += 1
        elif status == 'TIMEOUT':
            timeout_range_count += 1
            failed_range_count += 1
        else:
            failed_range_count += 1
            if size > PAGE and budget_ok():
                half = (size // 2 // PAGE) * PAGE
                if half < PAGE:
                    half = PAGE
                if half < size:
                    recover_range(start, half, top_index, depth + 1)
                    recover_range(start + half, size - half, top_index, depth + 1)

        read_manifest.append({
            'top_chunk': top_index,
            'depth': depth,
            'requested_bytes': size,
            'returned_bytes': len(payload),
            'trusted_prefix_bytes': trusted,
            'read_status': status,
            'rc': result['rc'],
            'host_stderr_bytes': result['host_stderr_bytes'],
            'text_like_short': result['text_like_short'],
            'returned_sha256': sha_bytes(payload) if payload and len(payload) < PAGE else None,
        })

    for i, ch in enumerate(plan):
        if not budget_ok():
            break
        recover_range(ch['start'], ch['size'], i)

    trusted_intervals = [(s['start'], s['end']) for s in segments]
    unique_bytes = interval_union_bytes(trusted_intervals)
    failed_selected_bytes = max(0, selected_bytes - unique_bytes)
    coverage_percent = (100.0 * unique_bytes / selected_bytes) if selected_bytes else 0.0
    census_exhausted = selected_bytes > 0 and unique_bytes == selected_bytes and stop_reason == 'COMPLETE'

    # Merge contiguous successfully recovered bytes so DEX magic can cross a read boundary.
    runs = merge_segments(segments)
    magic_hits = 0
    cdex_hits = 0
    valid_hits = 0
    seen_sha = {}
    recovered_bytes = 0
    candidate_manifest = []

    for run_index, run in enumerate(runs, 1):
        data = run['data']
        for kind, off, _magic in magic_offsets(data):
            address = run['start'] + off
            if kind == 'CDEX':
                cdex_hits += 1
                continue
            magic_hits += 1
            hdr = validate_dex_header(data, off)
            if not hdr:
                continue
            valid_hits += 1
            file_size = hdr['file_size']
            if off + file_size > len(data):
                candidate_manifest.append({'run': run_index, 'kind': 'DEX', 'validated_header': True, 'full_image_available': False})
                continue
            if len(seen_sha) >= MAX_CANDIDATES or recovered_bytes >= MAX_RECOVERED:
                continue
            full = data[off:off + file_size]
            if not validate_dex_header(full, 0):
                continue
            h = sha_bytes(full)
            if h in seen_sha:
                continue
            if recovered_bytes + len(full) > MAX_RECOVERED:
                continue
            idx = len(seen_sha) + 1
            name = f'external-memory-dex-{idx:03d}.dex'
            (dexdir / name).write_bytes(full)
            recovered_bytes += len(full)
            seen_sha[h] = name
            candidate_manifest.append({
                'run': run_index, 'kind': 'DEX', 'validated_header': True,
                'full_image_available': True, 'recovered_dex': name,
                'sha256': h, 'size': len(full), 'source_address': hex(address),
            })

    full_pages = unique_bytes // PAGE
    selected_pages = math.ceil(selected_bytes / PAGE) if selected_bytes else 0
    failed_pages = max(0, selected_pages - full_pages)

    if unique_bytes == 0:
        external_access = 'DENIED_OR_UNSUPPORTED'
    elif census_exhausted:
        external_access = 'READABLE_FULL'
    else:
        external_access = 'READABLE_PARTIAL'

    private = {
        'schema': 'rokid.test21-r3.3.4.2.5.2.1.coverage-repair.private.v1',
        'root_id': root_id.strip(),
        'pid': pid,
        'process_maps_access': 'READABLE',
        'external_proc_mem_access': external_access,
        'readable_mapping_count': len(readable_rows),
        'readable_mapping_bytes': readable_bytes,
        'selected_chunk_count': len(plan),
        'selected_memory_bytes': selected_bytes,
        'attempted_memory_bytes': attempted_bytes,
        'unique_byte_range_read': unique_bytes,
        'full_read_bytes': full_read_bytes,
        'partial_read_bytes': partial_prefix_bytes,
        'failed_read_bytes': failed_selected_bytes,
        'memory_read_coverage_percent': coverage_percent,
        'memory_census_exhausted': census_exhausted,
        'full_page_count': full_pages,
        'failed_page_count': failed_pages,
        'full_range_count': full_range_count,
        'partial_range_count': partial_range_count,
        'failed_range_count': failed_range_count,
        'zero_range_count': zero_range_count,
        'timeout_range_count': timeout_range_count,
        'suspicious_subpage_count': suspicious_subpage_count,
        'read_attempt_count': attempts,
        'stop_reason': stop_reason,
        'qualification_search': qsearch,
        'qualification_ladder': qladder,
        'qualification_duplicate_short_output_max_count': qdup,
        'prior_short_read_characterization': prior,
        'dex_magic_hit_count': magic_hits,
        'cdex_magic_hit_count': cdex_hits,
        'dex_validated_count': valid_hits,
        'dex_recovered_unique_count': len(seen_sha),
        'dex_recovered_bytes': recovered_bytes,
        'read_manifest': read_manifest,
        'coverage_segments': [
            {'start': hex(s['start']), 'end': hex(s['end']), 'size': s['end'] - s['start'], 'source': s['source'], 'name': s['name']}
            for s in segments
        ],
        'candidate_manifest': candidate_manifest,
        'limits': {
            'page_size': PAGE,
            'top_chunk_size': a.top_chunk_size,
            'max_total_bytes': a.max_total_bytes,
            'max_attempts': a.max_attempts,
            'max_seconds': a.max_seconds,
            'max_dex_bytes': MAX_DEX,
            'max_recovered_bytes': MAX_RECOVERED,
            'max_candidates': MAX_CANDIDATES,
        },
    }
    (out / 'external-memory-coverage-private.json').write_text(json.dumps(private, indent=2, sort_keys=True) + '\n')

    prior_mode = prior.get('returned_size_mode_bytes', 'UNAVAILABLE') if prior.get('available') else 'UNAVAILABLE'
    prior_mode_count = prior.get('returned_size_mode_count', 0) if prior.get('available') else 0
    prior_dup = prior.get('duplicate_short_output_max_count', 0) if prior.get('available') else 0
    print('EXTERNAL_PROC_MEM_ACCESS=' + external_access)
    print('READABLE_MAPPING_COUNT=' + str(len(readable_rows)))
    print('SELECTED_MEMORY_CHUNK_COUNT=' + str(len(plan)))
    print('SELECTED_MEMORY_BYTES=' + str(selected_bytes))
    print('ATTEMPTED_MEMORY_BYTES=' + str(attempted_bytes))
    print('UNIQUE_BYTE_RANGE_READ=' + str(unique_bytes))
    print('FULL_READ_BYTES=' + str(full_read_bytes))
    print('PARTIAL_READ_BYTES=' + str(partial_prefix_bytes))
    print('FAILED_READ_BYTES=' + str(failed_selected_bytes))
    print('MEMORY_READ_COVERAGE_PERCENT=%.6f' % coverage_percent)
    print('MEMORY_CENSUS_EXHAUSTED=' + ('YES' if census_exhausted else 'NO'))
    print('FULL_PAGE_COUNT=' + str(full_pages))
    print('FAILED_PAGE_COUNT=' + str(failed_pages))
    print('FULL_RANGE_COUNT=' + str(full_range_count))
    print('PARTIAL_RANGE_COUNT=' + str(partial_range_count))
    print('FAILED_RANGE_COUNT=' + str(failed_range_count))
    print('SUSPICIOUS_SUBPAGE_COUNT=' + str(suspicious_subpage_count))
    print('READ_ATTEMPT_COUNT=' + str(attempts))
    print('READ_STOP_REASON=' + stop_reason)
    print('PRIOR_SHORT_READ_CHARACTERIZATION=' + ('AVAILABLE' if prior.get('available') else 'UNAVAILABLE'))
    print('PRIOR_RETURNED_SIZE_MODE_BYTES=' + str(prior_mode))
    print('PRIOR_RETURNED_SIZE_MODE_COUNT=' + str(prior_mode_count))
    print('PRIOR_DUPLICATE_SHORT_OUTPUT_MAX_COUNT=' + str(prior_dup))
    print('DEX_MAGIC_HIT_COUNT=' + str(magic_hits))
    print('CDEX_MAGIC_HIT_COUNT=' + str(cdex_hits))
    print('DEX_VALIDATED_COUNT=' + str(valid_hits))
    print('DEX_RECOVERED_UNIQUE_COUNT=' + str(len(seen_sha)))
    print('FRIDA_SERVER_START=NONE')
    print('FRIDA_PROCESS_ATTACH=NONE')
    print('INJECTED_AGENT_LOAD=NONE')
    print('PTRACE_ATTACH=NONE')
    print('PROCESS_SIGNAL=NONE')
    print('PAYLOAD_EXECUTION=NONE')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
