#!/usr/bin/env python3
from __future__ import annotations

import re

TOKEN_RE = re.compile(
    r'(?i)(?:authorization[_ -]?token|auth[_ -]?token|bearer|access[_ -]?token)'
    r'\s*[:=]\s*[A-Za-z0-9._~+/=-]{8,}'
)
MAC_RE = re.compile(r'(?i)\b(?:[0-9a-f]{2}:){5}[0-9a-f]{2}\b')
PID_RE = re.compile(r'(?i)"?(?:pid|process_id)"?\s*[:=]\s*\d{2,}')
CURRENT_PATTERNS = [
    ('mac_home', re.compile(r'/Users/[A-Za-z0-9._-]+/')),
    ('linux_home', re.compile(r'/home/[A-Za-z0-9._-]+/')),
    ('email', re.compile(r'\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b', re.I)),
    ('mac', MAC_RE),
    ('bearer', re.compile(r'\bBearer\s+[A-Za-z0-9._~+/-]+=*', re.I)),
    ('jwt', re.compile(r'\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b')),
    ('phone_serial', re.compile(r'PHONE_SERIAL\s*=', re.I)),
]
CURRENT_FORBIDDEN_EXT = {
    '.aar', '.jar', '.apk', '.apks', '.pcap', '.pcapng', '.key', '.pem', '.der',
    '.jpg', '.jpeg', '.png', '.webp',
}
IPV4_CANDIDATE = re.compile(r'(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])')


def valid_ipv4(candidate: str) -> bool:
    parts = candidate.split('.')
    return len(parts) == 4 and all(part.isdigit() and 0 <= int(part) <= 255 for part in parts)


def current_privacy_violation(text: str) -> str | None:
    for label, rx in CURRENT_PATTERNS:
        if rx.search(text):
            return label
    for match in IPV4_CANDIDATE.finditer(text):
        if valid_ipv4(match.group(0)):
            return 'ipv4'
    return None
