# Scripts

- `generate_03b_public_evidence.sh` — regenerate sanitized Test 03b evidence
- `sanitize_http_requests.py` — redact and aggregate tshark request paths
- `sanitize_pcapdroid_csv.py` — remove IPs/UIDs/ports and aggregate connections
- `generate_evidence_manifest.py` — create hash-only private evidence manifest
- `validate_public_tree.py` — fail on forbidden files or unredacted secrets
- `run_baseline_gate.sh` — run tests, generation, and validation
- `tests/test_sanitizers.py` — standard-library unit tests
