#!/usr/bin/env python3
from __future__ import annotations

import ipaddress
import json
import re
import shutil
import struct
import subprocess
from pathlib import Path

try:
    from primitives import read_json
except ImportError:
    from scripts.research.canonical.primitives import read_json

MAGIC = 0x01072021
METHODS = (b"GET ", b"POST ", b"PUT ", b"PATCH ", b"DELETE ", b"HEAD ", b"OPTIONS ")
PROFILE_PATH = Path(__file__).resolve().parent / "profiles" / "test21-pcap-parsers.json"


def _profiles() -> list[dict]:
    data = read_json(PROFILE_PATH)
    if data.get("schema") != "rokid.r27.2.4.test21-pcap-parsers.v1":
        raise ValueError("unexpected PCAP parser profile schema")
    return data.get("profiles", [])


def get_profile(revision: str) -> dict:
    for profile in _profiles():
        if profile.get("revision") == revision:
            return profile
    raise KeyError(revision)


def list_profiles() -> int:
    for p in _profiles():
        print(f"{p['revision']}\t{p['legacy_path']}\t{p['summary_schema']}")
    return 0


def clean_path(value: str | None) -> str:
    p = (value or "/").split("?", 1)[0].split("#", 1)[0] or "/"
    segs: list[str] = []
    for segment in p.split("/"):
        if re.fullmatch(r"[A-Fa-f0-9]{16,}", segment or "") or re.fullmatch(r"[A-Za-z0-9_-]{28,}", segment or ""):
            segment = ":id"
        segs.append(segment)
    return "/".join(segs)[:240]


def trailer(data: bytes, search_bytes: int) -> tuple[int, int, str]:
    for endian in ("<", ">"):
        marker = struct.pack(endian + "I", MAGIC)
        pos = data.rfind(marker, max(0, len(data) - search_bytes))
        if pos >= 0 and pos + 28 <= len(data):
            uid = struct.unpack_from(endian + "i", data, pos + 4)[0]
            name = data[pos + 8 : pos + 28].split(b"\0", 1)[0].decode("utf-8", "replace")
            return pos, uid, name
    return len(data), -1, ""


def dns_q(payload: bytes) -> str | None:
    if len(payload) < 13:
        return None
    try:
        flags = struct.unpack("!H", payload[2:4])[0]
        if flags & 0x8000:
            return None
        i = 12
        parts: list[str] = []
        while i < len(payload):
            n = payload[i]
            i += 1
            if n == 0:
                break
            if n & 0xC0:
                return None
            parts.append(payload[i : i + n].decode("ascii", "ignore"))
            i += n
        return ".".join(parts) or None
    except Exception:
        return None


def tls_sni(payload: bytes) -> str | None:
    try:
        if len(payload) < 5 or payload[0] != 22:
            return None
        length = struct.unpack("!H", payload[3:5])[0]
        body = payload[5 : 5 + length]
        if len(body) < 42 or body[0] != 1:
            return None
        i = 4 + 2 + 32
        sid = body[i]
        i += 1 + sid
        cipher_size = struct.unpack("!H", body[i : i + 2])[0]
        i += 2 + cipher_size
        compression_size = body[i]
        i += 1 + compression_size
        extensions_size = struct.unpack("!H", body[i : i + 2])[0]
        i += 2
        end = min(len(body), i + extensions_size)
        while i + 4 <= end:
            typ, item_len = struct.unpack("!HH", body[i : i + 4])
            i += 4
            value = body[i : i + item_len]
            i += item_len
            if typ == 0 and len(value) >= 5:
                j = 2
                while j + 3 <= len(value):
                    name_type = value[j]
                    name_len = struct.unpack("!H", value[j + 1 : j + 3])[0]
                    j += 3
                    if name_type == 0:
                        return value[j : j + name_len].decode("ascii", "ignore")
                    j += name_len
    except Exception:
        pass
    return None


