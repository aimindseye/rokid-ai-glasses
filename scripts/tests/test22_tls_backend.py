#!/usr/bin/env python3
"""One-shot controlled TLS endpoint for Test 22. Writes hashes, never raw client IPs."""
from __future__ import annotations
import argparse, hashlib, json, socket, ssl, time
from pathlib import Path


def sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--bind', required=True)
    ap.add_argument('--port', type=int, required=True)
    ap.add_argument('--cert', required=True)
    ap.add_argument('--key', required=True)
    ap.add_argument('--nonce', required=True)
    ap.add_argument('--result', required=True)
    ap.add_argument('--ready', required=True)
    args=ap.parse_args()
    result_path=Path(args.result); ready=Path(args.ready)
    result_path.parent.mkdir(parents=True, exist_ok=True)
    ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version=ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(args.cert,args.key)
    payload={'schema':'rokid.test22.backend-result.v1','status':'FAIL','nonce_sha256':sha(args.nonce)}
    server=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    server.bind((args.bind,args.port)); server.listen(1); server.settimeout(100)
    ready.write_text('READY\n')
    try:
        conn,peer=server.accept()
        with ctx.wrap_socket(conn,server_side=True) as tls:
            tls.settimeout(15)
            data=b''
            while not data.endswith(b'\n') and len(data)<4096:
                chunk=tls.recv(4096)
                if not chunk: break
                data+=chunk
            line=data.decode('utf-8','strict').rstrip('\r\n')
            expected='TEST22|'+args.nonce
            valid=line==expected
            if valid:
                tls.sendall(('TEST22-OK|'+args.nonce+'\n').encode())
            payload.update({
                'status':'PASS' if valid else 'FAIL',
                'request_verified':valid,
                'peer_ip_sha256':sha(peer[0]),
                'peer_address_family':'IPv4',
                'tls_version':tls.version() or '',
                'cipher':(tls.cipher() or ('','',''))[0],
                'received_bytes':len(data),
                'completed_unix_ms':int(time.time()*1000),
            })
    except Exception as exc:
        payload['error_class']=exc.__class__.__name__
    finally:
        server.close()
        result_path.write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n')
    return 0 if payload['status']=='PASS' else 1

if __name__=='__main__':
    raise SystemExit(main())
