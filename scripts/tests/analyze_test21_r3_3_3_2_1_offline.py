#!/usr/bin/env python3
import argparse
import csv
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

HI_PACKAGE = 'com.rokid.sprite.global.aiapp'
EXPECTED_NATIVE_HOSTS = {
    'www.baidu.com',
    'ai-cloud-global.rokid.com',
    'device-account-prod.rokid.com',
    'rcs-internal.rokid.com',
}
REQ_COLS = [
    'IPProto','SrcIP','SrcPort','DstIp','DstPort','UID','App','PackageName',
    'Proto','Status','Info','BytesSent','BytesRcvd','PktsSent','PktsRcvd',
    'FirstSeen','LastSeen'
]
CALIBRATION_TOLERANCE_MS = 5000


def norm_host(value):
    return (value or '').strip().lower().rstrip('.')


def iso_ms(value):
    return int(datetime.fromisoformat(value).timestamp() * 1000)


def read_json(path):
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def read_jsonl(path):
    rows = []
    if path.is_file():
        for line in path.read_text(errors='replace').splitlines():
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    rows.append(obj)
            except Exception:
                pass
    return rows


def find_one(root, pattern, required=True):
    matches = [p for p in (root / 'raw').glob(pattern) if p.is_file() and p.stat().st_size > 0]
    if len(matches) == 1:
        return matches[0]
    if not matches and not required:
        return None
    raise ValueError(f'expected exactly one {pattern} under {root}/raw, found {len(matches)}')


def read_native_csv(path):
    with path.open('r', encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames or []
        if columns != REQ_COLS:
            raise ValueError('native CSV schema mismatch: ' + '|'.join(columns))
        source_rows = list(reader)

    hi_rows = []
    for row in source_rows:
        if row.get('PackageName') != HI_PACKAGE:
            continue
        host = norm_host(row.get('Info'))
        if not host:
            continue
        hi_rows.append({
            'app': row.get('App') or '',
            'package': row.get('PackageName') or '',
            'proto': (row.get('Proto') or '').upper(),
            'status': row.get('Status') or '',
            'host': host,
            'bytes_sent': int(row.get('BytesSent') or 0),
            'bytes_received': int(row.get('BytesRcvd') or 0),
            'packets_sent': int(row.get('PktsSent') or 0),
            'packets_received': int(row.get('PktsRcvd') or 0),
            'first_seen_epoch_ms': iso_ms(row['FirstSeen']),
            'last_seen_epoch_ms': iso_ms(row['LastSeen']),
        })
    if not hi_rows:
        raise ValueError('native CSV contains no Hi Rokid rows')
    hosts = {row['host'] for row in hi_rows}
    if hosts != EXPECTED_NATIVE_HOSTS:
        raise ValueError('native CSV ground-truth host set mismatch: ' + ','.join(sorted(hosts)))
    return source_rows, hi_rows


def run_tshark_fields(pcap, keylog, display_filter, fields):
    exe = shutil.which('tshark')
    if not exe:
        raise ValueError('tshark not found in PATH')
    cmd = [exe, '-r', str(pcap)]
    if keylog:
        cmd += ['-o', f'tls.keylog_file:{keylog}']
    cmd += [
        '-Y', display_filter,
        '-T', 'fields',
        '-E', 'separator=/t',
        '-E', 'occurrence=f',
    ]
    for field in fields:
        cmd += ['-e', field]
    proc = subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=90,
    )
    if proc.returncode != 0:
        msg = (proc.stderr or '').strip().replace('\n', ' ')
        raise ValueError('tshark failed: ' + msg[:500])
    rows = []
    malformed = 0
    for line in proc.stdout.splitlines():
        parts = line.split('\t')
        if len(parts) < len(fields):
            parts += [''] * (len(fields) - len(parts))
        if len(parts) != len(fields):
            malformed += 1
            continue
        rows.append(dict(zip(fields, parts)))
    return rows, malformed


def frame_ms(row):
    frame = int((row.get('frame.number') or '0').split(',')[0])
    epoch = float((row.get('frame.time_epoch') or '0').split(',')[0])
    return frame, int(epoch * 1000)


