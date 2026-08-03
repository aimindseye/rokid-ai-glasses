#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import struct
from collections import deque
from pathlib import Path
from typing import Any

SCHEMA = 'rokid.test21-r3-3-4-2-6.privilege-free-binder-contract.v1'
CUSTOM_PREFIX = 'Lorg/aimindseye/rokid/cxrphotoqualification/'
EXPECTED_DESCRIPTOR = 'com.rokid.sprite.aiapp.externalapp.IMediaStreamService'
EXPECTED_AAR_SHA256 = 'c23d34b3adc60d3fa16001645ce6172eaf4554173e7ef9c078595e672d50824e'
EXPECTED_METHOD_COUNT = 33


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def load_base(repo: Path):
    path = repo / 'scripts/tests/analyze_test21_r3_3_4_2_static_contract.py'
    spec = importlib.util.spec_from_file_location('test21_r3342_base', path)
    if spec is None or spec.loader is None:
        raise RuntimeError('unable to load r3.3.4.2 base analyzer')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def read_uleb(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    shift = 0
    for _ in range(5):
        if offset >= len(data):
            raise ValueError('truncated uleb128')
        b = data[offset]
        offset += 1
        value |= (b & 0x7F) << shift
        if not (b & 0x80):
            return value, offset
        shift += 7
    raise ValueError('invalid uleb128')


def signed_value(raw: bytes) -> int:
    if not raw:
        return 0
    value = int.from_bytes(raw, 'little', signed=False)
    bits = 8 * len(raw)
    if raw[-1] & 0x80:
        value -= 1 << bits
    return value


def parse_encoded_value(data: bytes, offset: int) -> tuple[Any, int]:
    if offset >= len(data):
        raise ValueError('truncated encoded_value')
    header = data[offset]
    offset += 1
    value_type = header & 0x1F
    value_arg = header >> 5
    n = value_arg + 1

    if value_type in (0x00, 0x02, 0x04, 0x06):  # byte, short, int, long
        raw = data[offset:offset + n]
        if len(raw) != n:
            raise ValueError('truncated integer encoded_value')
        return signed_value(raw), offset + n
    if value_type == 0x03:  # char
        raw = data[offset:offset + n]
        if len(raw) != n:
            raise ValueError('truncated char encoded_value')
        return int.from_bytes(raw, 'little', signed=False), offset + n
    if value_type in (0x17, 0x18, 0x19, 0x1A, 0x1B):  # string/type/field/method/enum index
        raw = data[offset:offset + n]
        if len(raw) != n:
            raise ValueError('truncated index encoded_value')
        return {'kind': 'index', 'value_type': value_type, 'index': int.from_bytes(raw, 'little')}, offset + n
    if value_type == 0x1E:  # null
        return None, offset
    if value_type == 0x1F:  # boolean, value_arg is value
        return bool(value_arg), offset
    raise ValueError(f'unsupported encoded_value type 0x{value_type:02x}')


def static_field_values(dex) -> dict[tuple[str, str, str], Any]:
    """Return {(class_desc, field_name, field_type): value} for encoded static values."""
    data = dex.data
    class_count = struct.unpack_from('<I', data, 0x60)[0]
    class_off = struct.unpack_from('<I', data, 0x64)[0]
    out: dict[tuple[str, str, str], Any] = {}

    for i in range(class_count):
        vals = struct.unpack_from('<IIIIIIII', data, class_off + 32 * i)
        class_idx, _access, _super_idx, _interfaces_off, _source_idx, _annotations_off, class_data_off, static_values_off = vals
        class_desc = dex.types[class_idx]
        if not class_data_off:
            continue

        p = class_data_off
        static_fields_size, p = read_uleb(data, p)
        instance_fields_size, p = read_uleb(data, p)
        direct_methods_size, p = read_uleb(data, p)
        virtual_methods_size, p = read_uleb(data, p)
        del direct_methods_size, virtual_methods_size

        static_field_indices: list[int] = []
        field_idx = 0
        for _ in range(static_fields_size):
            diff, p = read_uleb(data, p)
            _flags, p = read_uleb(data, p)
            field_idx += diff
            static_field_indices.append(field_idx)

        # Skip instance fields; static-values array only corresponds to static fields.
        field_idx = 0
        for _ in range(instance_fields_size):
            diff, p = read_uleb(data, p)
            _flags, p = read_uleb(data, p)
            field_idx += diff

        values: list[Any] = []
        if static_values_off:
            q = static_values_off
            count, q = read_uleb(data, q)
            for _ in range(count):
                value, q = parse_encoded_value(data, q)
                values.append(value)

        for n, idx in enumerate(static_field_indices):
            f = dex.fields[idx]
            value = values[n] if n < len(values) else 0
            out[(class_desc, f['name'], f['type'])] = value
    return out


def transaction_fields(model, iface_desc: str) -> list[dict[str, Any]]:
    stub = iface_desc[:-1] + '$Stub;'
    records: list[dict[str, Any]] = []
    for dex in model.dexes:
        try:
            values = static_field_values(dex)
        except Exception:
            continue
        for (owner, name, typ), value in values.items():
            if owner != stub or not name.startswith('TRANSACTION_') or typ != 'I':
                continue
            if not isinstance(value, int):
                continue
            records.append({
                'stub_class': owner,
                'field': name,
                'method_name': name[len('TRANSACTION_'):],
                'transaction_code': value,
                'source_dex': dex.name,
            })
    by_key = {(r['field'], r['transaction_code']): r for r in records}
    return sorted(by_key.values(), key=lambda r: (r['transaction_code'], r['field']))


def shortest_root_path(model, target: str, root_prefix: str = CUSTOM_PREFIX, max_depth: int = 12) -> list[str]:
    q = deque([(target, [target])])
    seen = {target}
    while q:
        current, backward_path = q.popleft()
        if len(backward_path) > 1 and current.startswith(root_prefix):
            return list(reversed(backward_path))
        if len(backward_path) >= max_depth:
            continue
        for parent in sorted(model.reverse.get(current, ())):
            if parent in seen:
                continue
            seen.add(parent)
            q.append((parent, backward_path + [parent]))
    return []


def direct_invoke_count(model, target: str, caller_prefix: str = CUSTOM_PREFIX) -> int:
    count = 0
    for caller, invokes in model.invoke_edges.items():
        if caller.startswith(caller_prefix) and target in invokes:
            count += 1
    return count


def proxy_transaction_codes(base, model, iface_desc: str, methods: list[dict[str, Any]]) -> list[dict[str, Any]]:
    proxy_desc = iface_desc[:-1] + '$Stub$Proxy;'
    out = []
    for item in methods:
        name = item['name']
        proto = item['proto']
        matches = [m for m in model.methods_of(proxy_desc, name) if m['proto'] == proto]
        codes: list[int] = []
        for m in matches:
            try:
                sim = base.simulate(model, m, {})
            except Exception:
                continue
            for event in sim.get('events', []):
                invoke = event.get('invoke', '')
                if not invoke.startswith('Landroid/os/IBinder;->transact('):
                    continue
                args = event.get('args') or []
                if len(args) < 2:
                    continue
                code = args[1]
                if isinstance(code, dict) and code.get('kind') == 'int' and isinstance(code.get('value'), int):
                    codes.append(code['value'])
        out.append({
            'method_name': name,
            'proto': proto,
            'proxy_class': proxy_desc,
            'proxy_method_found': bool(matches),
            'transaction_codes_observed': sorted(set(codes)),
        })
    return out


def parse_type_descriptors(proto: str) -> tuple[list[str], str]:
    if not proto.startswith('(') or ')' not in proto:
        return [], 'UNRESOLVED'
    params_text, ret = proto[1:].split(')', 1)
    params: list[str] = []
    i = 0
    while i < len(params_text):
        start = i
        while i < len(params_text) and params_text[i] == '[':
            i += 1
        if i >= len(params_text):
            break
        if params_text[i] == 'L':
            end = params_text.find(';', i)
            if end < 0:
                break
            i = end + 1
        else:
            i += 1
        params.append(params_text[start:i])
    return params, ret


def classify_type(desc: str) -> str:
    core = desc
    while core.startswith('['):
        core = core[1:]
    if core in {'V', 'Z', 'B', 'S', 'C', 'I', 'J', 'F', 'D'}:
        return 'PRIMITIVE'
    if core.startswith('Ljava/') or core.startswith('Ljavax/') or core.startswith('Lkotlin/'):
        return 'LANGUAGE_RUNTIME'
    if core.startswith('Landroid/') or core.startswith('Landroidx/'):
        return 'ANDROID_FRAMEWORK'
    if core.startswith('Lcom/rokid/'):
        return 'ROKID_API_TYPE'
    return 'OTHER_REFERENCE_TYPE'


def method_type_inventory(methods: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for method in methods:
        params, ret = parse_type_descriptors(method['proto'])
        for role, desc in [('RETURN', ret)] + [('PARAM', p) for p in params]:
            if desc == 'V':
                continue
            key = desc
            rec = seen.setdefault(key, {
                'descriptor': desc,
                'classification': classify_type(desc),
                'roles': set(),
                'method_names': set(),
            })
            rec['roles'].add(role)
            rec['method_names'].add(method['name'])
    out = []
    for rec in seen.values():
        out.append({
            'descriptor': rec['descriptor'],
            'classification': rec['classification'],
            'roles': sorted(rec['roles']),
            'method_names': sorted(rec['method_names']),
        })
    return sorted(out, key=lambda r: (r['classification'], r['descriptor']))


def build_from_fixture(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text())
    return {
        'descriptor': raw['descriptor'],
        'methods': raw['methods'],
        'transactions': raw['transactions'],
        'proxy': raw.get('proxy', []),
        'reachability': raw.get('reachability', []),
        'types': raw.get('types', method_type_inventory(raw['methods'])),
        'input': {'fixture_mode': True},
    }


def build_from_evidence(repo: Path, r3341_evidence: Path) -> dict[str, Any]:
    base = load_base(repo)
    apkdir = r3341_evidence / 'raw/apks'
    custom = base.apk_pick(apkdir, 'custom')
    if not custom:
        raise SystemExit('ERROR: r3.3.4.1 custom APK input not found under raw/apks')

    model = base.Model()
    model.add_apk(custom)

    sc = base.service_connection_classes(model)
    sc_desc = base.descriptor_candidates_from_sc(sc)
    descriptors = sorted({x['descriptor'] for x in sc_desc if x.get('descriptor')})
    descriptor = descriptors[0] if len(descriptors) == 1 else None
    if not descriptor:
        # The exact descriptor is an accepted r3.3.4.2 result, but this analyzer
        # refuses to hard-code it as proof when the current input cannot recover it.
        raise SystemExit('ERROR: exact Binder descriptor could not be uniquely recovered from the supplied custom APK')

    iface_desc = 'L' + descriptor.replace('.', '/') + ';'
    methods = base.interface_methods(model, iface_desc)
    transactions = transaction_fields(model, iface_desc)
    proxy = proxy_transaction_codes(base, model, iface_desc, methods)

    reachability = []
    for m in methods:
        target = iface_desc + '->' + m['name'] + m['proto']
        path = shortest_root_path(model, target)
        reachability.append({
            'method_name': m['name'],
            'proto': m['proto'],
            'target': target,
            'reachable_from_custom_app': bool(path),
            'shortest_call_path': path,
            'direct_custom_callsite_count': direct_invoke_count(model, target),
        })

    return {
        'descriptor': descriptor,
        'methods': methods,
        'transactions': transactions,
        'proxy': proxy,
        'reachability': reachability,
        'types': method_type_inventory(methods),
        'input': {
            'fixture_mode': False,
            'custom_apk_sha256': sha256_path(custom),
            'custom_apk_bytes': custom.stat().st_size,
        },
    }


def analyze(contract: dict[str, Any]) -> dict[str, Any]:
    descriptor = contract['descriptor']
    methods = sorted(contract['methods'], key=lambda m: (m['name'], m['proto']))
    transactions = sorted(contract['transactions'], key=lambda r: (r['transaction_code'], r['method_name']))
    proxy = contract.get('proxy', [])
    reachability = contract.get('reachability', [])

    method_names = [m['name'] for m in methods]
    tx_by_method: dict[str, list[int]] = {}
    for tx in transactions:
        tx_by_method.setdefault(tx['method_name'], []).append(int(tx['transaction_code']))

    missing_tx = sorted([name for name in method_names if len(tx_by_method.get(name, [])) != 1])
    extra_tx = sorted([name for name in tx_by_method if name not in set(method_names)])
    codes = [int(tx['transaction_code']) for tx in transactions]
    unique_codes = sorted(set(codes))
    duplicate_code_count = len(codes) - len(unique_codes)
    transaction_map_complete = not missing_tx and not extra_tx and duplicate_code_count == 0 and len(transactions) == len(methods)
    contiguous = bool(unique_codes) and unique_codes == list(range(min(unique_codes), max(unique_codes) + 1))

    proxy_mismatches = []
    proxy_confirmed = 0
    proxy_by_key = {(p['method_name'], p['proto']): p for p in proxy}
    for m in methods:
        p = proxy_by_key.get((m['name'], m['proto']))
        expected = tx_by_method.get(m['name'], [])
        observed = [] if not p else [int(x) for x in p.get('transaction_codes_observed', [])]
        if p and len(expected) == 1 and observed == expected:
            proxy_confirmed += 1
        elif p and observed:
            proxy_mismatches.append({
                'method_name': m['name'],
                'proto': m['proto'],
                'field_codes': expected,
                'proxy_codes': observed,
            })

    reachable = sorted([r for r in reachability if r.get('reachable_from_custom_app')], key=lambda r: (r['method_name'], r['proto']))
    unreachable = sorted([r for r in reachability if not r.get('reachable_from_custom_app')], key=lambda r: (r['method_name'], r['proto']))

    exact_descriptor = descriptor == EXPECTED_DESCRIPTOR
    expected_count = len(methods) == EXPECTED_METHOD_COUNT
    scaffold_ready = bool(exact_descriptor and expected_count and transaction_map_complete and not proxy_mismatches)

    method_contract = []
    for m in methods:
        tx = tx_by_method.get(m['name'], [])
        r = next((x for x in reachability if x['method_name'] == m['name'] and x['proto'] == m['proto']), None)
        method_contract.append({
            'name': m['name'],
            'proto': m['proto'],
            'signature': m.get('signature') or (m['name'] + m['proto']),
            'transaction_code': tx[0] if len(tx) == 1 else None,
            'reachable_from_custom_app': bool(r and r.get('reachable_from_custom_app')),
            'direct_custom_callsite_count': 0 if not r else int(r.get('direct_custom_callsite_count', 0)),
            'shortest_call_path': [] if not r else r.get('shortest_call_path', []),
        })

    result = {
        'schema': SCHEMA,
        'analysis': 'PASS',
        'access_mode': 'HOST_ONLY_EXISTING_EVIDENCE',
        'root_required': False,
        'magisk_required': False,
        'adb_required': False,
        'frida_required': False,
        'phone_action': 'NONE',
        'input': contract.get('input', {}),
        'binder': {
            'descriptor': descriptor,
            'descriptor_exact_expected_value': exact_descriptor,
            'method_count': len(methods),
            'expected_method_count': EXPECTED_METHOD_COUNT,
            'expected_method_count_match': expected_count,
            'transaction_field_count': len(transactions),
            'transaction_unique_code_count': len(unique_codes),
            'transaction_code_min': min(unique_codes) if unique_codes else None,
            'transaction_code_max': max(unique_codes) if unique_codes else None,
            'transaction_codes_contiguous': contiguous,
            'transaction_map_complete': transaction_map_complete,
            'transaction_missing_methods': missing_tx,
            'transaction_extra_methods': extra_tx,
            'transaction_duplicate_code_count': duplicate_code_count,
            'proxy_transaction_crosscheck_count': proxy_confirmed,
            'proxy_transaction_mismatch_count': len(proxy_mismatches),
            'proxy_transaction_mismatches': proxy_mismatches,
        },
        'method_contract': method_contract,
        'custom_app_usage': {
            'reachable_binder_method_count': len(reachable),
            'unreached_binder_method_count': len(unreachable),
            'reachable_methods': [r['method_name'] + r['proto'] for r in reachable],
            'unreached_methods': [r['method_name'] + r['proto'] for r in unreachable],
        },
        'type_inventory': contract.get('types', []),
        'clean_room': {
            'interface_scaffold_ready': scaffold_ready,
            'functional_behavior_compatibility_proven': False,
            'service_implementation_recovered': False,
            'replacement_boundary': 'INTERFACE_AND_TRANSACTION_COMPATIBILITY_ONLY_NO_VENDOR_IMPLEMENTATION_SEMANTICS',
            'disposition': (
                'CLEAN_ROOM_INTERFACE_SCAFFOLD_READY_BEHAVIOR_SEMANTICS_STILL_REQUIRED'
                if scaffold_ready else
                'CLEAN_ROOM_INTERFACE_SCAFFOLD_NOT_YET_EXACT'
            ),
        },
        'proof_boundary': 'OFFLINE_EXISTING_APK_BYTECODE_ONLY_NO_DEVICE_ACCESS_NO_ROOT_NO_MAGISK_NO_ADB_NO_FRIDA_NO_RUNTIME_MEMORY',
        'device_operation': 'NONE',
    }
    return result


def write_outputs(result: dict[str, Any], output: Path) -> None:
    sanitized = output / 'sanitized'
    sanitized.mkdir(parents=True, exist_ok=True)

    # Full analysis is still derived only from already-local bytecode; keep call paths
    # private because they can be noisy implementation detail. Sanitized outputs retain
    # factual API names/signatures/transaction codes and bounded counts.
    (output / 'privilege-free-contract-private.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')

    san = json.loads(json.dumps(result))
    for item in san.get('method_contract', []):
        item.pop('shortest_call_path', None)
    san_input = san.get('input', {})
    san_input.pop('custom_apk_bytes', None)
    (sanitized / 'test21-r3-3-4-2-6-summary.json').write_text(json.dumps(san, indent=2, sort_keys=True) + '\n')

    binder = result['binder']
    usage = result['custom_app_usage']
    clean = result['clean_room']
    lines = [
        'TEST21_R3_3_4_2_6_ANALYSIS=PASS',
        'ACCESS_MODE=HOST_ONLY_EXISTING_EVIDENCE',
        'ROOT_REQUIRED=NO',
        'MAGISK_REQUIRED=NO',
        'ADB_REQUIRED=NO',
        'FRIDA_REQUIRED=NO',
        'PHONE_ACTION=NONE',
        f'BINDER_INTERFACE_DESCRIPTOR={binder["descriptor"]}',
        'BINDER_DESCRIPTOR_EXPECTED_MATCH=' + ('YES' if binder['descriptor_exact_expected_value'] else 'NO'),
        f'BINDER_INTERFACE_METHOD_COUNT={binder["method_count"]}',
        'BINDER_INTERFACE_METHOD_COUNT_EXPECTED_MATCH=' + ('YES' if binder['expected_method_count_match'] else 'NO'),
        f'TRANSACTION_FIELD_COUNT={binder["transaction_field_count"]}',
        f'TRANSACTION_UNIQUE_CODE_COUNT={binder["transaction_unique_code_count"]}',
        'TRANSACTION_CODES_CONTIGUOUS=' + ('YES' if binder['transaction_codes_contiguous'] else 'NO'),
        'TRANSACTION_MAP_COMPLETE=' + ('YES' if binder['transaction_map_complete'] else 'NO'),
        f'PROXY_TRANSACTION_CROSSCHECK_COUNT={binder["proxy_transaction_crosscheck_count"]}',
        f'PROXY_TRANSACTION_MISMATCH_COUNT={binder["proxy_transaction_mismatch_count"]}',
        f'CUSTOM_APP_REACHABLE_BINDER_METHOD_COUNT={usage["reachable_binder_method_count"]}',
        f'CUSTOM_APP_UNREACHED_BINDER_METHOD_COUNT={usage["unreached_binder_method_count"]}',
        'CLEAN_ROOM_INTERFACE_SCAFFOLD_READY=' + ('YES' if clean['interface_scaffold_ready'] else 'NO'),
        'FUNCTIONAL_BEHAVIOR_COMPATIBILITY_PROVEN=NO',
        'SERVICE_IMPLEMENTATION_RECOVERED=NO',
        'CLEAN_ROOM_DISPOSITION=' + clean['disposition'],
        'DEVICE_OPERATION=NONE',
        'PHOTO_OPERATION=NONE',
        'AUDIO_OPERATION=NONE',
        'NETWORK_CAPTURE=NONE',
    ]
    (sanitized / 'test21-r3-3-4-2-6-summary.txt').write_text('\n'.join(lines) + '\n')

    # TSV is intentionally sanitized: public API symbols only, no call paths or raw bytecode.
    tsv = ['transaction_code\tmethod_name\tproto\treachable_from_custom_app\tdirect_custom_callsite_count']
    for item in sorted(result['method_contract'], key=lambda x: (x['transaction_code'] is None, x['transaction_code'] or 0, x['name'], x['proto'])):
        code = '' if item['transaction_code'] is None else str(item['transaction_code'])
        tsv.append('\t'.join([
            code,
            item['name'],
            item['proto'],
            'YES' if item['reachable_from_custom_app'] else 'NO',
            str(item['direct_custom_callsite_count']),
        ]))
    (sanitized / 'test21-r3-3-4-2-6-transaction-map.tsv').write_text('\n'.join(tsv) + '\n')

    md = [
        '# Test 21 r3.3.4.2.6 — Privilege-free Binder contract result',
        '',
        f'- Descriptor: `{binder["descriptor"]}`',
        f'- Interface methods: **{binder["method_count"]}**',
        f'- Exact transaction-map closure: **{"YES" if binder["transaction_map_complete"] else "NO"}**',
        f'- Proxy transaction mismatches: **{binder["proxy_transaction_mismatch_count"]}**',
        f'- Methods reachable from the custom companion: **{usage["reachable_binder_method_count"]}**',
        f'- Clean-room interface scaffold ready: **{"YES" if clean["interface_scaffold_ready"] else "NO"}**',
        '',
        'This result is interface/transaction compatibility evidence only. It does not recover or claim the proprietary service implementation or behavioral semantics.',
    ]
    (sanitized / 'test21-r3-3-4-2-6-summary.md').write_text('\n'.join(md) + '\n')

    print('\n'.join(lines))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', required=True)
    ap.add_argument('--r3341-evidence')
    ap.add_argument('--output', required=True)
    ap.add_argument('--fixture-json', help=argparse.SUPPRESS)
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)

    if args.fixture_json:
        contract = build_from_fixture(Path(args.fixture_json).resolve())
    else:
        if not args.r3341_evidence:
            raise SystemExit('ERROR: --r3341-evidence is required')
        contract = build_from_evidence(repo, Path(args.r3341_evidence).resolve())

    result = analyze(contract)
    write_outputs(result, output)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
