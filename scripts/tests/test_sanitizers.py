from __future__ import annotations

import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_module(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    import sys
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


http = load_module("sanitize_http_requests", "scripts/sanitize_http_requests.py")
pcap = load_module("sanitize_pcapdroid_csv", "scripts/sanitize_pcapdroid_csv.py")


class HttpSanitizerTests(unittest.TestCase):
    def test_query_values_are_redacted(self):
        value = http.sanitize_path("/device/login?deviceId=123&userId=abc&empty=")
        self.assertEqual(
            value,
            "/device/login?deviceId=[REDACTED]&userId=[REDACTED]&empty=[REDACTED]",
        )

    def test_identifier_path_segments_are_redacted(self):
        value = http.sanitize_path("/v1/items/1234567890abcdef1234567890abcdef")
        self.assertEqual(value, "/v1/items/[REDACTED]")

    def test_http1_and_http2_columns_parse(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "requests.txt"
            path.write_text(
                "1\t2026-01-01T00:00:00Z\tGET\texample.com\t/a?x=1\t\t\t\n"
                "2\t2026-01-01T00:00:01Z\t\t\t\tPOST\tapi.example.com\t/b?id=secret\n",
                encoding="utf-8",
            )
            records = http.load_records(path)
            self.assertEqual(len(records), 2)
            self.assertEqual(records[0].path, "/a?x=[REDACTED]")
            self.assertEqual(records[1].path, "/b?id=[REDACTED]")


class CsvSanitizerTests(unittest.TestCase):
    def test_private_columns_are_not_emitted(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "input.csv"
            out = Path(tmp) / "out.csv"
            md = Path(tmp) / "out.md"
            fields = [
                "IPProto", "SrcIP", "SrcPort", "DstIp", "DstPort", "UID",
                "App", "PackageName", "Proto", "Status", "Info", "BytesSent",
                "BytesRcvd", "PktsSent", "PktsRcvd", "FirstSeen", "LastSeen",
            ]
            with src.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerow({
                    "IPProto": "6", "SrcIP": "192.168.1.2", "SrcPort": "12345",
                    "DstIp": "8.8.8.8", "DstPort": "443", "UID": "10001",
                    "App": "Hi Rokid", "PackageName": "com.example", "Proto": "HTTPS",
                    "Status": "Closed", "Info": "api.example.com", "BytesSent": "10",
                    "BytesRcvd": "20", "PktsSent": "1", "PktsRcvd": "2",
                    "FirstSeen": "a", "LastSeen": "b",
                })
            items = pcap.load(src)
            pcap.write_csv(items, out)
            pcap.write_markdown(items, md)
            text = out.read_text(encoding="utf-8")
            self.assertNotIn("192.168.1.2", text)
            self.assertNotIn("8.8.8.8", text)
            self.assertNotIn("10001", text)
            self.assertIn("api.example.com", text)


if __name__ == "__main__":
    unittest.main()
