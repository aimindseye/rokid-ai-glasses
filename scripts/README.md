# Public Scripts

The repository contains capture, analysis, recovery, research, safety, and test
utilities. Scripts operate on controlled local inputs and must not publish raw
private evidence.

## Documentation and public-repository gates

```bash
bash scripts/safety/validate_public_repo.sh
python3 scripts/safety/check_markdown_links.py --repo .
python3 scripts/safety/check_documentation_governance.py --repo .
```

The documentation-governance gate validates the audience navigation manifest,
page-status metadata, canonical-page coverage, unique titles, consumer
navigation boundary, and legacy forwarders.

See the subdirectory READMEs for capture, analysis, recovery, and research
usage.

## Test 19 CXR-M qualification

```bash
python3 scripts/research/cxr/resolve_cxr_m_maven.py --help
python3 scripts/research/cxr/analyze_cxr_artifact.py --help
bash scripts/tests/run_test19_cxr_qualification.sh --help
python3 scripts/tests/analyze_test19_network.py --help
python3 scripts/tests/analyze_test19_cxr_evidence.py --help
```

The runner resolves CXR-M from Rokid Maven metadata, keeps the downloaded POM/AAR and runtime evidence private, and requires capture-based local-network qualification for a complete pass.

<!-- test22-final-publication:start -->
## Canonical Test 22 diagnostics

`scripts/tests/test22` consolidates the read-only Test 22 utilities that were repeatedly repaired during qualification: multi-device ADB selection, compact Wi-Fi/route monitoring, phone-off isolation, historical ARM/RUN receipt recovery, post-effect recovery, and redacted log compaction. `scripts/safety/check_shell_portability.py` provides a reusable macOS Bash 3.2 surface check.

Repair-version scripts remain provenance only; new work should use the canonical tool.

<!-- test22-final-publication:end -->

### Consolidation status

`./scripts/rokid-research consolidation status` verifies the R27.2.8 whole-history closure and next-test readiness. Historical filenames may remain as compatibility shims or intentionally distinct research programs.