def _ip_payload(frame: bytes, end: int, linktype: int, mode: str) -> bytes:
    if mode == "pcap_linktype_aware":
        if linktype == 1:
            if len(frame) < 14:
                return b""
            return frame[14:end]
        if linktype in (101, 228, 229):
            return frame[:end]
    return frame[14:end] if len(frame) >= 14 else frame[:end]


def parse_ip(frame: bytes, end: int, linktype: int, mode: str):
    data = _ip_payload(frame, end, linktype, mode)
    if not data:
        return None
    version = data[0] >> 4
    if version == 4 and len(data) >= 20:
        ihl = (data[0] & 15) * 4
        proto = data[9]
        src = str(ipaddress.IPv4Address(data[12:16]))
        dst = str(ipaddress.IPv4Address(data[16:20]))
        transport = data[ihl:]
    elif version == 6 and len(data) >= 40:
        proto = data[6]
        src = str(ipaddress.IPv6Address(data[8:24]))
        dst = str(ipaddress.IPv6Address(data[24:40]))
        transport = data[40:]
    else:
        return None
    src_port = dst_port = None
    app = transport
    if proto == 6 and len(transport) >= 20:
        src_port, dst_port = struct.unpack("!HH", transport[:4])
        offset = ((transport[12] >> 4) & 15) * 4
        app = transport[offset:]
    elif proto == 17 and len(transport) >= 8:
        src_port, dst_port = struct.unpack("!HH", transport[:4])
        app = transport[8:]
    return src, dst, proto, src_port, dst_port, app


def public_endpoint(src: str, dst: str) -> bool:
    for text in (src, dst):
        try:
            if ipaddress.ip_address(text).is_global:
                return True
        except Exception:
            pass
    return False


def _pcap_header(blob: bytes) -> tuple[str, bool, int]:
    if len(blob) < 24:
        return "", False, 0
    magic = blob[:4]
    if magic == b"\xd4\xc3\xb2\xa1":
        endian, nano = "<", False
    elif magic == b"\xa1\xb2\xc3\xd4":
        endian, nano = ">", False
    elif magic == b"M<\xb2\xa1":
        endian, nano = "<", True
    elif magic == b"\xa1\xb2<M":
        endian, nano = ">", True
    else:
        raise ValueError("unsupported PCAP magic")
    linktype = struct.unpack_from(endian + "I", blob, 20)[0]
    return endian, nano, linktype


def parse_pcap(path: Path, uid_map: dict[str, str], profile: dict) -> list[dict]:
    blob = Path(path).read_bytes()
    if len(blob) < 24:
        return []
    endian, nano, linktype = _pcap_header(blob)
    rows: list[dict] = []
    offset = 24
    frame_number = 0
    while offset + 16 <= len(blob):
        sec, frac, captured, _original = struct.unpack_from(endian + "IIII", blob, offset)
        offset += 16
        if offset + captured > len(blob):
            break
        frame = blob[offset : offset + captured]
        offset += captured
        frame_number += 1
        trailer_pos, uid, short_name = trailer(frame, int(profile["trailer_search_bytes"]))
        parsed = parse_ip(frame, trailer_pos, linktype, profile["linktype_mode"])
        if not parsed:
            continue
        src, dst, proto, src_port, dst_port, payload = parsed
        package = uid_map.get(str(uid), short_name or "UNKNOWN")
        timestamp = sec + (frac / (1e9 if nano else 1e6))
        marker = host = method = path_value = None
        if proto == 17 and (src_port == 53 or dst_port == 53):
            query = dns_q(payload)
            if query:
                marker = "dns_query"
                host = query
        if proto == 6:
            sni = tls_sni(payload)
            if sni:
                marker = "tls_client_hello"
                host = sni
            for method_prefix in METHODS:
                if payload.startswith(method_prefix):
                    try:
                        line = payload.split(b"\r\n", 1)[0].decode("latin1", "replace")
                        parts = line.split(" ", 2)
                        method = parts[0]
                        path_value = clean_path(parts[1])
                        headers = payload.split(b"\r\n\r\n", 1)[0].decode("latin1", "replace").split("\r\n")
                        hosts = [item.split(":", 1)[1].strip() for item in headers[1:] if item.lower().startswith("host:")]
                        host = hosts[0] if hosts else None
                        marker = "http_request"
                    except Exception:
                        pass
                    break
        flow_key = None
        if src_port is not None:
            flow_key = "|".join(map(str, sorted([(src, src_port), (dst, dst_port)]))) + "|" + str(proto)
        row = {
            "epoch_ms": int(timestamp * 1000),
            "uid": uid,
            "package": package,
            "src": src,
            "dst": dst,
            "proto": proto,
            "src_port": src_port,
            "dst_port": dst_port,
            "flow_key": flow_key,
            "marker_type": marker,
            "host": host,
            "method": method,
            "path": path_value,
        }
        if profile.get("include_frame_number"):
            row = {"frame_number": frame_number, **row}
        if profile.get("include_public_endpoint"):
            # Historical r3.3.3.1 places this field between flow_key and marker_type.
            row = {
                **{k: row[k] for k in row if k != "marker_type" and k != "host" and k != "method" and k != "path"},
                "public_endpoint": public_endpoint(src, dst),
                "marker_type": marker,
                "host": host,
                "method": method,
                "path": path_value,
            }
        rows.append(row)
    return rows