def scan_known_hosts(pcap, keylog, hosts):
    known = {norm_host(h) for h in hosts}
    markers = []
    malformed_total = 0

    scans = [
        (
            'DNS_QUERY',
            'dns.flags.response == 0 && dns.qry.name',
            ['frame.number', 'frame.time_epoch', 'dns.qry.name'],
            'dns.qry.name',
            None,
        ),
        (
            'TLS_CLIENT_HELLO',
            'tls.handshake.type == 1 && tls.handshake.extensions_server_name',
            ['frame.number', 'frame.time_epoch', 'tls.handshake.extensions_server_name'],
            'tls.handshake.extensions_server_name',
            None,
        ),
        (
            'HTTP_REQUEST',
            'http.request && http.host',
            ['frame.number', 'frame.time_epoch', 'http.request.method', 'http.host'],
            'http.host',
            'http.request.method',
        ),
        (
            'HTTP2_REQUEST',
            'http2.headers.method && http2.headers.authority',
            ['frame.number', 'frame.time_epoch', 'http2.headers.method', 'http2.headers.authority'],
            'http2.headers.authority',
            'http2.headers.method',
        ),
    ]

    for marker_type, display_filter, fields, host_field, method_field in scans:
        rows, malformed = run_tshark_fields(pcap, keylog, display_filter, fields)
        malformed_total += malformed
        for row in rows:
            host = norm_host(row.get(host_field))
            if host not in known:
                continue
            try:
                frame, epoch_ms = frame_ms(row)
            except Exception:
                malformed_total += 1
                continue
            markers.append({
                'frame_number': frame,
                'epoch_ms': epoch_ms,
                'marker_type': marker_type,
                'host': host,
                'method': (row.get(method_field) or '').strip() if method_field else None,
            })

    dedup = {}
    for marker in markers:
        key = (
            marker['frame_number'], marker['epoch_ms'], marker['marker_type'],
            marker['host'], marker.get('method')
        )
        dedup[key] = marker
    return sorted(dedup.values(), key=lambda x: (x['epoch_ms'], x['frame_number'], x['marker_type'], x['host'])), malformed_total


def calibrate(native_rows, scan_rows):
    native_first = {}
    for row in native_rows:
        host = row['host']
        first = row['first_seen_epoch_ms']
        if host not in native_first or first < native_first[host]:
            native_first[host] = first

    scan_by_host = {}
    for row in scan_rows:
        scan_by_host.setdefault(row['host'], []).append(row)

    details = []
    matched = []
    for host in sorted(EXPECTED_NATIVE_HOSTS):
        native_ms = native_first.get(host)
        candidates = scan_by_host.get(host, [])
        if native_ms is None or not candidates:
            details.append({
                'host': host,
                'native_first_seen_epoch_ms': native_ms,
                'scanner_epoch_ms': None,
                'scanner_marker_type': None,
                'delta_ms': None,
                'within_tolerance': False,
            })
            continue
        best = min(candidates, key=lambda x: abs(x['epoch_ms'] - native_ms))
        delta = best['epoch_ms'] - native_ms
        ok = abs(delta) <= CALIBRATION_TOLERANCE_MS
        if ok:
            matched.append(host)
        details.append({
            'host': host,
            'native_first_seen_epoch_ms': native_ms,
            'scanner_epoch_ms': best['epoch_ms'],
            'scanner_marker_type': best['marker_type'],
            'delta_ms': delta,
            'within_tolerance': ok,
        })

    matched = sorted(set(matched))
    qualified = set(matched) == EXPECTED_NATIVE_HOSTS
    return details, matched, qualified


def read_r333_timeline(r333):
    raw = r333 / 'raw'
    markers = read_jsonl(raw / 'host-timeline-private.jsonl')
    marker_map = {
        x.get('name'): x.get('host_epoch_ms')
        for x in markers if x.get('kind') == 'host_marker'
    }
    collector = read_json(raw / 'collector-summary-private.json')
    event_map = collector.get('event_first_seen_host_epoch_ms', {})
    if not isinstance(event_map, dict):
        event_map = {}
    out = {
        'pcap_start': marker_map.get('pcapdroid_capture_start'),
        'hi_force_stop': marker_map.get('hi_force_stop_issued'),
        'hi_absence': marker_map.get('hi_absence_proven'),
        'button_prompt': marker_map.get('button2_now_prompt'),
        'button_done': marker_map.get('button2_operator_done'),
        'connection_attempt': event_map.get('connection_attempt_started'),
        'hi_respawn': collector.get('first_hi_respawn_host_epoch_ms'),
        'pcap_stop': marker_map.get('pcapdroid_capture_stop'),
    }
    for key in ('hi_force_stop', 'hi_absence', 'button_prompt', 'connection_attempt', 'hi_respawn'):
        if not isinstance(out.get(key), int):
            raise ValueError('r3.3.3 timeline missing ' + key)
    return out


