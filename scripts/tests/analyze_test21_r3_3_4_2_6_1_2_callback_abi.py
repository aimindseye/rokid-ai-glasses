#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

SCHEMA = 'rokid.test21-r3-3-4-2-6-1-2.callback-binder-abi-closure.v1'
HERE = Path(__file__).resolve().parent
PARENT_PATH = HERE / 'analyze_test21_r3_3_4_2_6_1_1_proxy_closure.py'

spec = importlib.util.spec_from_file_location('r3342611_parent', PARENT_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError('unable to load accepted r3.3.4.2.6.1.1 analyzer')
P = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = P
spec.loader.exec_module(P)
B = P.B

EXPECTED_AAR_SHA256 = P.EXPECTED_AAR_SHA256
EXPECTED_COORDINATE = P.EXPECTED_COORDINATE
ACC_PUBLIC = P.ACC_PUBLIC
IBINDER_DESC = 'Landroid/os/IBinder;'
BINDER = 'android/os/Binder'

CALLBACK_INTERFACES = [
    ('IMAGE', 'com/rokid/sprite/aiapp/externalapp/IImageStreamCallback'),
    ('AUDIO', 'com/rokid/sprite/aiapp/externalapp/IAudioStreamCallback'),
    ('CUSTOM_VIEW', 'com/rokid/sprite/aiapp/externalapp/ICustomViewCallback'),
    ('DEVICE_STATUS', 'com/rokid/sprite/aiapp/externalapp/IDeviceStatusCallback'),
    ('CUSTOM_CMD', 'com/rokid/sprite/aiapp/externalapp/ICustomCmdCallback'),
    ('GLASS_APP', 'com/rokid/sprite/aiapp/externalapp/IGlassAppCallback'),
    ('AI_EVENT', 'com/rokid/sprite/aiapp/externalapp/IAiEventCallback'),
]
EXPECTED_CALLBACK_INTERFACE_COUNT = 7


def sha256_path(path: Path) -> str:
    return P.sha256_path(path)


def class_super_name(cf: Any) -> str | None:
    return P.class_super_name(cf)


def is_subclass(classes: dict[str, Any], cname: str, target: str, seen: set[str] | None = None) -> bool:
    if cname == target:
        return True
    if seen is None:
        seen = set()
    if cname in seen:
        return False
    seen.add(cname)
    cf = classes.get(cname)
    if cf is None:
        return False
    sup = class_super_name(cf)
    return bool(sup and is_subclass(classes, sup, target, seen))


def implements_iface(classes: dict[str, Any], cname: str, target: str) -> bool:
    return P.implements_iface(classes, cname, target)


def interface_methods(classes: dict[str, Any], iface: str) -> list[dict[str, Any]]:
    cf = classes.get(iface)
    if cf is None:
        return []
    rows = []
    for m in cf.methods:
        if m.name.startswith('<') or m.name == 'asBinder':
            continue
        rows.append({'name': m.name, 'proto': m.desc, 'signature': m.name + m.desc, 'access': m.access})
    return sorted(rows, key=lambda x: (x['name'], x['proto']))


def method_signature_set(cf: Any) -> set[str]:
    return {m.name + m.desc for m in cf.methods if not m.name.startswith('<') and m.name != 'asBinder'}


def cp_has_string(cf: Any, text: str) -> bool:
    for item in cf.cp:
        if not item:
            continue
        try:
            if item[0] == 'Utf8' and item[1] == text:
                return True
            if item[0] == 8 and cf.utf8(item[1]) == text:
                return True
        except Exception:
            pass
    return False


def transact_call_count(cf: Any) -> int:
    count = 0
    for m in cf.methods:
        for ref in B.invoke_refs(cf, m):
            if ref['owner'] == 'android/os/IBinder' and ref['name'] == 'transact':
                count += 1
    return count


def find_stub(classes: dict[str, Any], iface: str) -> tuple[str | None, str, int]:
    literal = iface + '$Stub'
    if literal in classes:
        return literal, 'LITERAL_STUB', 1
    candidates = []
    for cname, cf in classes.items():
        if cname == iface:
            continue
        if not implements_iface(classes, cname, iface):
            continue
        if not is_subclass(classes, cname, BINDER):
            continue
        if not any(m.name == 'onTransact' and m.code for m in cf.methods):
            continue
        candidates.append(cname)
    if len(candidates) == 1:
        return candidates[0], 'UNIQUE_STRUCTURAL_BINDER_STUB', 1
    if not candidates:
        return None, 'NO_BINDER_STUB_FOUND', 0
    return None, 'AMBIGUOUS_STRUCTURAL_BINDER_STUBS', len(candidates)


def structural_proxy_candidates(classes: dict[str, Any], iface: str, stub: str | None, methods: list[dict[str, Any]]) -> list[dict[str, Any]]:
    expected = {m['signature'] for m in methods}
    descriptor = iface.replace('/', '.')
    rows = []
    for cname, cf in classes.items():
        if cname == iface or cname == stub:
            continue
        if not implements_iface(classes, cname, iface):
            continue
        if stub and is_subclass(classes, cname, stub):
            continue
        sigs = method_signature_set(cf)
        matched = len(sigs & expected)
        binder_fields = sum(1 for f in cf.fields if f.desc == IBINDER_DESC)
        tx_calls = transact_call_count(cf)
        descriptor_ref = cp_has_string(cf, descriptor)
        stub_related = bool(stub and cname.startswith(stub + '$'))
        score = tx_calls * 1000 + matched * 20 + binder_fields * 10 + (5 if descriptor_ref else 0) + (1 if stub_related else 0)
        if tx_calls:
            rows.append({
                'class_name': cname,
                'matching_interface_method_count': matched,
                'binder_field_count': binder_fields,
                'ibinder_transact_call_count': tx_calls,
                'descriptor_reference': descriptor_ref,
                'stub_related_name': stub_related,
                'score': score,
            })
    return sorted(rows, key=lambda r: (-r['score'], r['class_name']))


def select_proxy(candidates: list[dict[str, Any]], method_count: int) -> tuple[str | None, str]:
    if not candidates:
        return None, 'NO_IBINDER_TRANSACT_IMPLEMENTER_FOUND'
    top = candidates[0]
    tied = [r for r in candidates if r['score'] == top['score']]
    if len(tied) != 1:
        return None, 'AMBIGUOUS_TOP_STRUCTURAL_PROXY_CANDIDATES'
    if top['matching_interface_method_count'] != method_count:
        return None, 'TOP_CANDIDATE_DOES_NOT_IMPLEMENT_EXACT_INTERFACE_SURFACE'
    return top['class_name'], 'UNIQUE_EXACT_STRUCTURAL_PROXY'


def invocation_ref(cf: Any, ins: Any) -> tuple[str, str, str, str] | None:
    return P.invocation_ref(cf, ins)


def field_ref(cf: Any, ins: Any) -> tuple[str, str, str, str] | None:
    return P.field_ref(cf, ins)


def recover_transact_code(cf: Any, insns: list[Any], tx_index: int) -> tuple[int | None, str]:
    return P.recover_transact_code(cf, insns, tx_index)


def recover_transact_flags(insns: list[Any], tx_index: int) -> tuple[int | None, str]:
    # AIDL-generated proxy code materializes the transact flags as the final
    # integer literal immediately before IBinder.transact(). This is robust to
    # payload integer writes because those precede the final transact arguments.
    start = max(0, tx_index - 20)
    vals = [x.int_value for x in insns[start:tx_index] if x.int_value is not None]
    if not vals:
        return None, 'NO_LITERAL_TRANSACT_FLAGS_RECOVERED'
    flag = vals[-1]
    if flag in (0, 1):
        return flag, 'FINAL_INTEGER_LITERAL_BEFORE_TRANSACT'
    return None, 'FINAL_INTEGER_LITERAL_NOT_STANDARD_AIDL_FLAG'


def ontransact_map(classes: dict[str, Any], stub: str | None, methods: list[dict[str, Any]]) -> dict[str, list[int]]:
    if stub is None:
        return {}
    cf = classes.get(stub)
    if cf is None:
        return {}
    out: dict[str, list[int]] = defaultdict(list)
    valid = {(x['name'], x['proto']): x['signature'] for x in methods}
    for m in [x for x in cf.methods if x.name == 'onTransact' and x.code]:
        insns = B.decode(m.code or b'', cf)
        off_to_index = {x.off: i for i, x in enumerate(insns)}
        switches = [x for x in insns if x.switch_pairs]
        for sw in switches:
            targets = sorted({target for _, target in sw.switch_pairs or []})
            for code, target in sw.switch_pairs or []:
                if code <= 0 or code > 65535:
                    continue
                idx = off_to_index.get(target)
                if idx is None:
                    continue
                next_targets = [t for t in targets if t > target]
                end = next_targets[0] if next_targets else len(m.code or b'')
                for x in insns[idx:]:
                    if x.off >= end:
                        break
                    ref = invocation_ref(cf, x)
                    if not ref:
                        continue
                    owner, name, desc, _ = ref
                    sig = valid.get((name, desc))
                    if sig:
                        out[sig].append(code)
                        break
    return {k: sorted(set(v)) for k, v in out.items()}


def proxy_contract(classes: dict[str, Any], proxy: str | None, methods: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    per_method: dict[str, Any] = {}
    diag = {
        'implemented_method_count': 0,
        'transaction_method_count': 0,
        'request_contract_count': 0,
        'reply_contract_count': 0,
        'parcel_contract_count': 0,
        'sync_reply_method_count': 0,
        'oneway_method_count': 0,
        'transact_flag_recovered_method_count': 0,
    }
    if proxy is None:
        return per_method, diag
    cf = classes[proxy]
    by_sig = {(m.name, m.desc): m for m in cf.methods}
    for item in methods:
        sig = item['signature']
        m = by_sig.get((item['name'], item['proto']))
        row = {
            'method_found': bool(m),
            'transaction_codes': [],
            'transaction_code_recovery': [],
            'transact_flags': [],
            'transact_flag_recovery': [],
            'request_operations': [],
            'reply_operations': [],
            'reply_mode': 'UNRESOLVED',
            'request_contract_recovered': False,
            'reply_contract_recovered': False,
            'parcel_contract_recovered': False,
        }
        if m:
            diag['implemented_method_count'] += 1
        if not m or not m.code:
            per_method[sig] = row
            continue
        insns = B.decode(m.code, cf)
        tx_indices = []
        codes = []
        flags = []
        code_hows = []
        flag_hows = []
        for idx, ins in enumerate(insns):
            ref = invocation_ref(cf, ins)
            if ref and ref[0] == 'android/os/IBinder' and ref[1] == 'transact':
                tx_indices.append(idx)
                code, how = recover_transact_code(cf, insns, idx)
                flag, fhow = recover_transact_flags(insns, idx)
                if code is not None:
                    codes.append(code)
                if flag is not None:
                    flags.append(flag)
                code_hows.append(how)
                flag_hows.append(fhow)
        row['transaction_codes'] = sorted(set(codes))
        row['transaction_code_recovery'] = code_hows
        row['transact_flags'] = sorted(set(flags))
        row['transact_flag_recovery'] = flag_hows
        if len(row['transaction_codes']) == 1:
            diag['transaction_method_count'] += 1
        if len(row['transact_flags']) == 1:
            diag['transact_flag_recovered_method_count'] += 1
        first_tx = tx_indices[0] if tx_indices else None
        req_ops: list[str] = []
        rep_ops: list[str] = []
        for idx, ins in enumerate(insns):
            ref = invocation_ref(cf, ins)
            if not ref or ref[0] != 'android/os/Parcel':
                continue
            op = ref[1] + ref[2]
            if first_tx is None or idx < first_tx:
                if ref[1].startswith('write'):
                    req_ops.append(op)
            elif idx > first_tx:
                if ref[1].startswith('read'):
                    rep_ops.append(op)
        row['request_operations'] = req_ops
        row['reply_operations'] = rep_ops
        request_ok = any(x.startswith('writeInterfaceToken') for x in req_ops) and len(row['transaction_codes']) == 1
        flag = row['transact_flags'][0] if len(row['transact_flags']) == 1 else None
        has_read_exception = any(x.startswith('readException') for x in rep_ops)
        if flag == 1 and not has_read_exception:
            reply_mode = 'ONEWAY_NO_REPLY'
            reply_ok = True
            diag['oneway_method_count'] += 1
        elif flag == 0 and has_read_exception:
            reply_mode = 'SYNC_REPLY'
            reply_ok = True
            diag['sync_reply_method_count'] += 1
        else:
            reply_mode = 'UNRESOLVED'
            reply_ok = False
        row['reply_mode'] = reply_mode
        row['request_contract_recovered'] = request_ok
        row['reply_contract_recovered'] = reply_ok and len(row['transaction_codes']) == 1
        row['parcel_contract_recovered'] = row['request_contract_recovered'] and row['reply_contract_recovered']
        diag['request_contract_count'] += int(row['request_contract_recovered'])
        diag['reply_contract_count'] += int(row['reply_contract_recovered'])
        diag['parcel_contract_count'] += int(row['parcel_contract_recovered'])
        per_method[sig] = row
    return per_method, diag


def descriptor_exact(classes: dict[str, Any], iface: str, stub: str | None, proxy: str | None) -> bool:
    want = iface.replace('/', '.')
    for cname in (iface, stub, proxy):
        if not cname or cname not in classes:
            continue
        cf = classes[cname]
        for f in cf.fields:
            if f.name == 'DESCRIPTOR' and f.const == want:
                return True
        if cp_has_string(cf, want):
            return True
    return False


def analyze_callback(classes: dict[str, Any], label: str, iface: str) -> dict[str, Any]:
    methods = interface_methods(classes, iface)
    method_count = len(methods)
    stub, stub_selection, stub_candidate_count = find_stub(classes, iface)
    candidates = structural_proxy_candidates(classes, iface, stub, methods)
    proxy, proxy_selection = select_proxy(candidates, method_count)
    on_map = ontransact_map(classes, stub, methods)
    pc, pdiag = proxy_contract(classes, proxy, methods)

    rows = []
    agreement = 0
    mismatches = 0
    canonical_codes = []
    for m in methods:
        sig = m['signature']
        stub_codes = on_map.get(sig, [])
        proxy_codes = pc.get(sig, {}).get('transaction_codes', [])
        sources = {}
        if stub_codes:
            sources['onTransact'] = stub_codes
        if proxy_codes:
            sources['proxy'] = proxy_codes
        flat = {x for vals in sources.values() for x in vals}
        mismatch = len(flat) > 1 or any(len(vals) != 1 for vals in sources.values())
        if mismatch:
            mismatches += 1
        agree = len(sources) == 2 and not mismatch
        agreement += int(agree)
        code = next(iter(flat)) if len(flat) == 1 else None
        if code is not None:
            canonical_codes.append(code)
        pr = pc.get(sig, {})
        rows.append({
            'name': m['name'], 'proto': m['proto'], 'signature': sig,
            'transaction_code': code,
            'ontransact_codes': stub_codes,
            'proxy_codes': proxy_codes,
            'two_source_agreement': agree,
            'transact_flags': pr.get('transact_flags', []),
            'reply_mode': pr.get('reply_mode', 'UNRESOLVED'),
            'request_operations': pr.get('request_operations', []),
            'reply_operations': pr.get('reply_operations', []),
            'request_contract_recovered': bool(pr.get('request_contract_recovered')),
            'reply_contract_recovered': bool(pr.get('reply_contract_recovered')),
            'parcel_contract_recovered': bool(pr.get('parcel_contract_recovered')),
        })

    on_count = sum(1 for r in rows if len(r['ontransact_codes']) == 1)
    proxy_count = sum(1 for r in rows if len(r['proxy_codes']) == 1)
    req_count = sum(1 for r in rows if r['request_contract_recovered'])
    rep_count = sum(1 for r in rows if r['reply_contract_recovered'])
    parcel_count = sum(1 for r in rows if r['parcel_contract_recovered'])
    unique_codes = len(set(canonical_codes))
    present = iface in classes
    desc_exact = descriptor_exact(classes, iface, stub, proxy)
    transaction_ready = (
        present and method_count > 0 and stub is not None and proxy is not None
        and on_count == method_count and proxy_count == method_count
        and agreement == method_count and mismatches == 0 and unique_codes == method_count
    )
    parcel_ready = method_count > 0 and req_count == method_count and rep_count == method_count and parcel_count == method_count
    abi_ready = transaction_ready and parcel_ready and desc_exact
    return {
        'label': label,
        'interface': iface,
        'descriptor': iface.replace('/', '.'),
        'interface_present': present,
        'descriptor_exact': desc_exact,
        'method_count': method_count,
        'stub_class': stub,
        'stub_selection': stub_selection,
        'stub_candidate_count': stub_candidate_count,
        'proxy_class': proxy,
        'proxy_selection': proxy_selection,
        'proxy_candidate_count': len(candidates),
        'proxy_candidates': candidates,
        'proxy_implemented_method_count': pdiag['implemented_method_count'],
        'ontransact_method_count': on_count,
        'proxy_transaction_method_count': proxy_count,
        'two_source_agreement_count': agreement,
        'transaction_mismatch_count': mismatches,
        'transaction_unique_code_count': unique_codes,
        'request_parcel_contract_count': req_count,
        'reply_parcel_contract_count': rep_count,
        'parcel_contract_count': parcel_count,
        'sync_reply_method_count': pdiag['sync_reply_method_count'],
        'oneway_method_count': pdiag['oneway_method_count'],
        'transact_flag_recovered_method_count': pdiag['transact_flag_recovered_method_count'],
        'transaction_contract_ready': transaction_ready,
        'parcel_contract_ready': parcel_ready,
        'abi_ready': abi_ready,
        'methods': rows,
    }


def analyze_aar(aar: Path, fixture_mode: bool = False) -> dict[str, Any]:
    digest = sha256_path(aar)
    if not fixture_mode and digest != EXPECTED_AAR_SHA256:
        raise ValueError(f'AAR SHA-256 mismatch expected={EXPECTED_AAR_SHA256} actual={digest}')
    classes, classes_jar_sha = B.load_aar(aar)
    callbacks = [analyze_callback(classes, label, iface) for label, iface in CALLBACK_INTERFACES]
    interface_present_count = sum(1 for c in callbacks if c['interface_present'])
    descriptor_count = sum(1 for c in callbacks if c['descriptor_exact'])
    method_count = sum(c['method_count'] for c in callbacks)
    stub_count = sum(1 for c in callbacks if c['stub_class'])
    proxy_count = sum(1 for c in callbacks if c['proxy_class'])
    on_count = sum(c['ontransact_method_count'] for c in callbacks)
    ptx_count = sum(c['proxy_transaction_method_count'] for c in callbacks)
    agree_count = sum(c['two_source_agreement_count'] for c in callbacks)
    mismatch_count = sum(c['transaction_mismatch_count'] for c in callbacks)
    req_count = sum(c['request_parcel_contract_count'] for c in callbacks)
    rep_count = sum(c['reply_parcel_contract_count'] for c in callbacks)
    parcel_count = sum(c['parcel_contract_count'] for c in callbacks)
    ready_count = sum(1 for c in callbacks if c['abi_ready'])
    full_boundary_ready = (
        interface_present_count == EXPECTED_CALLBACK_INTERFACE_COUNT
        and descriptor_count == EXPECTED_CALLBACK_INTERFACE_COUNT
        and stub_count == EXPECTED_CALLBACK_INTERFACE_COUNT
        and proxy_count == EXPECTED_CALLBACK_INTERFACE_COUNT
        and method_count > 0
        and agree_count == method_count
        and mismatch_count == 0
        and parcel_count == method_count
        and ready_count == EXPECTED_CALLBACK_INTERFACE_COUNT
    )
    return {
        'schema': SCHEMA,
        'analysis': 'PASS',
        'access_mode': 'HOST_ONLY_LOCAL_AAR',
        'root_required': False,
        'magisk_required': False,
        'adb_required': False,
        'frida_required': False,
        'phone_action': 'NONE',
        'network_required': False,
        'input': {
            'coordinate': EXPECTED_COORDINATE,
            'aar_sha256': digest,
            'aar_identity': 'FIXTURE' if fixture_mode else 'PASS',
            'classes_jar_sha256': classes_jar_sha,
            'fixture_mode': fixture_mode,
        },
        'callback_summary': {
            'expected_interface_count': EXPECTED_CALLBACK_INTERFACE_COUNT,
            'interface_present_count': interface_present_count,
            'descriptor_exact_count': descriptor_count,
            'total_method_count': method_count,
            'stub_interface_count': stub_count,
            'structural_proxy_interface_count': proxy_count,
            'ontransact_method_count': on_count,
            'proxy_transaction_method_count': ptx_count,
            'two_source_agreement_count': agree_count,
            'transaction_mismatch_count': mismatch_count,
            'request_parcel_contract_count': req_count,
            'reply_parcel_contract_count': rep_count,
            'parcel_contract_count': parcel_count,
            'abi_ready_interface_count': ready_count,
            'all_callback_binder_abis_ready': ready_count == EXPECTED_CALLBACK_INTERFACE_COUNT,
            'clean_room_full_binder_boundary_ready': full_boundary_ready,
        },
        'callbacks': callbacks,
        'clean_room': {
            'service_binder_abi_prerequisite': 'r3.3.4.2.6.1.1_ACCEPTED_TWO_SOURCE_CLIENT_BINDER_ABI',
            'callback_binder_boundary_ready': full_boundary_ready,
            'full_binder_boundary_ready': full_boundary_ready,
            'functional_behavior_compatibility_proven': False,
            'authorization_semantics_recovered': False,
            'session_lifecycle_semantics_recovered': False,
            'service_implementation_recovered': False,
            'disposition': 'SERVICE_AND_SEVEN_CALLBACK_BINDER_ABI_BOUNDARY_CLOSED_NO_VENDOR_BEHAVIOR_CLAIM' if full_boundary_ready else 'CALLBACK_BINDER_ABI_STATIC_CLOSURE_INCOMPLETE',
        },
        'device_operation': 'NONE',
        'photo_operation': 'NONE',
        'audio_operation': 'NONE',
        'network_capture': 'NONE',
    }


def write_outputs(result: dict[str, Any], output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    san = output / 'sanitized'
    san.mkdir(exist_ok=True)
    (output / 'r3342612-private-analysis.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    (san / 'test21-r3-3-4-2-6-1-2-summary.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    inp = result['input']; s = result['callback_summary']; cr = result['clean_room']
    lines = [
        'TEST21_R3_3_4_2_6_1_2_ANALYSIS=PASS',
        'ACCESS_MODE=HOST_ONLY_LOCAL_AAR', 'ROOT_REQUIRED=NO', 'MAGISK_REQUIRED=NO', 'ADB_REQUIRED=NO', 'FRIDA_REQUIRED=NO', 'PHONE_ACTION=NONE', 'NETWORK_REQUIRED=NO',
        'AAR_COORDINATE=' + inp['coordinate'], 'AAR_SHA256=' + inp['aar_sha256'], 'AAR_IDENTITY=' + inp['aar_identity'],
        f"CALLBACK_INTERFACE_COUNT={s['expected_interface_count']}",
        f"CALLBACK_INTERFACE_PRESENT_COUNT={s['interface_present_count']}",
        f"CALLBACK_DESCRIPTOR_EXACT_COUNT={s['descriptor_exact_count']}",
        f"CALLBACK_METHOD_COUNT={s['total_method_count']}",
        f"CALLBACK_STUB_INTERFACE_COUNT={s['stub_interface_count']}",
        f"CALLBACK_STRUCTURAL_PROXY_INTERFACE_COUNT={s['structural_proxy_interface_count']}",
        f"CALLBACK_ONTRANSACT_METHOD_COUNT={s['ontransact_method_count']}",
        f"CALLBACK_PROXY_TRANSACTION_METHOD_COUNT={s['proxy_transaction_method_count']}",
        f"CALLBACK_TWO_SOURCE_AGREEMENT_COUNT={s['two_source_agreement_count']}",
        f"CALLBACK_TRANSACTION_MISMATCH_COUNT={s['transaction_mismatch_count']}",
        f"CALLBACK_REQUEST_PARCEL_CONTRACT_COUNT={s['request_parcel_contract_count']}",
        f"CALLBACK_REPLY_PARCEL_CONTRACT_COUNT={s['reply_parcel_contract_count']}",
        f"CALLBACK_PARCEL_CONTRACT_COUNT={s['parcel_contract_count']}",
        f"CALLBACK_ABI_READY_INTERFACE_COUNT={s['abi_ready_interface_count']}",
    ]
    for c in result['callbacks']:
        lines.extend([
            f"{c['label']}_CALLBACK_DESCRIPTOR={c['descriptor']}",
            f"{c['label']}_CALLBACK_METHOD_COUNT={c['method_count']}",
            f"{c['label']}_CALLBACK_STUB_SELECTION={c['stub_selection']}",
            f"{c['label']}_CALLBACK_PROXY_SELECTION={c['proxy_selection']}",
            f"{c['label']}_CALLBACK_TWO_SOURCE_AGREEMENT_COUNT={c['two_source_agreement_count']}",
            f"{c['label']}_CALLBACK_TRANSACTION_MISMATCH_COUNT={c['transaction_mismatch_count']}",
            f"{c['label']}_CALLBACK_ABI_READY={'YES' if c['abi_ready'] else 'NO'}",
        ])
    lines.extend([
        'ALL_CALLBACK_BINDER_ABIS_READY=' + ('YES' if s['all_callback_binder_abis_ready'] else 'NO'),
        'CLEAN_ROOM_FULL_BINDER_BOUNDARY_READY=' + ('YES' if s['clean_room_full_binder_boundary_ready'] else 'NO'),
        'FUNCTIONAL_BEHAVIOR_COMPATIBILITY_PROVEN=NO', 'AUTHORIZATION_SEMANTICS_RECOVERED=NO', 'SESSION_LIFECYCLE_SEMANTICS_RECOVERED=NO', 'SERVICE_IMPLEMENTATION_RECOVERED=NO',
        'CLEAN_ROOM_DISPOSITION=' + cr['disposition'], 'DEVICE_OPERATION=NONE', 'PHOTO_OPERATION=NONE', 'AUDIO_OPERATION=NONE', 'NETWORK_CAPTURE=NONE',
    ])
    (san / 'test21-r3-3-4-2-6-1-2-summary.txt').write_text('\n'.join(lines) + '\n')
    md = [
        '# Test 21 r3.3.4.2.6.1.2 — callback Binder ABI closure', '',
        f"- AAR identity: **{inp['aar_identity']}** (`{inp['aar_sha256']}`)",
        f"- Callback interfaces present: **{s['interface_present_count']} / {EXPECTED_CALLBACK_INTERFACE_COUNT}**",
        f"- Callback methods: **{s['total_method_count']}**",
        f"- Stub/Proxy transaction agreements: **{s['two_source_agreement_count']} / {s['total_method_count']}**; mismatches **{s['transaction_mismatch_count']}**",
        f"- Parcel contracts recovered: **{s['parcel_contract_count']} / {s['total_method_count']}**",
        f"- Callback Binder ABIs ready: **{s['abi_ready_interface_count']} / {EXPECTED_CALLBACK_INTERFACE_COUNT}**",
        f"- Clean-room full Binder boundary ready: **{'YES' if s['clean_room_full_binder_boundary_ready'] else 'NO'}**", '',
        '| Callback | Methods | Stub | Proxy | Two-source | Parcel | ABI ready |',
        '|---|---:|---|---|---:|---:|---|',
    ]
    for c in result['callbacks']:
        md.append(f"| `{c['descriptor']}` | {c['method_count']} | {c['stub_selection']} | {c['proxy_selection']} | {c['two_source_agreement_count']}/{c['method_count']} | {c['parcel_contract_count']}/{c['method_count']} | {'YES' if c['abi_ready'] else 'NO'} |")
    md.extend(['', 'This closes only the static Binder transaction and Parcel boundary. It does not recover or claim Hi Rokid authorization policy, session/timing behavior, cloud behavior, or proprietary service implementation.'])
    (san / 'test21-r3-3-4-2-6-1-2-summary.md').write_text('\n'.join(md) + '\n')

    with (san / 'test21-r3-3-4-2-6-1-2-callback-interface-summary.tsv').open('w') as f:
        f.write('label\tdescriptor\tmethod_count\tstub_selection\tproxy_selection\ttwo_source_agreements\tmismatches\trequest_contracts\treply_contracts\tparcel_contracts\tabi_ready\n')
        for c in result['callbacks']:
            f.write(f"{c['label']}\t{c['descriptor']}\t{c['method_count']}\t{c['stub_selection']}\t{c['proxy_selection']}\t{c['two_source_agreement_count']}\t{c['transaction_mismatch_count']}\t{c['request_parcel_contract_count']}\t{c['reply_parcel_contract_count']}\t{c['parcel_contract_count']}\t{'YES' if c['abi_ready'] else 'NO'}\n")
    with (san / 'test21-r3-3-4-2-6-1-2-callback-transaction-map.tsv').open('w') as f:
        f.write('callback_label\tdescriptor\ttransaction_code\tmethod_name\tproto\tontransact_code\tproxy_code\ttwo_source_agreement\ttransact_flags\treply_mode\tparcel_contract\n')
        for c in result['callbacks']:
            for r in c['methods']:
                f.write(f"{c['label']}\t{c['descriptor']}\t{'' if r['transaction_code'] is None else r['transaction_code']}\t{r['name']}\t{r['proto']}\t{','.join(map(str,r['ontransact_codes']))}\t{','.join(map(str,r['proxy_codes']))}\t{'YES' if r['two_source_agreement'] else 'NO'}\t{','.join(map(str,r['transact_flags']))}\t{r['reply_mode']}\t{'YES' if r['parcel_contract_recovered'] else 'NO'}\n")
    with (san / 'test21-r3-3-4-2-6-1-2-callback-parcel-marshalling.tsv').open('w') as f:
        f.write('callback_label\tdescriptor\tmethod_name\tproto\ttransaction_code\ttransact_flags\treply_mode\trequest_operations\treply_operations\n')
        for c in result['callbacks']:
            for r in c['methods']:
                f.write(f"{c['label']}\t{c['descriptor']}\t{r['name']}\t{r['proto']}\t{'' if r['transaction_code'] is None else r['transaction_code']}\t{','.join(map(str,r['transact_flags']))}\t{r['reply_mode']}\t{' | '.join(r['request_operations'])}\t{' | '.join(r['reply_operations'])}\n")


def resolve_aar(explicit: str | None, home: Path) -> list[Path]:
    return P.resolve_aar(explicit, home)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--aar')
    ap.add_argument('--output', required=True)
    ap.add_argument('--fixture-mode', action='store_true')
    x = ap.parse_args()
    candidates = resolve_aar(x.aar, Path.home())
    if not candidates:
        raise SystemExit('ERROR: exact client-l 1.0.1 AAR not found in local Gradle/Maven cache; pass --aar <path>. No network or device access was attempted.')
    chosen = None
    if x.fixture_mode:
        chosen = candidates[0]
    else:
        for p in candidates:
            if p.is_file() and sha256_path(p) == EXPECTED_AAR_SHA256:
                chosen = p
                break
        if chosen is None:
            found = ', '.join(f'{p.name}:{sha256_path(p) if p.is_file() else "MISSING"}' for p in candidates)
            raise SystemExit('ERROR: no locally resolved AAR matches exact expected SHA-256. Candidates: ' + found)
    result = analyze_aar(chosen, fixture_mode=x.fixture_mode)
    write_outputs(result, Path(x.output).resolve())
    print((Path(x.output).resolve() / 'sanitized/test21-r3-3-4-2-6-1-2-summary.txt').read_text(), end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
