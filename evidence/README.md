# Public Evidence

This directory contains only reviewed and sanitized evidence.

Raw packet captures, TLS keys, decrypted payloads, Android logs, Bluetooth
captures, account IDs, device IDs, and credentials are intentionally excluded.

## Test 03b

`sanitized/03b/` contains:

- `protocol-summary.txt` — protocol hierarchy only
- `http-request-paths.tsv` — sanitized and aggregated HTTP paths
- `http-request-paths.md` — human-readable sanitized path table
- `connection-summary.csv` — aggregated PCAPdroid connection statistics
- `connection-summary.md` — human-readable connection table

`manifests/03b-private-evidence-sha256.json` contains hashes, sizes, and
private-relative filenames only. It does not contain captured payload data.