def _flow_key(src: str, src_port: str, dst: str, dst_port: str) -> str | None:
    try:
        return "|".join(map(str, sorted([(src, int(src_port)), (dst, int(dst_port))]))) + "|6"
    except Exception:
        return None


def tshark_http(pcap: Path, keylog: Path | None, rows: list[dict], profile: dict):
    exe = shutil.which("tshark")
    if not exe or not keylog or not Path(keylog).is_file() or not Path(keylog).stat().st_size:
        return [], "UNAVAILABLE"
    fields = [
        "frame.time_epoch", "ip.src", "ipv6.src", "ip.dst", "ipv6.dst", "tcp.srcport", "tcp.dstport",
        "http.request.method", "http.host", "http.request.uri", "http.response.code", "http2.headers.method",
        "http2.headers.authority", "http2.headers.path", "http2.headers.status",
    ]
    if profile.get("tshark_include_frame_number"):
        fields.insert(0, "frame.number")
    cmd = [
        exe, "-r", str(pcap), "-o", f"tls.keylog_file:{keylog}", "-Y",
        "http.request or http.response or http2.headers.method or http2.headers.status",
        "-T", "fields", "-E", "separator=\t", "-E", "occurrence=f",
    ]
    for field in fields:
        cmd += ["-e", field]
    try:
        result = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    except Exception:
        return [], "ERROR"
    if result.returncode != 0:
        return [], "ERROR"

    targets = set(profile.get("target_packages", []))
    frame_package = {
        row["frame_number"]: row["package"]
        for row in rows
        if row.get("frame_number") and row.get("package") in targets
    }
    if profile.get("tshark_target_attribution"):
        flow_map = {
            row["flow_key"]: row["package"]
            for row in rows
            if row.get("flow_key") and row.get("package") in targets
        }
    else:
        flow_map = {
            row["flow_key"]: row["package"]
            for row in rows
            if row.get("flow_key") and row.get("package")
        }

    out: list[dict] = []
    for line in result.stdout.splitlines():
        columns = line.split("\t")
        columns += [""] * (len(fields) - len(columns))
        item = dict(zip(fields, columns))
        src = item["ip.src"] or item["ipv6.src"]
        dst = item["ip.dst"] or item["ipv6.dst"]
        src_port = item["tcp.srcport"]
        dst_port = item["tcp.dstport"]
        key = _flow_key(src, src_port, dst, dst_port)
        if profile.get("tshark_target_attribution"):
            try:
                frame = int(item["frame.number"])
            except Exception:
                frame = None
            package = frame_package.get(frame)
            attribution = "FRAME_TRAILER" if package else None
            if not package and key and key in flow_map:
                package = flow_map[key]
                attribution = "FLOW_TUPLE"
            if not package:
                package = "UNKNOWN"
                attribution = "UNATTRIBUTED"
        else:
            frame = None
            package = flow_map.get(key, "UNKNOWN")
            attribution = None
        method = item["http.request.method"] or item["http2.headers.method"]
        host = item["http.host"] or item["http2.headers.authority"]
        path_value = item["http.request.uri"] or item["http2.headers.path"]
        status = item["http.response.code"] or item["http2.headers.status"]
        row = {
            "epoch_ms": int(float(item["frame.time_epoch"]) * 1000) if item["frame.time_epoch"] else None,
            "package": package,
            "host": host or None,
            "method": method or None,
            "path": clean_path(path_value) if path_value else None,
            "status": status or None,
        }
        if profile.get("tshark_target_attribution"):
            row = {
                "frame_number": frame,
                "epoch_ms": row["epoch_ms"],
                "package": package,
                "attribution_method": attribution,
                "host": row["host"],
                "method": row["method"],
                "path": row["path"],
                "status": row["status"],
            }
        out.append(row)
    return out, "AVAILABLE"


