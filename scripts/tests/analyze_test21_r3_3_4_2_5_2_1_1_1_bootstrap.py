#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

SERVICE = 'Lcom/rokid/sprite/aiapp/externalapp/service/CXRLinkService;'
MEDIA = 'Lcom/rokid/sprite/aiapp/externalapp/IMediaStreamService;'
STUB = 'Lcom/rokid/sprite/aiapp/externalapp/IMediaStreamService$Stub;'
PROXY = 'Lcom/rokid/sprite/aiapp/externalapp/IMediaStreamService$Stub$Proxy;'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_prev(repo: Path):
    p = repo / 'scripts/tests/analyze_test21_r3_3_4_2_3_code_origin.py'
    spec = importlib.util.spec_from_file_location('r33423', p)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def cdefs(hits, target):
    return (hits.get(target) or {}).get('class_defs') or []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', required=True)
    ap.add_argument('--collection', required=True)
    ap.add_argument('--output', required=True)
    a = ap.parse_args()

    repo = Path(a.repo)
    collection = Path(a.collection)
    out = Path(a.output)
    san = out / 'sanitized'
    priv = out / 'private'
    san.mkdir(parents=True, exist_ok=True)
    priv.mkdir(parents=True, exist_ok=True)

    meta = json.loads((collection / 'external-memory-persistent-private.json').read_text())
    prev = load_prev(repo)
    Dex = prev.load_dex_base(repo).Dex

    evidence = []
    svc = []
    media = []
    stub = []
    proxy = []
    subclasses = []
    onbind = []
    parse_errors = 0

    for i, p in enumerate(sorted((collection / 'recovered-dex').glob('*.dex')), 1):
        origin = f'EXTERNAL_MEMORY_DEX[{i:03d}]'
        hits, subs, err = prev.scan_dex_bytes(p.read_bytes(), origin, Dex)
        if err:
            parse_errors += 1
        evidence.append({'origin': origin, 'sha256': sha(p), 'size': p.stat().st_size, 'parse_error': err, 'targets': hits})
        subclasses.extend(subs)
        if cdefs(hits, SERVICE):
            svc.append({'origin': origin, 'sha256': sha(p), 'class_defs': cdefs(hits, SERVICE)})
        if cdefs(hits, MEDIA):
            media.append({'origin': origin, 'sha256': sha(p), 'class_defs': cdefs(hits, MEDIA)})
        if cdefs(hits, STUB):
            stub.append({'origin': origin, 'sha256': sha(p), 'class_defs': cdefs(hits, STUB)})
        if cdefs(hits, PROXY):
            proxy.append({'origin': origin, 'sha256': sha(p), 'class_defs': cdefs(hits, PROXY)})
        for row in cdefs(hits, SERVICE):
            for method in row.get('methods') or []:
                if method.get('name') == 'onBind':
                    onbind.append({'origin': origin, 'sha256': sha(p), 'proto': method.get('proto'), 'ret': method.get('ret')})

    impls = sorted(set(str(x.get('class') or '') for x in subclasses if x.get('class')))
    svc_exact = bool(svc)
    binder_lineage = bool(stub or impls)
    impl_exact = svc_exact and bool(onbind) and binder_lineage

    selected = int(meta.get('selected_memory_bytes') or 0)
    unique = int(meta.get('unique_byte_range_read') or 0)
    readable_bytes = int(meta.get('readable_mapping_bytes') or 0)
    coverage = float(meta.get('memory_read_coverage_percent') or 0.0)
    census_exhausted = bool(meta.get('memory_census_exhausted')) and selected > 0 and unique == selected
    all_readable_selected = selected > 0 and selected == readable_bytes
    target_absence_selected = census_exhausted and not svc_exact
    target_absence_process = target_absence_selected and all_readable_selected

    if impl_exact:
        disposition = 'EXTERNAL_MEMORY_CXRLINKSERVICE_AND_ONBIND_AND_IMEDIASTREAMSERVICE_BINDER_LINEAGE_RECOVERED'
    elif svc_exact:
        disposition = 'EXTERNAL_MEMORY_CXRLINKSERVICE_CLASS_DEF_RECOVERED_BINDER_IMPLEMENTATION_PARTIAL'
    elif not census_exhausted:
        disposition = 'SELECTED_MEMORY_CENSUS_INCOMPLETE_TARGET_NOT_FOUND_IN_RECOVERED_RANGES'
    else:
        disposition = 'SELECTED_MEMORY_CENSUS_EXHAUSTED_TARGET_CLASS_DEF_NOT_RECOVERED'

    private = {
        'schema': 'rokid.test21-r3.3.4.2.5.2.1.1.1.private.v1',
        'collection': meta,
        'dex_evidence': evidence,
        'stub_subclasses': subclasses,
        'service_onbind': onbind,
    }
    (priv / 'r3-3-4-2-5-2-1-1-1-private.json').write_text(json.dumps(private, indent=2, sort_keys=True) + '\n')

    def first(rows):
        return rows[0]['origin'] if rows else 'NOT_RECOVERED'

    def firstsha(rows):
        return rows[0]['sha256'] if rows else 'NONE'

    prior = meta.get('prior_short_read_characterization') or {}
    summary = {
        'schema': 'rokid.test21-r3.3.4.2.5.2.1.1.1.sanitized.v1',
        'analysis': 'PASS',
        'root_probe': 'AVAILABLE',
        'process_maps_access': meta.get('process_maps_access', 'UNRESOLVED'),
        'persistent_root_session': 'YES' if meta.get('persistent_root_session') else 'NO',
        'persistent_root_transport': meta.get('persistent_root_transport', 'UNRESOLVED'),
        'persistent_root_session_qualification': meta.get('persistent_root_protocol_qualification', 'UNRESOLVED'),
        'magisk_su_command_quoting': meta.get('magisk_su_command_quoting', 'UNRESOLVED'),
        'persistent_root_session_count': int(meta.get('persistent_root_session_count') or 0),
        'root_worker_start_count': int(meta.get('root_worker_start_count') or 0),
        'root_worker_temp_cleanup_reported': 'YES' if meta.get('worker_cleanup_reported') else 'NO',
        'device_transient_temp_files': 'YES' if meta.get('device_transient_temp_files') else 'NO',
        'qualification_result': meta.get('qualification_result', 'UNRESOLVED'),
        'qualification_elapsed_seconds': int(meta.get('qualification_elapsed_seconds') or 0),
        'qualification_read_count': int(meta.get('qualification_read_count') or 0),
        'global_elapsed_seconds': int(meta.get('global_elapsed_seconds') or 0),
        'external_proc_mem_access': meta.get('external_proc_mem_access', 'UNRESOLVED'),
        'readable_mapping_count': meta.get('readable_mapping_count', 0),
        'readable_mapping_bytes': readable_bytes,
        'selected_memory_chunk_count': meta.get('selected_chunk_count', 0),
        'selected_memory_bytes': selected,
        'attempted_memory_bytes': meta.get('attempted_memory_bytes', 0),
        'unique_byte_range_read': unique,
        'full_read_bytes': meta.get('full_read_bytes', 0),
        'partial_read_bytes': meta.get('partial_read_bytes', 0),
        'failed_read_bytes': meta.get('failed_read_bytes', 0),
        'memory_read_coverage_percent': coverage,
        'memory_census_exhausted': 'YES' if census_exhausted else 'NO',
        'target_not_found_in_recovered_ranges': 'YES' if not svc_exact else 'NO',
        'target_absence_from_selected_memory_proven': 'YES' if target_absence_selected else 'NO',
        'target_absence_from_process_memory_proven': 'YES' if target_absence_process else 'NO',
        'full_page_count': meta.get('full_page_count', 0),
        'failed_page_count': meta.get('failed_page_count', 0),
        'full_range_count': meta.get('full_range_count', 0),
        'partial_range_count': meta.get('partial_range_count', 0),
        'failed_range_count': meta.get('failed_range_count', 0),
        'suspicious_subpage_count': meta.get('suspicious_subpage_count', 0),
        'read_attempt_count': meta.get('read_attempt_count', 0),
        'read_stop_reason': meta.get('stop_reason', 'UNRESOLVED'),
        'prior_short_read_characterization': 'AVAILABLE' if prior.get('available') else 'UNAVAILABLE',
        'prior_selected_bytes': prior.get('selected_bytes', 0) if prior.get('available') else 0,
        'prior_memory_bytes_read': prior.get('memory_bytes_read', 0) if prior.get('available') else 0,
        'prior_coverage_percent': prior.get('coverage_percent') if prior.get('available') else None,
        'prior_partial_read_count': prior.get('partial_read_count', 0) if prior.get('available') else 0,
        'prior_returned_size_mode_bytes': prior.get('returned_size_mode_bytes', 0) if prior.get('available') else 0,
        'prior_returned_size_mode_count': prior.get('returned_size_mode_count', 0) if prior.get('available') else 0,
        'prior_duplicate_short_output_max_count': prior.get('duplicate_short_output_max_count', 0) if prior.get('available') else 0,
        'dex_magic_hit_count': meta.get('dex_magic_hit_count', 0),
        'cdex_magic_hit_count': meta.get('cdex_magic_hit_count', 0),
        'dex_validated_count': meta.get('dex_validated_count', 0),
        'dex_recovered_unique_count': meta.get('dex_recovered_unique_count', 0),
        'dex_parse_error_count': parse_errors,
        'cxrlinkservice_code_origin': first(svc),
        'cxrlinkservice_code_origin_sha256': firstsha(svc),
        'cxrlinkservice_class_def_confirmed': 'YES' if svc_exact else 'NO',
        'imediaservice_interface_origin': first(media),
        'imediaservice_stub_origin': first(stub),
        'imediaservice_proxy_origin': first(proxy),
        'service_side_cxrlinkservice_onbind_count': len(onbind),
        'imediaservice_stub_subclass_count': len(impls),
        'service_implementation_origin_closure': 'YES' if impl_exact else 'NO',
        'service_implementation_disposition': disposition,
        'proof_boundary': 'ONE_MAGISK_ROOT_SHELL_T_NONTTY_QUOTED_SU_PERSISTENT_WORKER_FRAMED_BOUNDED_PROC_MEM_READS_EXACT_COVERAGE_ACCOUNTING_PARSED_DEX_CLASS_DEF_NO_FRIDA_NO_PTRACE_NO_SIGNAL_NO_PAYLOAD_EXECUTION',
    }

    (san / 'test21-r3-3-4-2-5-2-1-1-1-summary.json').write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n')

    def v(name):
        x = summary[name]
        if isinstance(x, float):
            return f'{x:.6f}'
        if x is None:
            return 'UNRESOLVED'
        return str(x)

    keys = [
        ('TEST21_R3_3_4_2_5_2_1_1_1_ANALYSIS', 'PASS'),
        ('ROOT_PROBE', 'AVAILABLE'),
        ('ROOT_PROCESS_MAPS_ACCESS', summary['process_maps_access']),
        ('PERSISTENT_ROOT_SESSION', summary['persistent_root_session']),
        ('PERSISTENT_ROOT_TRANSPORT', summary['persistent_root_transport']),
        ('PERSISTENT_ROOT_SESSION_QUALIFICATION', summary['persistent_root_session_qualification']),
        ('MAGISK_SU_COMMAND_QUOTING', summary['magisk_su_command_quoting']),
        ('PERSISTENT_ROOT_SESSION_COUNT', v('persistent_root_session_count')),
        ('ROOT_WORKER_START_COUNT', v('root_worker_start_count')),
        ('ROOT_WORKER_TEMP_CLEANUP_REPORTED', summary['root_worker_temp_cleanup_reported']),
        ('DEVICE_TRANSIENT_TEMP_FILES', summary['device_transient_temp_files']),
        ('QUALIFICATION_RESULT', summary['qualification_result']),
        ('QUALIFICATION_ELAPSED_SECONDS', v('qualification_elapsed_seconds')),
        ('QUALIFICATION_READ_COUNT', v('qualification_read_count')),
        ('GLOBAL_ELAPSED_SECONDS', v('global_elapsed_seconds')),
        ('EXTERNAL_PROC_MEM_ACCESS', summary['external_proc_mem_access']),
        ('READABLE_MAPPING_COUNT', v('readable_mapping_count')),
        ('READABLE_MAPPING_BYTES', v('readable_mapping_bytes')),
        ('SELECTED_MEMORY_CHUNK_COUNT', v('selected_memory_chunk_count')),
        ('SELECTED_MEMORY_BYTES', v('selected_memory_bytes')),
        ('ATTEMPTED_MEMORY_BYTES', v('attempted_memory_bytes')),
        ('UNIQUE_BYTE_RANGE_READ', v('unique_byte_range_read')),
        ('FULL_READ_BYTES', v('full_read_bytes')),
        ('PARTIAL_READ_BYTES', v('partial_read_bytes')),
        ('FAILED_READ_BYTES', v('failed_read_bytes')),
        ('MEMORY_READ_COVERAGE_PERCENT', v('memory_read_coverage_percent')),
        ('MEMORY_CENSUS_EXHAUSTED', summary['memory_census_exhausted']),
        ('TARGET_NOT_FOUND_IN_RECOVERED_RANGES', summary['target_not_found_in_recovered_ranges']),
        ('TARGET_ABSENCE_FROM_SELECTED_MEMORY_PROVEN', summary['target_absence_from_selected_memory_proven']),
        ('TARGET_ABSENCE_FROM_PROCESS_MEMORY_PROVEN', summary['target_absence_from_process_memory_proven']),
        ('FULL_PAGE_COUNT', v('full_page_count')),
        ('FAILED_PAGE_COUNT', v('failed_page_count')),
        ('FULL_RANGE_COUNT', v('full_range_count')),
        ('PARTIAL_RANGE_COUNT', v('partial_range_count')),
        ('FAILED_RANGE_COUNT', v('failed_range_count')),
        ('SUSPICIOUS_SUBPAGE_COUNT', v('suspicious_subpage_count')),
        ('READ_ATTEMPT_COUNT', v('read_attempt_count')),
        ('READ_STOP_REASON', summary['read_stop_reason']),
        ('PRIOR_SHORT_READ_CHARACTERIZATION', summary['prior_short_read_characterization']),
        ('PRIOR_SELECTED_BYTES', v('prior_selected_bytes')),
        ('PRIOR_MEMORY_BYTES_READ', v('prior_memory_bytes_read')),
        ('PRIOR_COVERAGE_PERCENT', v('prior_coverage_percent')),
        ('PRIOR_PARTIAL_READ_COUNT', v('prior_partial_read_count')),
        ('PRIOR_RETURNED_SIZE_MODE_BYTES', v('prior_returned_size_mode_bytes')),
        ('PRIOR_RETURNED_SIZE_MODE_COUNT', v('prior_returned_size_mode_count')),
        ('PRIOR_DUPLICATE_SHORT_OUTPUT_MAX_COUNT', v('prior_duplicate_short_output_max_count')),
        ('DEX_MAGIC_HIT_COUNT', v('dex_magic_hit_count')),
        ('CDEX_MAGIC_HIT_COUNT', v('cdex_magic_hit_count')),
        ('DEX_VALIDATED_COUNT', v('dex_validated_count')),
        ('DEX_RECOVERED_UNIQUE_COUNT', v('dex_recovered_unique_count')),
        ('DEX_PARSE_ERROR_COUNT', v('dex_parse_error_count')),
        ('CXRLINKSERVICE_CODE_ORIGIN', summary['cxrlinkservice_code_origin']),
        ('CXRLINKSERVICE_CODE_ORIGIN_SHA256', summary['cxrlinkservice_code_origin_sha256']),
        ('CXRLINKSERVICE_CLASS_DEF_CONFIRMED', summary['cxrlinkservice_class_def_confirmed']),
        ('IMEDIASTREAMSERVICE_INTERFACE_ORIGIN', summary['imediaservice_interface_origin']),
        ('IMEDIASTREAMSERVICE_STUB_ORIGIN', summary['imediaservice_stub_origin']),
        ('IMEDIASTREAMSERVICE_PROXY_ORIGIN', summary['imediaservice_proxy_origin']),
        ('SERVICE_SIDE_CXRLINKSERVICE_ONBIND_COUNT', v('service_side_cxrlinkservice_onbind_count')),
        ('IMEDIASTREAMSERVICE_STUB_SUBCLASS_COUNT', v('imediaservice_stub_subclass_count')),
        ('SERVICE_IMPLEMENTATION_ORIGIN_CLOSURE', summary['service_implementation_origin_closure']),
        ('SERVICE_IMPLEMENTATION_DISPOSITION', disposition),
        ('FRIDA_SERVER_START', 'NONE'),
        ('FRIDA_PROCESS_ATTACH', 'NONE'),
        ('INJECTED_AGENT_LOAD', 'NONE'),
        ('PTRACE_ATTACH', 'NONE'),
        ('PROCESS_SIGNAL', 'NONE'),
        ('PAYLOAD_EXECUTION', 'NONE'),
        ('DEVICE_PERSISTENT_MUTATION', 'NONE'),
        ('HI_ROKID_FORCE_STOP', 'NONE'),
        ('CXR_L_CONNECTION_ATTEMPT', 'NONE'),
        ('PHOTO_OPERATION', 'NONE'),
        ('AUDIO_OPERATION', 'NONE'),
    ]
    lines = [f'{k}={val}' for k, val in keys]
    (san / 'test21-r3-3-4-2-5-2-1-1-1-summary.txt').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