def ordering(a, b, a_name='CONNECTION', b_name='RESPAWN'):
    if a is None or b is None:
        return 'UNRESOLVED_MISSING_TIMESTAMP'
    if a == b:
        return 'SAME_OBSERVATION_TIMESTAMP'
    return a_name + '_PRECEDES_' + b_name if a < b else b_name + '_PRECEDES_' + a_name


def marker_phase(epoch_ms, timeline):
    boundary = min(timeline['connection_attempt'], timeline['hi_respawn'])
    if epoch_ms < timeline['hi_force_stop']:
        return 'PRE_FORCE_STOP'
    if epoch_ms < timeline['button_prompt']:
        return 'FORCE_STOP_TO_BUTTON_PROMPT'
    if epoch_ms < boundary:
        return 'BUTTON_PROMPT_TO_CONNECTION_RESPAWN_BOUNDARY'
    if epoch_ms == boundary:
        return 'CONNECTION_RESPAWN_BOUNDARY_TIMESTAMP'
    return 'POST_CONNECTION_RESPAWN_BOUNDARY'


def classify_network(markers, timeline):
    after_force = [x for x in markers if x['epoch_ms'] >= timeline['hi_force_stop']]
    before_prompt = [x for x in after_force if x['epoch_ms'] < timeline['button_prompt']]
    boundary = min(timeline['connection_attempt'], timeline['hi_respawn'])
    before_boundary = [x for x in after_force if x['epoch_ms'] < boundary]
    prompt_to_boundary = [x for x in before_boundary if x['epoch_ms'] >= timeline['button_prompt']]
    at_boundary = [x for x in after_force if x['epoch_ms'] == boundary]
    after_boundary = [x for x in after_force if x['epoch_ms'] > boundary]
    first = after_force[0] if after_force else None

    if first is None:
        respawn_disposition = 'NO_KNOWN_ROKID_ENDPOINT_INITIATION_AFTER_FORCE_WITH_QUALIFIED_SCANNER'
    elif first['epoch_ms'] < timeline['hi_respawn']:
        respawn_disposition = 'KNOWN_ROKID_ENDPOINT_INITIATION_PRECEDES_RESPAWN'
    elif first['epoch_ms'] == timeline['hi_respawn']:
        respawn_disposition = 'KNOWN_ROKID_ENDPOINT_INITIATION_SAME_OBSERVATION_TIMESTAMP_AS_RESPAWN'
    else:
        respawn_disposition = 'RESPAWN_PRECEDES_KNOWN_ROKID_ENDPOINT_INITIATION'

    if before_prompt:
        server = 'KNOWN_ROKID_ENDPOINT_INITIATION_BEFORE_BUTTON_PROMPT_CORRELATION'
    elif prompt_to_boundary:
        server = 'KNOWN_ROKID_ENDPOINT_INITIATION_AFTER_BUTTON_PROMPT_BEFORE_CONNECTION_RESPAWN_BOUNDARY_CORRELATION'
    elif at_boundary:
        server = 'KNOWN_ROKID_ENDPOINT_INITIATION_AT_CONNECTION_RESPAWN_BOUNDARY'
    elif after_boundary:
        server = 'KNOWN_ROKID_ENDPOINT_INITIATION_ONLY_AFTER_CONNECTION_RESPAWN_BOUNDARY'
    else:
        server = 'NO_KNOWN_ROKID_ENDPOINT_INITIATION_AFTER_FORCE_OBSERVED_WITH_QUALIFIED_SCANNER'

    return {
        'after_force': after_force,
        'before_button_prompt': before_prompt,
        'before_boundary': before_boundary,
        'prompt_to_boundary': prompt_to_boundary,
        'at_boundary': at_boundary,
        'after_boundary': after_boundary,
        'first_after_force': first,
        'network_respawn_disposition': respawn_disposition,
        'server_dependency_interpretation': server,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--r333-evidence', required=True)
    parser.add_argument('--r3331-evidence', required=True)
    parser.add_argument('--native-csv', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()

    r333 = Path(args.r333_evidence)
    r3331 = Path(args.r3331_evidence)
    native_csv = Path(args.native_csv)
    output = Path(args.output)
    private = output / 'private'
    sanitized = output / 'sanitized'
    private.mkdir(parents=True, exist_ok=True)
    sanitized.mkdir(parents=True, exist_ok=True)

    try:
        if not native_csv.is_file() or native_csv.stat().st_size == 0:
            raise ValueError('native CSV missing/empty')

        source_rows, native_rows = read_native_csv(native_csv)
        known_hosts = sorted(EXPECTED_NATIVE_HOSTS)
        known_rokid_hosts = sorted(h for h in known_hosts if h.endswith('.rokid.com'))

        calibration_pcap = find_one(r3331, '*-private.pcap')
        calibration_keylog = find_one(r3331, '*-private.sslkeylog', required=False)
        calibration_scan, calibration_malformed = scan_known_hosts(
            calibration_pcap, calibration_keylog, known_hosts
        )
        calibration_details, matched_hosts, qualified = calibrate(native_rows, calibration_scan)

        calibration_record = {
            'expected_hosts': known_hosts,
            'matched_hosts': matched_hosts,
            'matched_count': len(matched_hosts),
            'expected_count': len(known_hosts),
            'disposition': 'QUALIFIED_4_OF_4' if qualified else 'NOT_QUALIFIED',
            'tolerance_ms': CALIBRATION_TOLERANCE_MS,
            'malformed_tshark_rows': calibration_malformed,
            'rows': calibration_details,
        }
        (sanitized / 'scanner-ground-truth-4-of-4-sanitized.json').write_text(
            json.dumps(calibration_record, indent=2, sort_keys=True) + '\n'
        )

        if not qualified:
            print('TEST21_R3_3_3_2_1_ANALYSIS=FAIL')
            print('SCANNER_GROUND_TRUTH_DISPOSITION=NOT_QUALIFIED')
            print(f'SCANNER_GROUND_TRUTH_MATCHED_HOSTS={len(matched_hosts)}/4')
            print('R333_NETWORK_CONCLUSION=WITHHELD')
            print('ERROR: ground-truth scanner did not recover all 4 native PCAPdroid hosts')
            return 1

        r333_pcap = find_one(r333, '*-private.pcap')
        r333_keylog = find_one(r333, '*-private.sslkeylog', required=False)
        r333_scan, r333_malformed = scan_known_hosts(r333_pcap, r333_keylog, known_hosts)
        timeline = read_r333_timeline(r333)

        rokid_markers = [x for x in r333_scan if x['host'] in known_rokid_hosts]
        network = classify_network(rokid_markers, timeline)
        for marker in rokid_markers:
            marker['phase'] = marker_phase(marker['epoch_ms'], timeline)

        safe_native = [
            {
                'app': x['app'], 'package': x['package'], 'proto': x['proto'],
                'status': x['status'], 'host': x['host'],
                'bytes_sent': x['bytes_sent'], 'bytes_received': x['bytes_received'],
                'packets_sent': x['packets_sent'], 'packets_received': x['packets_received'],
                'first_seen_epoch_ms': x['first_seen_epoch_ms'],
                'last_seen_epoch_ms': x['last_seen_epoch_ms'],
            }
            for x in native_rows
        ]
        (sanitized / 'native-csv-ground-truth-sanitized.jsonl').write_text(
            ''.join(json.dumps(x, sort_keys=True) + '\n' for x in safe_native)
        )
        (sanitized / 'r333-known-rokid-endpoint-timeline-sanitized.jsonl').write_text(
            ''.join(json.dumps(x, sort_keys=True) + '\n' for x in rokid_markers)
        )

        first = network['first_after_force']
        connection_ordering = ordering(timeline['connection_attempt'], timeline['hi_respawn'])
        summary = {
            'schema': 'rokid.test21-r3-3-3-2-1.sanitized-summary.v1',
            'analysis': 'PASS',
            'mode': 'OFFLINE_EXISTING_EVIDENCE_ONLY',
            'repair': 'TSHARK_FIELD_SEPARATOR_SEPARATOR_SLASH_T',
            'scanner_ground_truth_disposition': 'QUALIFIED_4_OF_4',
            'scanner_ground_truth_matched_hosts': matched_hosts,
            'scanner_ground_truth_matched_count': len(matched_hosts),
            'scanner_ground_truth_expected_count': 4,
            'scanner_ground_truth_malformed_rows': calibration_malformed,
            'r333_scanner_malformed_rows': r333_malformed,
            'native_csv_rows': len(source_rows),
            'native_hi_rokid_rows': len(native_rows),
            'native_known_hosts': known_hosts,
            'native_rokid_hosts': known_rokid_hosts,
            'r333_known_rokid_marker_rows': len(rokid_markers),
            'r333_known_rokid_initiation_rows_after_force': len(network['after_force']),
            'r333_known_rokid_initiation_rows_before_button_prompt': len(network['before_button_prompt']),
            'r333_known_rokid_initiation_rows_before_boundary': len(network['before_boundary']),
            'r333_known_rokid_initiation_rows_at_boundary': len(network['at_boundary']),
            'r333_known_rokid_initiation_rows_after_boundary': len(network['after_boundary']),
            'first_known_rokid_initiation_after_force': first,
            'hi_force_stop_epoch_ms': timeline['hi_force_stop'],
            'button_prompt_epoch_ms': timeline['button_prompt'],
            'connection_attempt_epoch_ms': timeline['connection_attempt'],
            'hi_respawn_epoch_ms': timeline['hi_respawn'],
            'connection_respawn_ordering': connection_ordering,
            'network_respawn_disposition': network['network_respawn_disposition'],
            'server_dependency_interpretation': network['server_dependency_interpretation'],
            'network_causality': 'CORRELATION_ONLY_NOT_CAUSATION',
            'network_absence_claim_eligible': True,
            'device_operation': 'NONE',
            'adb_operation': 'NONE',
            'new_capture': 'NONE',
            'photo_operation': 'NONE',
            'audio_operation': 'NONE',
        }
        (sanitized / 'test21-r3-3-3-2-1-summary.json').write_text(
            json.dumps(summary, indent=2, sort_keys=True) + '\n'
        )

        lines = [
            'TEST21_R3_3_3_2_1_ANALYSIS=PASS',
            'MODE=OFFLINE_EXISTING_EVIDENCE_ONLY',
            'TSHARK_FIELD_SEPARATOR_REPAIR=separator=/t',
            'SCANNER_GROUND_TRUTH_DISPOSITION=QUALIFIED_4_OF_4',
            'SCANNER_GROUND_TRUTH_MATCHED_HOSTS=4/4',
            'SCANNER_GROUND_TRUTH_HOSTS=' + ','.join(matched_hosts),
            'NETWORK_ABSENCE_CLAIM_ELIGIBLE=YES',
            f'R333_KNOWN_ROKID_MARKER_ROWS={len(rokid_markers)}',
            f'R333_KNOWN_ROKID_INITIATION_ROWS_AFTER_FORCE={len(network["after_force"])}',
            f'R333_KNOWN_ROKID_INITIATION_ROWS_BEFORE_BUTTON_PROMPT={len(network["before_button_prompt"])}',
            f'R333_KNOWN_ROKID_INITIATION_ROWS_BEFORE_CONNECTION_RESPAWN_BOUNDARY={len(network["before_boundary"])}',
            f'R333_KNOWN_ROKID_INITIATION_ROWS_AT_CONNECTION_RESPAWN_BOUNDARY={len(network["at_boundary"])}',
            f'R333_KNOWN_ROKID_INITIATION_ROWS_AFTER_CONNECTION_RESPAWN_BOUNDARY={len(network["after_boundary"])}',
            f'FIRST_KNOWN_ROKID_INITIATION_AFTER_FORCE_EPOCH_MS={first["epoch_ms"] if first else "NONE"}',
            f'FIRST_KNOWN_ROKID_INITIATION_HOST={first["host"] if first else "NONE"}',
            f'FIRST_KNOWN_ROKID_INITIATION_TYPE={first["marker_type"] if first else "NONE"}',
            f'HI_FORCE_STOP_EPOCH_MS={timeline["hi_force_stop"]}',
            f'BUTTON_PROMPT_EPOCH_MS={timeline["button_prompt"]}',
            f'CONNECTION_ATTEMPT_EPOCH_MS={timeline["connection_attempt"]}',
            f'HI_RESPAWN_EPOCH_MS={timeline["hi_respawn"]}',
            f'CONNECTION_RESPAWN_ORDERING={connection_ordering}',
            f'NETWORK_RESPAWN_DISPOSITION={network["network_respawn_disposition"]}',
            f'SERVER_DEPENDENCY_INTERPRETATION={network["server_dependency_interpretation"]}',
            'NETWORK_CAUSALITY=CORRELATION_ONLY_NOT_CAUSATION',
            'DEVICE_OPERATION=NONE',
            'ADB_OPERATION=NONE',
            'NEW_CAPTURE=NONE',
            'PHOTO_OPERATION=NONE',
            'AUDIO_OPERATION=NONE',
        ]
        (sanitized / 'test21-r3-3-3-2-1-summary.txt').write_text('\n'.join(lines) + '\n')
        print('\n'.join(lines))
        return 0
    except Exception as exc:
        print('ERROR:', exc)
        print('TEST21_R3_3_3_2_1_ANALYSIS=FAIL')
        print('R333_NETWORK_CONCLUSION=WITHHELD')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
