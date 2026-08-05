#!/usr/bin/env python3
import argparse
from pathlib import Path


def classify(settings_value: str, cmd_status: str) -> str:
    s = (settings_value or '').strip().lower()
    if s == '0':
        return 'DISABLED'
    if s == '1':
        return 'ENABLED'

    c = (cmd_status or '').strip().lower()
    enabled_markers = (
        'wifi is enabled',
        'wifi enabled',
        'wifi state: enabled',
        'wifi_state_enabled',
    )
    disabled_markers = (
        'wifi is disabled',
        'wifi disabled',
        'wifi state: disabled',
        'wifi_state_disabled',
    )
    if any(m in c for m in disabled_markers):
        return 'DISABLED'
    if any(m in c for m in enabled_markers):
        return 'ENABLED'
    return 'UNKNOWN'


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--settings-value', default='')
    ap.add_argument('--cmd-status-file')
    args = ap.parse_args()
    cmd_status = ''
    if args.cmd_status_file:
        p = Path(args.cmd_status_file)
        if p.is_file():
            cmd_status = p.read_text(errors='replace')
    print(classify(args.settings_value, cmd_status))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
