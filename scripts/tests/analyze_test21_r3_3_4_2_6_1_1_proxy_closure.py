#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

SCHEMA = 'rokid.test21-r3-3-4-2-6-1-1.obfuscation-resilient-proxy-closure.v1'
HERE = Path(__file__).resolve().parent
BASE_PATH = HERE / 'analyze_test21_r3_3_4_2_6_1_aar_contract.py'

spec = importlib.util.spec_from_file_location('r334261_base', BASE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError('unable to load accepted r3.3.4.2.6.1 analyzer')
B = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = B
spec.loader.exec_module(B)

EXPECTED_AAR_SHA256 = B.EXPECTED_AAR_SHA256
EXPECTED_COORDINATE = B.EXPECTED_COORDINATE
IFACE = B.IFACE
STUB = B.STUB
DESCRIPTOR = B.DESCRIPTOR
EXPECTED_METHODS = B.EXPECTED_METHODS
EXPECTED_METHOD_COUNT = B.EXPECTED_METHOD_COUNT
ACC_PUBLIC = B.ACC_PUBLIC
IBINDER_DESC = 'Landroid/os/IBinder;'


def sha256_path(path: Path) -> str:
    return B.sha256_path(path)


def class_super_name(cf: Any) -> str | None:
    try:
        if not cf.super_class:
            return None
        return cf.class_name(cf.super_class)
    except Exception:
        return None


def implements_iface(classes: dict[str, Any], cname: str, target: str, seen: set[str] | None = None) -> bool:
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
    if target in getattr(cf, 'interfaces', []):
        return True
    for iface in getattr(cf, 'interfaces', []):
        if implements_iface(classes, iface, target, seen):
            return True
    sup = class_super_name(cf)
    return bool(sup and implements_iface(classes, sup, target, seen))


def cp_has_descriptor(cf: Any) -> bool:
    for item in cf.cp:
        if not item:
            continue
        try:
            if item[0] == 'Utf8' and item[1] == DESCRIPTOR:
                return True
            if item[0] == 8 and cf.utf8(item[1]) == DESCRIPTOR:
                return True
        except Exception:
            pass
    return False


def method_signature_set(cf: Any) -> set[str]:
    return {m.name + m.desc for m in cf.methods if not m.name.startswith('<') and m.name != 'asBinder'}


def transact_call_count(cf: Any) -> int:
    count = 0
    for m in cf.methods:
        for ref in B.invoke_refs(cf, m):
            if ref['owner'] == 'android/os/IBinder' and ref['name'] == 'transact':
                count += 1
    return count


def structural_proxy_candidates(classes: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for cname, cf in classes.items():
        if cname in (IFACE, STUB):
            continue
        if not implements_iface(classes, cname, IFACE):
            continue
        sigs = method_signature_set(cf)
        matched = len(sigs & EXPECTED_METHODS)
        binder_fields = sum(1 for f in cf.fields if f.desc == IBINDER_DESC)
        tx_calls = transact_call_count(cf)
        descriptor_ref = cp_has_descriptor(cf)
        stub_related = cname.startswith(STUB + '$')
        # transact calls are decisive; the rest are tie-breakers/diagnostics.
        score = tx_calls * 1000 + matched * 20 + binder_fields * 10 + (5 if descriptor_ref else 0) + (1 if stub_related else 0)
        if tx_calls:
            rows.append({
                'class_name': cname,
                'implements_interface': True,
                'matching_interface_method_count': matched,
                'binder_field_count': binder_fields,
                'ibinder_transact_call_count': tx_calls,
                'descriptor_reference': descriptor_ref,
                'stub_related_name': stub_related,
                'score': score,
            })
    return sorted(rows, key=lambda r: (-r['score'], r['class_name']))


def select_structural_proxy(candidates: list[dict[str, Any]]) -> tuple[str | None, str]:
    if not candidates:
        return None, 'NO_IBINDER_TRANSACT_IMPLEMENTER_FOUND'
    top = candidates[0]
    tied = [r for r in candidates if r['score'] == top['score']]
    if len(tied) != 1:
        return None, 'AMBIGUOUS_TOP_STRUCTURAL_PROXY_CANDIDATES'
    if top['matching_interface_method_count'] != EXPECTED_METHOD_COUNT:
        return None, 'TOP_CANDIDATE_DOES_NOT_IMPLEMENT_EXACT_33_METHOD_SURFACE'
    return top['class_name'], 'UNIQUE_EXACT_STRUCTURAL_PROXY'


def invocation_ref(cf: Any, ins: Any) -> tuple[str, str, str, str] | None:
    if ins.op not in (0xb6, 0xb7, 0xb8, 0xb9) or ins.cp_index is None:
        return None
    return cf.member_ref(ins.cp_index)


def field_ref(cf: Any, ins: Any) -> tuple[str, str, str, str] | None:
    if ins.op not in (0xb2, 0xb3, 0xb4, 0xb5) or ins.cp_index is None:
        return None
    return cf.member_ref(ins.cp_index)


def recover_transact_code(cf: Any, insns: list[Any], tx_index: int) -> tuple[int | None, str]:
    # JVM evaluation order evaluates the IBinder receiver before transact args.
    # Locate the nearest preceding IBinder-typed field access, then choose the
    # first positive integer constant before invokeinterface transact(). This
    # survives obfuscated field names and absent TRANSACTION_* constants.
    start = max(0, tx_index - 96)
    binder_field_index = None
    for j in range(tx_index - 1, start - 1, -1):
        ref = field_ref(cf, insns[j])
        if ref and ref[2] == IBINDER_DESC:
            binder_field_index = j
            break
    lo = binder_field_index + 1 if binder_field_index is not None else start
    positives = [x.int_value for x in insns[lo:tx_index] if x.int_value is not None and 0 < x.int_value <= 65535]
    if positives:
        return positives[0], 'FIRST_POSITIVE_INT_AFTER_IBINDER_RECEIVER' if binder_field_index is not None else 'FALLBACK_FIRST_POSITIVE_INT'
    return None, 'NO_LITERAL_TRANSACTION_CODE_RECOVERED'


def proxy_contract_for_class(classes: dict[str, Any], proxy_class: str | None, methods: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    per_method: dict[str, Any] = {}
    diagnostics = {
        'proxy_class': proxy_class,
        'implemented_interface_method_count': 0,
        'transaction_method_count': 0,
        'request_contract_count': 0,
        'reply_contract_count': 0,
        'parcel_contract_count': 0,
    }
    if proxy_class is None:
        return per_method, diagnostics
    cf = classes[proxy_class]
    by_sig = {(m.name, m.desc): m for m in cf.methods}
    for item in methods:
        sig = item['signature']
        m = by_sig.get((item['name'], item['proto']))
        row = {
            'method_found': bool(m),
            'transaction_codes': [],
            'transaction_code_recovery': [],
            'request_operations': [],
            'reply_operations': [],
            'request_contract_recovered': False,
            'reply_contract_recovered': False,
            'parcel_contract_recovered': False,
        }
        if m:
            diagnostics['implemented_interface_method_count'] += 1
        if not m or not m.code:
            per_method[sig] = row
            continue
        insns = B.decode(m.code, cf)
        tx_indices: list[int] = []
        tx_codes: list[int] = []
        tx_recovery: list[str] = []
        for idx, ins in enumerate(insns):
            ref = invocation_ref(cf, ins)
            if ref and ref[0] == 'android/os/IBinder' and ref[1] == 'transact':
                tx_indices.append(idx)
                code, how = recover_transact_code(cf, insns, idx)
                if code is not None:
                    tx_codes.append(code)
                tx_recovery.append(how)
        row['transaction_codes'] = sorted(set(tx_codes))
        row['transaction_code_recovery'] = tx_recovery
        if len(row['transaction_codes']) == 1:
            diagnostics['transaction_method_count'] += 1
        first_tx = tx_indices[0] if tx_indices else None
        req_ops: list[str] = []
        reply_ops: list[str] = []
        for idx, ins in enumerate(insns):
            ref = invocation_ref(cf, ins)
            if not ref or ref[0] != 'android/os/Parcel':
                continue
            opname = ref[1] + ref[2]
            if first_tx is None or idx < first_tx:
                if ref[1].startswith('write'):
                    req_ops.append(opname)
            elif idx > first_tx:
                if ref[1].startswith('read'):
                    reply_ops.append(opname)
        row['request_operations'] = req_ops
        row['reply_operations'] = reply_ops
        request_ok = any(x.startswith('writeInterfaceToken') for x in req_ops)
        reply_ok = any(x.startswith('readException') for x in reply_ops)
        row['request_contract_recovered'] = request_ok and len(row['transaction_codes']) == 1
        row['reply_contract_recovered'] = reply_ok and len(row['transaction_codes']) == 1
        row['parcel_contract_recovered'] = row['request_contract_recovered'] and row['reply_contract_recovered']
        diagnostics['request_contract_count'] += int(row['request_contract_recovered'])
        diagnostics['reply_contract_count'] += int(row['reply_contract_recovered'])
        diagnostics['parcel_contract_count'] += int(row['parcel_contract_recovered'])
        per_method[sig] = row
    return per_method, diagnostics


def wrapper_bridges(classes: dict[str, Any], methods: list[dict[str, Any]], proxy_class: str | None) -> list[dict[str, Any]]:
    valid = {(x['name'], x['proto']): x['signature'] for x in methods}
    bridges = []
    for cf in classes.values():
        if cf.name in (IFACE, STUB, proxy_class) or cf.name.startswith(STUB + '$'):
            continue
        for m in cf.methods:
            for ref in B.invoke_refs(cf, m):
                if ref['owner'] != IFACE:
                    continue
                sig = valid.get((ref['name'], ref['desc']))
                if not sig:
                    continue
                bridges.append({
                    'caller_class': cf.name.replace('/', '.'),
                    'caller_method': m.name,
                    'caller_proto': m.desc,
                    'caller_public': bool(m.access & ACC_PUBLIC),
                    'binder_signature': sig,
                })
    unique = {(b['caller_class'], b['caller_method'], b['caller_proto'], b['binder_signature']): b for b in bridges}
    return sorted(unique.values(), key=lambda b: (b['binder_signature'], b['caller_class'], b['caller_method']))


def structural_facades(bridges: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for b in bridges:
        grouped[b['caller_class']].append(b)
    out = {}
    for cname, rows in grouped.items():
        public_rows = [r for r in rows if r['caller_public']]
        unique_targets = {r['binder_signature'] for r in public_rows}
        if len(unique_targets) >= 3:
            out[cname] = {
                'public_direct_bridge_count': len(public_rows),
                'public_unique_binder_method_count': len(unique_targets),
                'classification': 'PUBLIC_STRUCTURAL_BINDER_FACADE',
            }
    return out


def build_call_graph(classes: dict[str, Any]) -> tuple[dict[str, set[str]], dict[str, Any]]:
    return B.build_call_graph(classes)


def public_root_paths(classes: dict[str, Any], methods: list[dict[str, Any]], bridges: list[dict[str, Any]], facades: dict[str, dict[str, Any]], max_depth: int = 8) -> dict[str, list[str]]:
    edges, info = build_call_graph(classes)
    reverse: dict[str, set[str]] = defaultdict(set)
    for src, targets in edges.items():
        for t in targets:
            reverse[t].add(src)
    direct_by_sig: dict[str, list[str]] = defaultdict(list)
    for b in bridges:
        node = f"{b['caller_class'].replace('.', '/')}->{b['caller_method']}{b['caller_proto']}"
        direct_by_sig[b['binder_signature']].append(node)
    roots: dict[str, list[str]] = {}
    facade_internal = {c.replace('.', '/') for c in facades}
    for item in methods:
        sig = item['signature']
        q = deque((n, [n]) for n in direct_by_sig.get(sig, []))
        seen = {n for n, _ in q}
        best: list[str] = []
        while q:
            node, path = q.popleft()
            mi = info.get(node)
            if mi and (mi.access & ACC_PUBLIC) and (mi.owner in facade_internal or mi.owner.startswith('com/rokid/cxr/')):
                best = list(reversed(path))
                break
            if len(path) >= max_depth:
                continue
            for parent in sorted(reverse.get(node, ())):
                if parent not in seen:
                    seen.add(parent)
                    q.append((parent, path + [parent]))
        roots[sig] = best
    return roots


def merge(methods: list[dict[str, Any]], on_codes: dict[str, list[int]], proxy_contract: dict[str, Any], bridges: list[dict[str, Any]], roots: dict[str, list[str]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = []
    mismatch_count = 0
    agreement_count = 0
    canonical_codes = []
    bridge_targets = {b['binder_signature'] for b in bridges}
    public_direct_targets = {b['binder_signature'] for b in bridges if b['caller_public']}
    for m in methods:
        sig = m['signature']
        pc = proxy_contract.get(sig, {})
        proxy_codes = pc.get('transaction_codes', [])
        stub_codes = on_codes.get(sig, [])
        sources = {}
        if stub_codes:
            sources['onTransact'] = stub_codes
        if proxy_codes:
            sources['proxy'] = proxy_codes
        flat = {x for vals in sources.values() for x in vals}
        mismatch = len(flat) > 1 or any(len(vals) != 1 for vals in sources.values())
        if mismatch:
            mismatch_count += 1
        agreement = len(sources) >= 2 and not mismatch
        agreement_count += int(agreement)
        code = next(iter(flat)) if len(flat) == 1 else None
        if code is not None:
            canonical_codes.append(code)
        rows.append({
            'name': m['name'],
            'proto': m['proto'],
            'signature': sig,
            'transaction_code': code,
            'ontransact_codes': stub_codes,
            'proxy_codes': proxy_codes,
            'two_source_agreement': agreement,
            'request_contract_recovered': bool(pc.get('request_contract_recovered')),
            'reply_contract_recovered': bool(pc.get('reply_contract_recovered')),
            'parcel_contract_recovered': bool(pc.get('parcel_contract_recovered')),
            'request_operations': pc.get('request_operations', []),
            'reply_operations': pc.get('reply_operations', []),
            'sdk_direct_bridge': sig in bridge_targets,
            'sdk_public_direct_bridge': sig in public_direct_targets,
            'sdk_public_root_found': bool(roots.get(sig)),
        })
    unique_codes = len(set(canonical_codes))
    on_complete = sum(1 for r in rows if len(r['ontransact_codes']) == 1)
    proxy_complete = sum(1 for r in rows if len(r['proxy_codes']) == 1)
    req_count = sum(1 for r in rows if r['request_contract_recovered'])
    rep_count = sum(1 for r in rows if r['reply_contract_recovered'])
    parcel_count = sum(1 for r in rows if r['parcel_contract_recovered'])
    tx_ready = (
        len(rows) == EXPECTED_METHOD_COUNT
        and on_complete == EXPECTED_METHOD_COUNT
        and proxy_complete == EXPECTED_METHOD_COUNT
        and agreement_count == EXPECTED_METHOD_COUNT
        and mismatch_count == 0
        and unique_codes == EXPECTED_METHOD_COUNT
    )
    parcel_ready = req_count == EXPECTED_METHOD_COUNT and rep_count == EXPECTED_METHOD_COUNT and parcel_count == EXPECTED_METHOD_COUNT
    return rows, {
        'ontransact_map_complete': on_complete == EXPECTED_METHOD_COUNT,
        'ontransact_transaction_method_count': on_complete,
        'proxy_transaction_map_complete': proxy_complete == EXPECTED_METHOD_COUNT,
        'proxy_transaction_method_count': proxy_complete,
        'proxy_ontransact_agreement_count': agreement_count,
        'proxy_ontransact_mismatch_count': mismatch_count,
        'transaction_unique_code_count': unique_codes,
        'transaction_contract_ready': tx_ready,
        'parcel_request_contract_count': req_count,
        'parcel_reply_contract_count': rep_count,
        'parcel_contract_recovered_method_count': parcel_count,
        'parcel_contract_ready': parcel_ready,
    }


def analyze_aar(aar: Path, fixture_mode: bool = False) -> dict[str, Any]:
    digest = sha256_path(aar)
    if not fixture_mode and digest != EXPECTED_AAR_SHA256:
        raise ValueError(f'AAR SHA-256 mismatch expected={EXPECTED_AAR_SHA256} actual={digest}')
    classes, classes_jar_sha = B.load_aar(aar)
    methods = B.interface_methods(classes)
    method_set = {m['signature'] for m in methods}
    iface_exact = method_set == EXPECTED_METHODS
    descriptor_exact = DESCRIPTOR in B.descriptor_evidence(classes)
    on_codes = B.ontransact_map(classes, methods)
    candidates = structural_proxy_candidates(classes)
    proxy_class, proxy_disposition = select_structural_proxy(candidates)
    proxy_contract, proxy_diag = proxy_contract_for_class(classes, proxy_class, methods)
    bridges = wrapper_bridges(classes, methods, proxy_class)
    facades = structural_facades(bridges)
    roots = public_root_paths(classes, methods, bridges, facades)
    rows, closure = merge(methods, on_codes, proxy_contract, bridges, roots)

    direct_targets = {b['binder_signature'] for b in bridges}
    public_direct_targets = {b['binder_signature'] for b in bridges if b['caller_public']}
    root_targets = {sig for sig, p in roots.items() if p}
    structural_proxy_found = proxy_class is not None
    interface_ready = iface_exact and STUB in classes and structural_proxy_found and descriptor_exact
    binder_abi_ready = interface_ready and closure['transaction_contract_ready'] and closure['parcel_contract_ready']
    if binder_abi_ready:
        disposition = 'TWO_SOURCE_BINDER_TRANSACTION_AND_CLIENT_PARCEL_ABI_CLOSED_NO_VENDOR_BEHAVIOR_CLAIM'
    elif structural_proxy_found:
        disposition = 'STRUCTURAL_PROXY_FOUND_BUT_EXACT_TWO_SOURCE_OR_PARCEL_CLOSURE_INCOMPLETE'
    else:
        disposition = 'STRUCTURAL_PROXY_NOT_EXACTLY_IDENTIFIED_STATIC_CLOSURE_INCOMPLETE'

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
        'interface': {
            'descriptor': DESCRIPTOR,
            'descriptor_exact': descriptor_exact,
            'method_count': len(methods),
            'signature_set_exact': iface_exact,
            'missing_signatures': sorted(EXPECTED_METHODS - method_set),
            'extra_signatures': sorted(method_set - EXPECTED_METHODS),
        },
        'stub': {
            'class_present': STUB in classes,
        },
        'proxy_discovery': {
            'literal_proxy_class_present': (STUB + '$Proxy') in classes,
            'candidate_count': len(candidates),
            'structural_proxy_found': structural_proxy_found,
            'selected_proxy_class': proxy_class,
            'selection_disposition': proxy_disposition,
            'candidates': candidates,
            **proxy_diag,
        },
        'transactions': closure,
        'sdk_wrapper_bridge': {
            'direct_bridge_count': len(bridges),
            'direct_reachable_binder_method_count': len(direct_targets),
            'public_direct_reachable_binder_method_count': len(public_direct_targets),
            'public_root_reachable_binder_method_count': len(root_targets),
            'structural_facade_count': len(facades),
            'structural_facades': facades,
        },
        'method_contract': rows,
        'bridges': bridges,
        'clean_room': {
            'interface_scaffold_ready': interface_ready,
            'transaction_contract_ready': closure['transaction_contract_ready'],
            'parcel_contract_ready': closure['parcel_contract_ready'],
            'binder_abi_ready': binder_abi_ready,
            'functional_behavior_compatibility_proven': False,
            'authorization_semantics_recovered': False,
            'session_lifecycle_semantics_recovered': False,
            'service_implementation_recovered': False,
            'replacement_boundary': 'BINDER_ABI_AND_CLIENT_MARSHALLING_ONLY_NO_PROPRIETARY_SERVICE_BEHAVIOR',
            'disposition': disposition,
        },
        'device_operation': 'NONE',
        'photo_operation': 'NONE',
        'audio_operation': 'NONE',
        'network_capture': 'NONE',
    }


def sanitized(result: dict[str, Any]) -> dict[str, Any]:
    out = json.loads(json.dumps(result))
    # Keep exact API/ABI facts and method-level Parcel operation sequences.
    # Remove private call-graph paths; no local filesystem path is ever stored.
    return out


def write_outputs(result: dict[str, Any], output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    san = output / 'sanitized'
    san.mkdir(exist_ok=True)
    (output / 'r3342611-private-analysis.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    s = sanitized(result)
    (san / 'test21-r3-3-4-2-6-1-1-summary.json').write_text(json.dumps(s, indent=2, sort_keys=True) + '\n')
    inp = s['input']; iface = s['interface']; pd = s['proxy_discovery']; tx = s['transactions']; br = s['sdk_wrapper_bridge']; cr = s['clean_room']
    lines = [
        'TEST21_R3_3_4_2_6_1_1_ANALYSIS=PASS',
        'ACCESS_MODE=HOST_ONLY_LOCAL_AAR', 'ROOT_REQUIRED=NO', 'MAGISK_REQUIRED=NO', 'ADB_REQUIRED=NO', 'FRIDA_REQUIRED=NO', 'PHONE_ACTION=NONE', 'NETWORK_REQUIRED=NO',
        'AAR_COORDINATE=' + inp['coordinate'], 'AAR_SHA256=' + inp['aar_sha256'], 'AAR_IDENTITY=' + inp['aar_identity'],
        'BINDER_INTERFACE_DESCRIPTOR=' + iface['descriptor'], 'BINDER_DESCRIPTOR_EXACT=' + ('YES' if iface['descriptor_exact'] else 'NO'),
        f"BINDER_INTERFACE_METHOD_COUNT={iface['method_count']}", 'BINDER_SIGNATURE_SET_EXACT=' + ('YES' if iface['signature_set_exact'] else 'NO'),
        'STUB_CLASS_PRESENT=' + ('YES' if s['stub']['class_present'] else 'NO'),
        'LITERAL_PROXY_CLASS_PRESENT=' + ('YES' if pd['literal_proxy_class_present'] else 'NO'),
        f"STRUCTURAL_PROXY_CANDIDATE_COUNT={pd['candidate_count']}",
        'STRUCTURAL_PROXY_FOUND=' + ('YES' if pd['structural_proxy_found'] else 'NO'),
        'STRUCTURAL_PROXY_SELECTION=' + pd['selection_disposition'],
        f"PROXY_IMPLEMENTED_BINDER_METHOD_COUNT={pd['implemented_interface_method_count']}",
        f"PROXY_IBINDER_TRANSACTION_METHOD_COUNT={pd['transaction_method_count']}",
        'ONTRANSACT_MAP_COMPLETE=' + ('YES' if tx['ontransact_map_complete'] else 'NO'),
        f"ONTRANSACT_TRANSACTION_METHOD_COUNT={tx['ontransact_transaction_method_count']}",
        'PROXY_TRANSACTION_MAP_COMPLETE=' + ('YES' if tx['proxy_transaction_map_complete'] else 'NO'),
        f"PROXY_TRANSACTION_METHOD_COUNT={tx['proxy_transaction_method_count']}",
        f"PROXY_ONTRANSACT_AGREEMENT_COUNT={tx['proxy_ontransact_agreement_count']}",
        f"PROXY_ONTRANSACT_MISMATCH_COUNT={tx['proxy_ontransact_mismatch_count']}",
        f"TRANSACTION_UNIQUE_CODE_COUNT={tx['transaction_unique_code_count']}",
        f"PARCEL_REQUEST_CONTRACT_COUNT={tx['parcel_request_contract_count']}",
        f"PARCEL_REPLY_CONTRACT_COUNT={tx['parcel_reply_contract_count']}",
        f"PARCEL_CONTRACT_RECOVERED_METHOD_COUNT={tx['parcel_contract_recovered_method_count']}",
        f"SDK_DIRECT_BINDER_BRIDGE_COUNT={br['direct_bridge_count']}",
        f"SDK_DIRECT_REACHABLE_BINDER_METHOD_COUNT={br['direct_reachable_binder_method_count']}",
        f"SDK_PUBLIC_DIRECT_REACHABLE_BINDER_METHOD_COUNT={br['public_direct_reachable_binder_method_count']}",
        f"SDK_PUBLIC_ROOT_REACHABLE_BINDER_METHOD_COUNT={br['public_root_reachable_binder_method_count']}",
        f"SDK_STRUCTURAL_FACADE_COUNT={br['structural_facade_count']}",
        'CLEAN_ROOM_INTERFACE_SCAFFOLD_READY=' + ('YES' if cr['interface_scaffold_ready'] else 'NO'),
        'CLEAN_ROOM_TRANSACTION_CONTRACT_READY=' + ('YES' if cr['transaction_contract_ready'] else 'NO'),
        'CLEAN_ROOM_PARCEL_CONTRACT_READY=' + ('YES' if cr['parcel_contract_ready'] else 'NO'),
        'CLEAN_ROOM_BINDER_ABI_READY=' + ('YES' if cr['binder_abi_ready'] else 'NO'),
        'FUNCTIONAL_BEHAVIOR_COMPATIBILITY_PROVEN=NO', 'AUTHORIZATION_SEMANTICS_RECOVERED=NO', 'SESSION_LIFECYCLE_SEMANTICS_RECOVERED=NO', 'SERVICE_IMPLEMENTATION_RECOVERED=NO',
        'CLEAN_ROOM_DISPOSITION=' + cr['disposition'], 'DEVICE_OPERATION=NONE', 'PHOTO_OPERATION=NONE', 'AUDIO_OPERATION=NONE', 'NETWORK_CAPTURE=NONE',
    ]
    (san / 'test21-r3-3-4-2-6-1-1-summary.txt').write_text('\n'.join(lines) + '\n')
    md = [
        '# Test 21 r3.3.4.2.6.1.1 — obfuscation-resilient Binder Proxy closure', '',
        f"- AAR identity: **{inp['aar_identity']}** (`{inp['aar_sha256']}`)",
        f"- Exact 33-method Binder interface: **{'YES' if iface['signature_set_exact'] else 'NO'}**",
        f"- Literal `$Proxy` present: **{'YES' if pd['literal_proxy_class_present'] else 'NO'}**",
        f"- Structurally identified Proxy: **{'YES' if pd['structural_proxy_found'] else 'NO'}**",
        f"- Stub `onTransact` map: **{tx['ontransact_transaction_method_count']} / {EXPECTED_METHOD_COUNT}**",
        f"- Proxy transaction map: **{tx['proxy_transaction_method_count']} / {EXPECTED_METHOD_COUNT}**",
        f"- Stub/Proxy exact agreements: **{tx['proxy_ontransact_agreement_count']} / {EXPECTED_METHOD_COUNT}**; mismatches **{tx['proxy_ontransact_mismatch_count']}**",
        f"- Request Parcel contracts: **{tx['parcel_request_contract_count']} / {EXPECTED_METHOD_COUNT}**",
        f"- Reply Parcel contracts: **{tx['parcel_reply_contract_count']} / {EXPECTED_METHOD_COUNT}**",
        f"- Public wrapper direct reachability: **{br['public_direct_reachable_binder_method_count']}** Binder methods",
        f"- Clean-room Binder ABI ready: **{'YES' if cr['binder_abi_ready'] else 'NO'}**", '',
        'This is static, host-only Binder ABI and client-marshalling evidence. It does not recover or claim Hi Rokid authorization policy, session/timing behavior, cloud behavior, or proprietary service implementation.',
    ]
    (san / 'test21-r3-3-4-2-6-1-1-summary.md').write_text('\n'.join(md) + '\n')

    with (san / 'test21-r3-3-4-2-6-1-1-transaction-map.tsv').open('w') as f:
        f.write('transaction_code\tmethod_name\tproto\tontransact_code\tproxy_code\ttwo_source_agreement\trequest_contract\treply_contract\tparcel_contract\tsdk_direct_bridge\tsdk_public_root\n')
        for r in result['method_contract']:
            oc = ','.join(map(str, r['ontransact_codes'])); pc = ','.join(map(str, r['proxy_codes']))
            f.write(f"{'' if r['transaction_code'] is None else r['transaction_code']}\t{r['name']}\t{r['proto']}\t{oc}\t{pc}\t{'YES' if r['two_source_agreement'] else 'NO'}\t{'YES' if r['request_contract_recovered'] else 'NO'}\t{'YES' if r['reply_contract_recovered'] else 'NO'}\t{'YES' if r['parcel_contract_recovered'] else 'NO'}\t{'YES' if r['sdk_direct_bridge'] else 'NO'}\t{'YES' if r['sdk_public_root_found'] else 'NO'}\n")

    with (san / 'test21-r3-3-4-2-6-1-1-parcel-marshalling.tsv').open('w') as f:
        f.write('method_name\tproto\ttransaction_code\trequest_operations\treply_operations\n')
        for r in result['method_contract']:
            f.write(f"{r['name']}\t{r['proto']}\t{'' if r['transaction_code'] is None else r['transaction_code']}\t{' | '.join(r['request_operations'])}\t{' | '.join(r['reply_operations'])}\n")

    with (san / 'test21-r3-3-4-2-6-1-1-sdk-wrapper-bridge.tsv').open('w') as f:
        f.write('caller_class\tcaller_method\tcaller_proto\tbinder_signature\tcaller_public\n')
        for b in result['bridges']:
            f.write(f"{b['caller_class']}\t{b['caller_method']}\t{b['caller_proto']}\t{b['binder_signature']}\t{'YES' if b['caller_public'] else 'NO'}\n")


def resolve_aar(explicit: str | None, home: Path) -> list[Path]:
    return B.resolve_aar(explicit, home)


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
    print((Path(x.output).resolve() / 'sanitized/test21-r3-3-4-2-6-1-1-summary.txt').read_text(), end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