def parse_revision(
    repo: Path,
    revision: str,
    pcap: Path,
    uid_map_path: Path,
    output: Path,
    sslkeylog: Path | None = None,
    *,
    emit_output: bool = True,
):
    del repo  # reserved for future repository-scoped policies
    profile = get_profile(revision)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    uid_map = json.loads(Path(uid_map_path).read_text())
    rows = parse_pcap(Path(pcap), uid_map, profile)
    (output / "network-packets-private.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
    )
    http, status = tshark_http(Path(pcap), Path(sslkeylog) if sslkeylog else None, rows, profile)
    (output / "decrypted-http-private.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in http)
    )

    targets = set(profile.get("target_packages", []))
    if revision == "r3.3.3.1":
        target_http = sum(1 for row in http if row.get("package") in targets)
        frame_http = sum(1 for row in http if row.get("attribution_method") == "FRAME_TRAILER")
        summary = {
            "schema": profile["summary_schema"],
            "packet_rows": len(rows),
            "target_packet_rows": sum(1 for row in rows if row.get("package") in targets),
            "marker_rows": sum(bool(row.get("marker_type")) for row in rows),
            "packages": sorted(set(row["package"] for row in rows)),
            "tshark_decryption_metadata": status,
            "decrypted_http_rows": len(http),
            "target_attributed_http_rows": target_http,
            "frame_trailer_attributed_http_rows": frame_http,
        }
    else:
        summary = {
            "schema": profile["summary_schema"],
            "packet_rows": len(rows),
            "marker_rows": sum(bool(row.get("marker_type")) for row in rows),
            "packages": sorted(set(row["package"] for row in rows)),
            "tshark_decryption_metadata": status,
            "decrypted_http_rows": len(http),
        }
    (output / "network-parse-private.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")

    lines = [profile["pass_marker"], f"PACKET_ROWS={len(rows)}"]
    if revision == "r3.3.3.1":
        lines.append(f"TARGET_PACKET_ROWS={summary['target_packet_rows']}")
    lines.append(f"DECRYPTED_HTTP_METADATA={status}")
    if revision == "r3.3.3.1":
        lines.append(f"TARGET_ATTRIBUTED_HTTP_ROWS={summary['target_attributed_http_rows']}")
        lines.append(f"FRAME_TRAILER_ATTRIBUTED_HTTP_ROWS={summary['frame_trailer_attributed_http_rows']}")
    if emit_output:
        for line in lines:
            print(line)
    return 0, summary, lines
