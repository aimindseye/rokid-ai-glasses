#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, subprocess, time
from pathlib import Path

def adb(adb_bin, phone, *args, timeout=8):
    try:
        p = subprocess.run([adb_bin, '-s', phone, *args], text=True,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           timeout=timeout)
        return p.returncode, p.stdout
    except Exception as exc:
        return 125, f"collector_exception={type(exc).__name__}:{exc}\n"

def pidof(adb_bin, phone, pkg):
    rc, out = adb(adb_bin, phone, 'shell', 'pidof', pkg, timeout=4)
    out = out.replace('\r', '').strip()
    return out if rc == 0 else ''

def write_cmd(path, adb_bin, phone, *args):
    rc, out = adb(adb_bin, phone, *args, timeout=12)
    path.write_text(f"RC={rc}\nCOMMAND={' '.join(args)}\n{out}", encoding='utf-8')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--adb', required=True)
    ap.add_argument('--phone', required=True)
    ap.add_argument('--hi-package', required=True)
    ap.add_argument('--custom-package', required=True)
    ap.add_argument('--output', required=True)
    ap.add_argument('--duration-seconds', type=float, default=30)
    ap.add_argument('--poll-seconds', type=float, default=.20)
    args = ap.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    timeline = out / 'timeline-private.jsonl'
    started = time.monotonic()
    respawn = False
    first_ms = None
    with timeline.open('w', encoding='utf-8') as fh:
        while True:
            elapsed = (time.monotonic() - started) * 1000
            hi = pidof(args.adb, args.phone, args.hi_package)
            custom = pidof(args.adb, args.phone, args.custom_package)
            fh.write(json.dumps({
                'schema': 'rokid.test21-r3-1.timeline.v1',
                'elapsed_ms': round(elapsed, 1),
                'hi_process_visible': bool(hi),
                'custom_process_visible': bool(custom),
            }, sort_keys=True) + '\n')
            fh.flush()
            if hi and not respawn:
                respawn = True
                first_ms = round(elapsed, 1)
                write_cmd(out/'respawn-hi-services-private.txt', args.adb, args.phone,
                          'shell', 'dumpsys', 'activity', 'services', args.hi_package)
                write_cmd(out/'respawn-custom-services-private.txt', args.adb, args.phone,
                          'shell', 'dumpsys', 'activity', 'services', args.custom_package)
                write_cmd(out/'respawn-processes-private.txt', args.adb, args.phone,
                          'shell', 'dumpsys', 'activity', 'processes')
                write_cmd(out/'respawn-ps-private.txt', args.adb, args.phone,
                          'shell', 'ps', '-A', '-o', 'USER,PID,PPID,NAME,ARGS')
            if elapsed >= args.duration_seconds * 1000:
                break
            time.sleep(max(args.poll_seconds, .05))
    (out/'collector-result.txt').write_text(
        'SCHEMA=rokid.test21-r3-1.collector-result.v1\n'
        f'RESPAWN_OBSERVED={"YES" if respawn else "NO"}\n'
        f'FIRST_RESPAWN_ELAPSED_MS={first_ms if first_ms is not None else "NONE"}\n'
        f'OBSERVATION_SECONDS={args.duration_seconds}\n', encoding='utf-8')
    print(f'RESPAWN_OBSERVED={"YES" if respawn else "NO"}')
    print(f'FIRST_RESPAWN_ELAPSED_MS={first_ms if first_ms is not None else "NONE"}')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
