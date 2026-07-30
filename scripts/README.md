# Public Scripts

The public scripts support the numbered tests, evidence sanitization, repository
safety, and the published native-loader artifacts. Outputs from capture runners
are private by default and must be stored outside the Git worktree.

## Directory map

- [Analysis helpers](analysis/README.md)
- [Capture helpers](capture/README.md)
- [Recovery utilities](recovery/README.md)
- [Research utilities](research/README.md)
- [Safety gates](safety/README.md)
- [Test runners](tests/README.md)

## Root utilities

| Script | Purpose |
|---|---|
| `generate_evidence_manifest.py` | Build hash-only evidence manifests |
| `generate_03b_public_evidence.sh` | Generate sanitized Test 03B summaries |
| `generate_04ab_manifests.sh` | Generate Test 04A/04B manifests |
| `sanitize_http_requests.py` | Sanitize request exports |
| `sanitize_pcapdroid_csv.py` | Sanitize PCAPdroid CSV exports |
| `validate_public_tree.py` | Validate the public tree |
| `safety/check_markdown_links.py` | Validate local Markdown targets and heading fragments |
| `run_baseline_gate.sh` | Run baseline public checks |
| `run_test10_docs_gate.sh` | Validate Test 10 documentation/evidence |

## Coverage

The committed interactive runners cover Tests 14A-r2 through 17F. Test 18 was
an offline/static follow-up and does not have a committed runtime replay tool.
The r22–r24 research packages used additional private analysis tooling; this
repository publishes their sanitized results and generic verification or
observation utilities, not the private evidence-processing workspaces.

## Requirements

- Python 3.10 or later
- Android platform tools (`adb`) for device tests
- an authorized phone or glasses target where required
- PCAPdroid configured for the controlled app/account for network tests

## Safety boundary

Generated evidence may contain PCAPs, TLS keys, screenshots, logcat, HCI logs,
package inventories, media, account/session values, location, device serials,
APKs, and complete Android state. Keep private output outside the repository and
run the [safety gates](safety/README.md) before publishing derived material.

<!-- BEGIN R1.3.3.2.25 SCRIPT INDEX -->
## Stock connection protocol

See [`research/connection-protocol/`](research/connection-protocol/) for the r25 stock capture, HCI metadata, client-log, attribution and finalization tools. Use `research/verify_r25_3_pre_repair_publication.py` for the historical r25.3 pre-repair and boot-chain publication gate. Use `research/verify_r25_3_1_4_publication.py` for the accepted stock ADB-toggle publication integration.
<!-- END R1.3.3.2.25 SCRIPT INDEX -->
<!-- BEGIN R1.3.3.2.25.1 SCRIPT INDEX -->
The r25.1 analyzer under [`research/connection-protocol/`](research/connection-protocol/) reconstructs the BLE-to-RFCOMM establishment sequence from a private r25 evidence ZIP while generating a sanitized public closure record.
<!-- END R1.3.3.2.25.1 SCRIPT INDEX -->

### r25.2 connection-only qualification

Use `scripts/research/connection-protocol/run_r1_3_3_2_25_2.sh` to enforce strict Hi Rokid isolation, collect the private client log, validate zero payload I/O, and restore stock operation.


### r25.3.1.2 and r25.3.1.3 host-only analyzers

The `research/connection-protocol/` directory includes the accepted target-pair-scoped RFCOMM qualification analyzer and the exact observed-frame grammar analyzer. They read explicit private source archives supplied by the operator, write private output outside the repository, generate separate sanitized publication artifacts, and contain no device command or captured-payload replay path.
