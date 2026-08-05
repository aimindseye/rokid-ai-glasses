#!/usr/bin/env python3
"""Classify Test 22 without publishing raw Wi-Fi credentials or addresses."""
from __future__ import annotations
import argparse, json
from pathlib import Path


def load(path): return json.loads(Path(path).read_text())

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--app-result',required=True)
    ap.add_argument('--backend-result',required=True)
    ap.add_argument('--phone-isolation-confirmed',required=True)
    ap.add_argument('--output',required=True)
    args=ap.parse_args()
    app=load(args.app_result); backend=load(args.backend_result)
    phone_ok=args.phone_isolation_confirmed=='YES'
    direct=(
        app.get('wifi_transport_found') is True and
        app.get('wifi_default_route') is True and
        app.get('tcp_connect_success') is True and
        app.get('tls_handshake_success') is True and
        app.get('tls_echo_verified') is True and
        app.get('socket_local_matches_wifi_link_address') is True and
        backend.get('status')=='PASS' and
        backend.get('request_verified') is True and
        app.get('socket_local_ip_sha256') and
        app.get('socket_local_ip_sha256')==backend.get('peer_ip_sha256') and
        app.get('nonce_sha256')==backend.get('nonce_sha256')
    )
    driven=(
        app.get('wifi_enabled_before') is False and
        app.get('wifi_enable_requested_by_app') is True and
        app.get('wifi_enable_request_return') is True and
        app.get('wifi_enabled_after_request') is True and
        app.get('wifi_network_add_id_nonnegative') is True and
        app.get('wifi_enable_network_return') is True and
        app.get('wifi_reconnect_return') is True
    )
    if not app.get('feature_wifi') or not app.get('wifi_service_present'):
        disposition='NO_WIFI_FRAMEWORK_CAPABILITY'
    elif direct and driven and phone_ok:
        disposition='PASS_APP_DRIVEN_WIFI_AND_DIRECT_TLS'
    elif direct and phone_ok:
        disposition='PASS_DIRECT_WIFI_DATAPLANE_CONTROL_NOT_PROVEN'
    elif app.get('wifi_enabled_after_request') is not True:
        disposition='BLOCKED_APP_WIFI_ENABLE'
    elif app.get('wifi_network_add_id_nonnegative') is not True:
        disposition='BLOCKED_APP_WIFI_CONFIGURATION'
    elif app.get('wifi_transport_found') is not True:
        disposition='BLOCKED_WIFI_ASSOCIATION_OR_ROUTE'
    elif app.get('tls_handshake_success') is not True:
        disposition='PARTIAL_WIFI_ROUTE_NO_DIRECT_TLS'
    else:
        disposition='FAIL_DIRECT_WIFI_PROOF'
    summary={
      'schema':'rokid.test22.summary.v1',
      'disposition':disposition,
      'phone_isolation_operator_confirmed':phone_ok,
      'feature_wifi':bool(app.get('feature_wifi')),
      'wifi_service_present':bool(app.get('wifi_service_present')),
      'app_wifi_enable_proven':driven,
      'wifi_transport_found':bool(app.get('wifi_transport_found')),
      'wifi_default_route':bool(app.get('wifi_default_route')),
      'wifi_interface':app.get('wifi_interface',''),
      'direct_tls_proven':direct,
      'tls_protocol':app.get('tls_protocol',''),
      'socket_peer_hash_agreement':bool(app.get('socket_local_ip_sha256') and app.get('socket_local_ip_sha256')==backend.get('peer_ip_sha256')),
      'bluetooth_api_used':bool(app.get('bluetooth_api_used',True)),
      'cxr_api_used':bool(app.get('cxr_api_used',True)),
      'default_network_socket_used':bool(app.get('default_network_socket_used',True)),
      'raw_wifi_credentials_in_summary':False,
      'raw_ip_addresses_in_summary':False,
    }
    out=Path(args.output); out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    for k,v in summary.items():
        print(f'TEST22_{k.upper()}={str(v).upper() if isinstance(v,bool) else v}')
    return 0

if __name__=='__main__': raise SystemExit(main())
