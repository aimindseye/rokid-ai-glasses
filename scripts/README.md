# Scripts

Private-evidence generators read `ROKID_PRIVATE_ROOT` from `.env.local`.
Create it from `.env.example`; `.env.local` must remain untracked.

- `generate_03b_public_evidence.sh` — regenerate sanitized Test 03b evidence
- `generate_04ab_manifests.sh` — regenerate hash-only Test 04a/04b manifests
- `sanitize_http_requests.py` — redact and aggregate tshark request paths
- `sanitize_pcapdroid_csv.py` — remove IPs, UIDs, ports, and aggregate connections
- `generate_evidence_manifest.py` — create hash-only private evidence manifests
- `validate_public_tree.py` — fail on forbidden files or unredacted secrets
- `safety/scan_public_artifacts.sh` — scan Git files for private-evidence signatures
- `run_baseline_gate.sh` — run baseline tests, evidence generation, and validation
- `tests/test_sanitizers.py` — standard-library unit tests
- `tests/validate_06c_public_findings.sh` — validate Test 06c public closeout
- `tests/validate_10_public_findings.sh` — validate Test 10 public closeout
- `run_test10_docs_gate.sh` — run the Test 10 and public-tree gates
