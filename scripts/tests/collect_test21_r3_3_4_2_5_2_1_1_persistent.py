#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import select
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
DEFAULT_GLOBAL_SECONDS = 600
DEFAULT_QUAL_SECONDS = 60
DEFAULT_QUAL_MAPPINGS = 8
PROGRESS_INTERVAL = 10
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
    if not row['perms'].startswith('r'):
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
        if bucket(row) >= 99:
            continue
        pos = row['start']
        while pos < row['end'] and used < max_total:
            n = min(chunk_size, row['end'] - pos, max_total - used)
            # proc maps are page aligned. Only select complete pages so exact coverage
            # accounting and page fallback remain unambiguous.
            n = (n // PAGE) * PAGE
            if n < PAGE:
                break
            out.append({'start': pos, 'size': n, 'bucket': bucket(row), 'path': row['path'], 'perms': row['perms']})
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


def merge_segments(segments):
    if not segments:
        return []
    rows = sorted(segments, key=lambda x: x['start'])
    out = []
    for seg in rows:
        start = seg['start']
        data = seg['data']
        if not data:
            continue
        if not out:
            out.append({'start': start, 'data': bytearray(data)})
            continue
        prev = out[-1]
        prev_end = prev['start'] + len(prev['data'])
        if start == prev_end:
            prev['data'].extend(data)
        elif start > prev_end:
            out.append({'start': start, 'data': bytearray(data)})
        else:
            overlap = prev_end - start
            if overlap < len(data):
                prev['data'].extend(data[overlap:])
    return [{'start': x['start'], 'data': bytes(x['data'])} for x in out]


def interval_union_bytes(intervals):
    rows = sorted((s, e) for s, e in intervals if e > s)
    if not rows:
        return 0
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


WORKER_SCRIPT = r'''umask 077
BASE="/data/local/tmp/rokid-test21-r3252111-$$"
mkdir -p "$BASE" >/dev/null 2>&1 || exit 97
cleanup_worker() { rm -rf "$BASE" >/dev/null 2>&1; }
trap cleanup_worker 0 1 2 15
emit_file() {
  req="$1"; rc="$2"; payload="$3"; errfile="$4"
  n=$(wc -c < "$payload" 2>/dev/null | tr -d ' ')
  en=$(wc -c < "$errfile" 2>/dev/null | tr -d ' ')
  [ -n "$n" ] || n=0
  [ -n "$en" ] || en=0
  printf 'FRAME|%s|%s|%s|%s\n' "$req" "$rc" "$n" "$en"
  cat "$payload" 2>/dev/null
  printf '\nEND|%s\n' "$req"
  rm -f "$payload" "$errfile" >/dev/null 2>&1
}
printf 'WORKER_READY\n'
# __WORKER_BOOTSTRAP_END__
while IFS='|' read -r op req a b c; do
  out="$BASE/out-$req"
  err="$BASE/err-$req"
  : > "$out"; : > "$err"
  case "$op" in
    ID)
      id > "$out" 2> "$err"; rc=$?; emit_file "$req" "$rc" "$out" "$err" ;;
    MAPS)
      case "$a" in *[!0-9]*|'') rc=96 ;; *) cat "/proc/$a/maps" > "$out" 2> "$err"; rc=$? ;; esac
      emit_file "$req" "$rc" "$out" "$err" ;;
    READ)
      case "$a:$b:$c" in *[!0-9:]*|'') rc=96 ;; *)
        dd if="/proc/$a/mem" of="$out" bs=4096 skip="$b" count="$c" status=none 2> "$err"; rc=$? ;;
      esac
      emit_file "$req" "$rc" "$out" "$err" ;;
    QUIT)
      cleanup_worker
      trap - 0 1 2 15
      printf 'BYE|%s\n' "$req"
      exit 0 ;;
    *)
      printf 'FRAME|%s|95|0|0\n\nEND|%s\n' "$req" "$req" ;;
  esac
done
'''


class FramedReader:
    def __init__(self, pipe):
        self.pipe = pipe
        self.fd = pipe.fileno()
        self.buf = bytearray()

    def _fill(self, deadline: float):
        remain = deadline - time.monotonic()
        if remain <= 0:
            raise TimeoutError('worker read timeout')
        ready, _, _ = select.select([self.fd], [], [], remain)
        if not ready:
            raise TimeoutError('worker read timeout')
        chunk = os.read(self.fd, 65536)
        if not chunk:
            raise EOFError('worker stdout closed')
        self.buf.extend(chunk)

    def line(self, timeout: float) -> bytes:
        deadline = time.monotonic() + max(0.1, timeout)
        while True:
            i = self.buf.find(b'\n')
            if i >= 0:
                out = bytes(self.buf[:i])
                del self.buf[:i + 1]
                return out
            self._fill(deadline)

    def exact(self, n: int, timeout: float) -> bytes:
        deadline = time.monotonic() + max(0.1, timeout)
        while len(self.buf) < n:
            self._fill(deadline)
        out = bytes(self.buf[:n])
        del self.buf[:n]
        return out


class RootWorker:
    def __init__(self, adb: str, phone: str, startup_timeout: float = 12):
        self.proc = subprocess.Popen(
            [adb, '-s', phone, 'exec-out', 'su', '-c', 'sh'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0,
        )
        assert self.proc.stdin is not None and self.proc.stdout is not None
        self.reader = FramedReader(self.proc.stdout)
        self.seq = 0
        self.closed = False
        self.cleanup_reported = False
        self.proc.stdin.write(WORKER_SCRIPT.encode('utf-8'))
        self.proc.stdin.flush()
        ready = self.reader.line(startup_timeout).decode('ascii', 'replace')
        if ready != 'WORKER_READY':
            self.close(force=True)
            raise RuntimeError('persistent root worker did not become ready: ' + ready)

    def request(self, op: str, args: list[int | str], timeout: float):
        if self.closed:
            raise RuntimeError('worker closed')
        self.seq += 1
        req = str(self.seq)
        fields = [op, req] + [str(x) for x in args]
        line = '|'.join(fields) + '\n'
        assert self.proc.stdin is not None
        self.proc.stdin.write(line.encode('ascii'))
        self.proc.stdin.flush()
        header = self.reader.line(timeout).decode('ascii', 'replace')
        parts = header.split('|')
        if len(parts) != 5 or parts[0] != 'FRAME' or parts[1] != req:
            raise RuntimeError('invalid worker frame header')
        rc, n, errn = int(parts[2]), int(parts[3]), int(parts[4])
        payload = self.reader.exact(n, timeout)
        sep = self.reader.exact(1, timeout)
        if sep != b'\n':
            raise RuntimeError('invalid worker frame separator')
        trailer = self.reader.line(timeout).decode('ascii', 'replace')
        if trailer != f'END|{req}':
            raise RuntimeError('invalid worker frame trailer')
        return {'rc': rc, 'payload': payload, 'remote_stderr_bytes': errn}

    def close(self, force: bool = False):
        if self.closed:
            return
        self.closed = True
        try:
            if not force and self.proc.poll() is None and self.proc.stdin is not None:
                self.seq += 1
                req = str(self.seq)
                self.proc.stdin.write(f'QUIT|{req}\n'.encode('ascii'))
                self.proc.stdin.flush()
                line = self.reader.line(3).decode('ascii', 'replace')
                self.cleanup_reported = line == f'BYE|{req}'
        except Exception:
            pass
        try:
            if self.proc.poll() is None:
                self.proc.terminate()
                self.proc.wait(timeout=2)
        except Exception:
            try:
                self.proc.kill()
            except Exception:
                pass
        try:
            if self.proc.stdin is not None:
                self.proc.stdin.close()
        except Exception:
            pass


def read_mem_worker(worker: RootWorker, pid: str, address: int, size: int, timeout: float):
    if address % PAGE != 0 or size % PAGE != 0 or size <= 0:
        raise ValueError('worker memory reads must be positive page-aligned ranges')
    started = time.monotonic()
    try:
        frame = worker.request('READ', [pid, address // PAGE, size // PAGE], timeout)
    except TimeoutError:
        return {
            'status': 'TIMEOUT', 'requested_bytes': size, 'payload': b'', 'trusted_prefix_bytes': 0,
            'rc': None, 'remote_stderr_bytes': 0, 'duration_ms': int((time.monotonic() - started) * 1000),
            'text_like_short': False, 'worker_usable': False,
        }
    payload = frame['payload'][:size]
    if len(payload) >= size and frame['rc'] == 0:
        status = 'FULL'
    elif payload:
        status = 'PARTIAL'
    else:
        status = 'FAILED' if frame['rc'] != 0 else 'ZERO'
    return {
        'status': status,
        'requested_bytes': size,
        'payload': payload,
        'trusted_prefix_bytes': trusted_prefix_length(len(payload), size),
        'rc': frame['rc'],
        'remote_stderr_bytes': frame['remote_stderr_bytes'],
        'duration_ms': int((time.monotonic() - started) * 1000),
        'text_like_short': looks_text_like_short(payload),
        'worker_usable': True,
    }


def emit_progress(**values):
    values = {'ELAPSED_SECONDS': int(values.pop('elapsed_seconds', 0)), **values}
    print('PROGRESS ' + ' '.join(f'{k}={v}' for k, v in values.items()), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--phone', required=True)
    ap.add_argument('--output', required=True)
    ap.add_argument('--adb', default='adb')
    ap.add_argument('--prior-evidence')
    ap.add_argument('--top-chunk-size', type=int, default=DEFAULT_TOP_CHUNK)
    ap.add_argument('--max-total-bytes', type=int, default=DEFAULT_TOTAL)
    ap.add_argument('--max-attempts', type=int, default=DEFAULT_MAX_ATTEMPTS)
    ap.add_argument('--global-max-seconds', type=int, default=DEFAULT_GLOBAL_SECONDS)
    ap.add_argument('--qualification-max-seconds', type=int, default=DEFAULT_QUAL_SECONDS)
    ap.add_argument('--qualification-max-mappings', type=int, default=DEFAULT_QUAL_MAPPINGS)
    a = ap.parse_args()

    out = Path(a.output)
    out.mkdir(parents=True, exist_ok=True)
    segdir = out / 'coverage-segments'
    dexdir = out / 'recovered-dex'
    segdir.mkdir(exist_ok=True)
    dexdir.mkdir(exist_ok=True)

    global_start = time.monotonic()
    global_deadline = global_start + a.global_max_seconds
    prior = characterize_prior(a.prior_evidence)
    worker = None
    worker_cleanup_reported = False
    worker_usable = True
    root_id = ''
    maps = ''
    pid = ''
    qsearch = []
    qladder = []
    qualification_result = 'NOT_STARTED'
    qualification_elapsed = 0
    qualification_read_count = 0
    qualification_trusted_bytes = 0

    try:
        state = run_text([a.adb, '-s', a.phone, 'get-state'])
        if state[0] != 0 or 'device' not in state[1]:
            print('ERROR: device offline', file=sys.stderr)
            return 2

        rc, pidtxt, _ = run_text([a.adb, '-s', a.phone, 'shell', 'pidof', PKG])
        pid = pidtxt.strip().split()[0] if pidtxt.strip() else ''
        if not pid or not pid.isdigit():
            print('HI_ROKID_PROCESS_VISIBLE=NO')
            print('ERROR: Hi Rokid must already be running; collector will not launch it')
            return 4
        print('HI_ROKID_PROCESS_VISIBLE=YES')

        print('PHASE=PERSISTENT_ROOT_SESSION_START', flush=True)
        worker = RootWorker(a.adb, a.phone)
        print('PERSISTENT_ROOT_SESSION=READY', flush=True)

        frame = worker.request('ID', [], min(10, max(1, global_deadline - time.monotonic())))
        root_id = frame['payload'].decode('utf-8', 'replace').replace('\r', '').strip()
        if frame['rc'] != 0 or 'uid=0' not in root_id:
            print('ROOT_PROBE=UNAVAILABLE')
            return 3
        print('ROOT_PROBE=AVAILABLE')

        frame = worker.request('MAPS', [pid], min(12, max(1, global_deadline - time.monotonic())))
        maps = frame['payload'].decode('utf-8', 'replace').replace('\r', '')
        if frame['rc'] != 0 or not maps.strip():
            print('ROOT_PROCESS_MAPS_ACCESS=UNAVAILABLE')
            return 5
        print('ROOT_PROCESS_MAPS_ACCESS=READABLE')
        (out / 'process-maps.txt').write_text(maps)

        rows = parse_maps(maps)
        readable_rows = [r for r in rows if r['perms'].startswith('r')]
        readable_bytes = sum(r['size'] for r in readable_rows)
        plan = plan_chunks(rows, a.top_chunk_size, a.max_total_bytes)
        selected_bytes = sum(x['size'] for x in plan)

        # Qualification is a strict bounded precondition to the expensive census.
        print('PHASE=QUALIFICATION', flush=True)
        qual_start = time.monotonic()
        qual_deadline = min(global_deadline, qual_start + a.qualification_max_seconds)
        candidates = [r for r in sorted(readable_rows, key=lambda r: (bucket(r), -r['size'], r['start'])) if r['size'] >= PAGE]
        qrow = None
        for idx, row in enumerate(candidates[:a.qualification_max_mappings], 1):
            now = time.monotonic()
            if now >= qual_deadline:
                qualification_result = 'TIME_BUDGET_EXHAUSTED'
                break
            emit_progress(PHASE='QUALIFICATION', QUALIFICATION_MAPPING=f'{idx}/{min(len(candidates), a.qualification_max_mappings)}', QUALIFICATION_SIZE=PAGE, elapsed_seconds=now-global_start)
            result = read_mem_worker(worker, pid, row['start'], PAGE, min(10, max(1, qual_deadline - now)))
            qualification_read_count += 1
            trusted = result['trusted_prefix_bytes']
            qualification_trusted_bytes += trusted
            qsearch.append({
                'mapping_size': row['size'], 'bucket': bucket(row), 'requested_bytes': PAGE,
                'returned_bytes': len(result['payload']), 'trusted_prefix_bytes': trusted,
                'status': result['status'], 'rc': result['rc'], 'remote_stderr_bytes': result['remote_stderr_bytes'],
                'text_like_short': result['text_like_short'],
                'short_output_sha256': sha_bytes(result['payload']) if result['payload'] and len(result['payload']) < PAGE else None,
            })
            print(f'QUALIFICATION_MAPPING_RESULT={idx} REQUESTED_BYTES={PAGE} RETURNED_BYTES={len(result["payload"])} TRUSTED_BYTES={trusted} STATUS={result["status"]}', flush=True)
            if not result['worker_usable']:
                worker_usable = False
                qualification_result = 'WORKER_TIMEOUT'
                break
            if result['status'] == 'FULL':
                qrow = row
                qualification_result = 'FULL_PAGE_FOUND'
                break
        if qualification_result == 'NOT_STARTED':
            qualification_result = 'NO_FULL_PAGE'

        if qrow is not None and worker_usable:
            for size in QUAL_SIZES:
                now = time.monotonic()
                if now >= qual_deadline:
                    qualification_result = 'LADDER_TIME_BUDGET_EXHAUSTED'
                    break
                n = min(size, qrow['size'])
                n = (n // PAGE) * PAGE
                if n < PAGE:
                    continue
                emit_progress(PHASE='QUALIFICATION_LADDER', QUALIFICATION_SIZE=n, elapsed_seconds=now-global_start)
                result = read_mem_worker(worker, pid, qrow['start'], n, min(12, max(1, qual_deadline - now)))
                qualification_read_count += 1
                qualification_trusted_bytes += result['trusted_prefix_bytes']
                qladder.append({
                    'requested_bytes': n, 'returned_bytes': len(result['payload']),
                    'trusted_prefix_bytes': result['trusted_prefix_bytes'], 'status': result['status'],
                    'rc': result['rc'], 'remote_stderr_bytes': result['remote_stderr_bytes'],
                    'text_like_short': result['text_like_short'],
                    'short_output_sha256': sha_bytes(result['payload']) if result['payload'] and len(result['payload']) < PAGE else None,
                })
                print(f'QUALIFICATION_LADDER_RESULT REQUESTED_BYTES={n} RETURNED_BYTES={len(result["payload"])} TRUSTED_BYTES={result["trusted_prefix_bytes"]} STATUS={result["status"]}', flush=True)
                if not result['worker_usable']:
                    worker_usable = False
                    qualification_result = 'WORKER_TIMEOUT'
                    break
                if n >= qrow['size']:
                    break

        qualification_elapsed = int(time.monotonic() - qual_start)
        print('QUALIFICATION_RESULT=' + qualification_result)
        print('QUALIFICATION_ELAPSED_SECONDS=' + str(qualification_elapsed))
        print('QUALIFICATION_READ_COUNT=' + str(qualification_read_count))

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
        last_progress = time.monotonic()

        def budget_ok():
            nonlocal stop_reason
            if not worker_usable:
                stop_reason = 'WORKER_UNUSABLE'
                return False
            if attempts >= a.max_attempts:
                stop_reason = 'MAX_ATTEMPTS'
                return False
            if time.monotonic() >= global_deadline:
                stop_reason = 'GLOBAL_MAX_SECONDS'
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

        def maybe_progress(top_index: int, top_count: int, force: bool = False):
            nonlocal last_progress
            now = time.monotonic()
            if force or now - last_progress >= PROGRESS_INTERVAL:
                unique = interval_union_bytes((s['start'], s['end']) for s in segments)
                cov = (100.0 * unique / selected_bytes) if selected_bytes else 0.0
                emit_progress(
                    PHASE='CENSUS', TOP_LEVEL_RANGE=f'{top_index}/{top_count}', READ_ATTEMPTS=attempts,
                    TRUSTED_UNIQUE_BYTES=unique, COVERAGE_PERCENT=f'{cov:.6f}', elapsed_seconds=now-global_start,
                )
                last_progress = now

        sys.setrecursionlimit(max(sys.getrecursionlimit(), 10000))

        def recover_range(start: int, size: int, top_index: int, top_count: int, depth: int = 0):
            nonlocal attempts, attempted_bytes, full_range_count, partial_range_count
            nonlocal failed_range_count, zero_range_count, timeout_range_count, suspicious_subpage_count, worker_usable, stop_reason
            if size <= 0 or not budget_ok():
                return
            attempts += 1
            attempted_bytes += size
            remaining_global = max(1, global_deadline - time.monotonic())
            timeout = min(15, remaining_global)
            result = read_mem_worker(worker, pid, start, size, timeout=timeout)
            payload = result['payload']
            trusted = result['trusted_prefix_bytes']
            status = result['status']
            if not result['worker_usable']:
                worker_usable = False
                timeout_range_count += 1
                failed_range_count += 1
                stop_reason = 'WORKER_READ_TIMEOUT'
            elif status == 'FULL':
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
                    if size == PAGE:
                        # This is already the page-granularity retry. A sub-page result
                        # receives zero coverage credit and is final for this page.
                        failed_range_count += 1
                    elif remaining_size == PAGE:
                        # Retry the unread tail once at exact page granularity.
                        recover_range(remaining_start, PAGE, top_index, top_count, depth + 1)
                    elif remaining_size > PAGE:
                        half = (remaining_size // 2 // PAGE) * PAGE
                        half = max(PAGE, half)
                        if half >= remaining_size:
                            half = remaining_size - PAGE
                        recover_range(remaining_start, half, top_index, top_count, depth + 1)
                        recover_range(remaining_start + half, remaining_size - half, top_index, top_count, depth + 1)
                    else:
                        failed_range_count += 1
            elif status == 'ZERO':
                zero_range_count += 1
                if size > PAGE and budget_ok():
                    half = max(PAGE, (size // 2 // PAGE) * PAGE)
                    if half >= size:
                        half = size - PAGE
                    recover_range(start, half, top_index, top_count, depth + 1)
                    recover_range(start + half, size - half, top_index, top_count, depth + 1)
                else:
                    failed_range_count += 1
            elif status == 'TIMEOUT':
                timeout_range_count += 1
                failed_range_count += 1
                worker_usable = False
                stop_reason = 'WORKER_READ_TIMEOUT'
            else:
                failed_range_count += 1
                if size > PAGE and budget_ok():
                    half = max(PAGE, (size // 2 // PAGE) * PAGE)
                    if half >= size:
                        half = size - PAGE
                    recover_range(start, half, top_index, top_count, depth + 1)
                    recover_range(start + half, size - half, top_index, top_count, depth + 1)

            read_manifest.append({
                'top_chunk': top_index, 'depth': depth, 'requested_bytes': size,
                'returned_bytes': len(payload), 'trusted_prefix_bytes': trusted,
                'read_status': status, 'rc': result['rc'],
                'remote_stderr_bytes': result['remote_stderr_bytes'],
                'text_like_short': result['text_like_short'],
                'returned_sha256': sha_bytes(payload) if payload and len(payload) < PAGE else None,
            })
            maybe_progress(top_index + 1, len(plan))

        if qrow is None or qualification_result in ('TIME_BUDGET_EXHAUSTED', 'NO_FULL_PAGE', 'WORKER_TIMEOUT'):
            stop_reason = 'QUALIFICATION_NOT_PASSED'
            print('PHASE=CENSUS_SKIPPED QUALIFICATION_NOT_PASSED=YES', flush=True)
        elif time.monotonic() >= global_deadline:
            stop_reason = 'GLOBAL_MAX_SECONDS'
        else:
            print('PHASE=CENSUS', flush=True)
            for i, ch in enumerate(plan):
                if not budget_ok():
                    break
                maybe_progress(i + 1, len(plan), force=True)
                recover_range(ch['start'], ch['size'], i, len(plan))
                maybe_progress(i + 1, len(plan), force=True)

        trusted_intervals = [(s['start'], s['end']) for s in segments]
        unique_bytes = interval_union_bytes(trusted_intervals)
        failed_selected_bytes = max(0, selected_bytes - unique_bytes)
        coverage_percent = (100.0 * unique_bytes / selected_bytes) if selected_bytes else 0.0
        census_exhausted = selected_bytes > 0 and unique_bytes == selected_bytes and stop_reason == 'COMPLETE'

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
                if h in seen_sha or recovered_bytes + len(full) > MAX_RECOVERED:
                    continue
                idx = len(seen_sha) + 1
                name = f'external-memory-dex-{idx:03d}.dex'
                (dexdir / name).write_bytes(full)
                recovered_bytes += len(full)
                seen_sha[h] = name
                candidate_manifest.append({'run': run_index, 'kind': 'DEX', 'validated_header': True, 'full_image_available': True, 'recovered_dex': name, 'sha256': h, 'size': len(full)})

        full_pages = unique_bytes // PAGE
        selected_pages = selected_bytes // PAGE if selected_bytes else 0
        failed_pages = max(0, selected_pages - full_pages)
        qual_nonzero = sum(int(x.get('returned_bytes') or 0) for x in qsearch + qladder)
        if unique_bytes == 0 and qual_nonzero == 0:
            external_access = 'DENIED_OR_UNSUPPORTED'
        elif census_exhausted:
            external_access = 'READABLE_FULL'
        else:
            external_access = 'READABLE_PARTIAL'

        global_elapsed = int(time.monotonic() - global_start)
        private = {
            'schema': 'rokid.test21-r3.3.4.2.5.2.1.1.persistent-root.private.v1',
            'root_id': root_id,
            'pid': pid,
            'process_maps_access': 'READABLE',
            'external_proc_mem_access': external_access,
            'persistent_root_session': True,
            'persistent_root_session_count': 1,
            'root_worker_start_count': 1,
            'worker_cleanup_reported': False,
            'device_transient_temp_files': True,
            'qualification_result': qualification_result,
            'qualification_elapsed_seconds': qualification_elapsed,
            'qualification_read_count': qualification_read_count,
            'qualification_trusted_bytes': qualification_trusted_bytes,
            'qualification_search': qsearch,
            'qualification_ladder': qladder,
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
            'global_elapsed_seconds': global_elapsed,
            'prior_short_read_characterization': prior,
            'dex_magic_hit_count': magic_hits,
            'cdex_magic_hit_count': cdex_hits,
            'dex_validated_count': valid_hits,
            'dex_recovered_unique_count': len(seen_sha),
            'dex_recovered_bytes': recovered_bytes,
            'read_manifest': read_manifest,
            'coverage_segments': [
                {'size': s['end'] - s['start'], 'source': s['source'], 'name': s['name']}
                for s in segments
            ],
            'candidate_manifest': candidate_manifest,
            'limits': {
                'page_size': PAGE, 'top_chunk_size': a.top_chunk_size, 'max_total_bytes': a.max_total_bytes,
                'max_attempts': a.max_attempts, 'global_max_seconds': a.global_max_seconds,
                'qualification_max_seconds': a.qualification_max_seconds,
                'qualification_max_mappings': a.qualification_max_mappings,
                'max_dex_bytes': MAX_DEX, 'max_recovered_bytes': MAX_RECOVERED, 'max_candidates': MAX_CANDIDATES,
            },
        }
        (out / 'external-memory-persistent-private.json').write_text(json.dumps(private, indent=2, sort_keys=True) + '\n')

        prior_mode = prior.get('returned_size_mode_bytes', 'UNAVAILABLE') if prior.get('available') else 'UNAVAILABLE'
        prior_mode_count = prior.get('returned_size_mode_count', 0) if prior.get('available') else 0
        prior_dup = prior.get('duplicate_short_output_max_count', 0) if prior.get('available') else 0
        print('PERSISTENT_ROOT_SESSION=YES')
        print('PERSISTENT_ROOT_SESSION_COUNT=1')
        print('DEVICE_TRANSIENT_TEMP_FILES=YES')
        print('QUALIFICATION_RESULT=' + qualification_result)
        print('QUALIFICATION_ELAPSED_SECONDS=' + str(qualification_elapsed))
        print('GLOBAL_ELAPSED_SECONDS=' + str(global_elapsed))
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

    except KeyboardInterrupt:
        print('ERROR: interrupted by operator', file=sys.stderr)
        return 130
    except (TimeoutError, EOFError, RuntimeError) as exc:
        print('ERROR: persistent root worker failure: ' + str(exc), file=sys.stderr)
        return 6
    finally:
        if worker is not None:
            worker.close(force=not worker_usable)
            worker_cleanup_reported = worker.cleanup_reported
            # If a completed private result exists, update only its cleanup boolean.
            p = out / 'external-memory-persistent-private.json'
            if p.is_file():
                try:
                    d = json.loads(p.read_text())
                    d['worker_cleanup_reported'] = bool(worker_cleanup_reported)
                    p.write_text(json.dumps(d, indent=2, sort_keys=True) + '\n')
                except Exception:
                    pass
            print('ROOT_WORKER_TEMP_CLEANUP_REPORTED=' + ('YES' if worker_cleanup_reported else 'NO'), flush=True)


if __name__ == '__main__':
    raise SystemExit(main())
