# Research Tooling

<!-- wiki-status: audience=research; applies_to=repository-tooling; evidence=validated; last_reviewed=2026-08-02 -->

R27.1 introduces a repository-wide canonical tooling layer for the full research history, including numbered tests, CXR work, connection-protocol releases, protected-application/native-loader work, and common evidence tooling.

## Canonical entry point

```bash
scripts/rokid-research summary
scripts/rokid-research catalog
scripts/rokid-research verify
```

The canonical entry point is intentionally **non-destructive** in R27.1.0. It inventories and resolves existing legacy implementations; it does not delete, rename, or automatically execute historical scripts.

## Why this exists

The research process accumulated many revision-specific runners, collectors, analyzers, packagers, validators, and tests. Those paths are valuable provenance, but they are not a sustainable developer interface.

R27 separates two concerns:

1. **stable semantic tooling** — the interface developers should use going forward;
2. **revision lineage** — historical implementations retained for reproducibility and auditability.

## Read next

- [Canonical harness](canonical-harness.md)
- [Legacy and revision-lineage policy](legacy-lineage-policy.md)
- [R27.1.0 canonicalization record](../r27.1.0-whole-repository-canonicalization.md)
- [Tests and qualification history](../../tests/README.md)
- [Research library](../README.md)

## First canonicalized implementation family

R27.1.1 begins actual implementation consolidation with the tracked r25 connection-protocol package validators. Twelve revision-specific validation scripts are represented by one canonical validation engine plus declarative profiles, while the historical scripts remain untouched for equivalence and provenance.

```bash
scripts/rokid-research connection validate --list
scripts/rokid-research connection validate --revision r25.3.1.3
```

See [R27.1.1 r25 validator consolidation](../r27.1.1-r25-validator-consolidation.md).

<!-- r27.1.2-packager-family -->
## Canonical sanitized-evidence packaging

R27.1.2 consolidates the Test 21 sanitized-packager family behind one profile-driven engine while preserving all historical packager files unchanged.

```bash
scripts/rokid-research evidence package --list
scripts/rokid-research evidence package --revision r3.3.4.2.6.1.3 --evidence /path/to/test21-output
```

See [R27.1.2 Test 21 packager consolidation](../r27.1.2-test21-packager-consolidation.md).

<!-- r27.1.3-source-contract-family -->
## Canonical source-contract dispatch

R27.1.3 qualifies the 29 currently applicable Test 21 source-contract checkers behind a single source-locked semantic command while preserving all historical checker files unchanged.

```bash
scripts/rokid-research contract check --list
scripts/rokid-research contract check --track test21 --revision r3.3.4.2.6.1.2
```

Three Test 20 source-contract checkers remain explicit deferred historical contracts because they do not represent a clean current-source equivalence set.

See [R27.1.3 source-contract framework](../r27.1.3-source-contract-framework.md).

<!-- r27.1.5-retirement-readiness -->
## Shared primitives and retirement readiness

R27.1.5 removes duplicated host-only helpers from the canonical engines and adds a machine-readable retirement gate:

```bash
scripts/rokid-research retirement status
```

The gate currently distinguishes 42 independent canonical retirement candidates from historical source-contract/test oracles that are still required. No historical file is removed in this stage.

See [R27.1.5 shared primitives and retirement readiness](../r27.1.5-shared-primitives-retirement-readiness.md).
<!-- r27.1.6-first-legacy-reduction -->
## First controlled legacy reduction

R27.1.6 adds an inbound-dependency gate before retirement. Ten r25 validator implementations are preserved to a private archive and replaced by compatibility shims that delegate to the canonical validator. Two r25 validators remain blocked by the r25.3.1.4 publication hash-lock, and all 30 Test 21 packagers remain preserved because of historical inbound dependencies or ZIP-container compatibility semantics.

No repository path is deleted. See [R27.1.6 first legacy reduction](../r27.1.6-first-legacy-reduction.md).


<!-- r27.1.7-historical-container-compatibility -->
## Historical ZIP-container compatibility

R27.1.7 makes ZIP-container behavior an explicit profile property. The early Test 21 `r3.1`, `r3.2`, and `r3.3` packagers retain legacy source-metadata-sensitive ZIP semantics through canonical compatibility shims, while newer canonical packaging remains deterministic.

Three more duplicated packager implementations are therefore retired without deleting their historical paths. The remaining 27 Test 21 packagers stay unchanged until their source-contract/test/runner dependencies are migrated.

See [R27.1.7 historical container compatibility](../r27.1.7-test21-historical-container-compatibility.md).

### R27.1.8 — publication-lineage decoupling

The final two r25 validator implementations (`r25.3.1` and `r25.3.1.1`) are
now represented by the canonical validator profile registry. Their historical
implementation hashes remain recorded as lineage metadata, while the revision
paths are compatibility shims. The stock ADB-toggle publication verifier checks
that canonical lineage instead of requiring the historical implementation bytes
at the live path.

The publication verifier also limits the forbidden-binary gate to Git-tracked
content (with a generated-directory-aware fallback), so ignored Android build
outputs do not create false publication failures.

## R27.1.9 — Test 21 source-contract lineage decoupling

R27.1.9 reduces the first source-contract-only Test 21 packaging slice. Eleven revision-specific packagers whose only live inbound dependency was the source-contract hash chain are preserved, replaced by canonical compatibility shims, and the 29-source-contract prerequisite hash chain is migrated to the shim identities without changing source-contract PASS behavior.

The remaining sixteen Test 21 packagers are intentionally preserved because tool tests and/or runners still depend on their historical paths or implementation details. This phase does not delete any repository path.

## R27.1.10 — final Test 21 packager implementation reduction

R27.1.10 completes implementation consolidation for the Test 21 sanitized-evidence packager family. All 30 historical packager paths remain callable for reproducibility, but each path is now a thin compatibility shim backed by the single canonical evidence packager and its revision profile.

Historical runners and tool tests may continue to reference the legacy paths; those references are compatibility callers rather than independent packager implementations. The 29 Test 21 source-contract checkers retain their transitive SHA lineage against the shim identities.

The cumulative implementation state after this phase is 42 compatibility shims: 12 r25 validators plus all 30 Test 21 packagers. No repository path is deleted.

See [R27.1.10 final Test 21 packager reduction](../r27.1.10-test21-final-packager-implementation-reduction.md).

## R27.1.11 — independent source-contract engine

The 29 active Test 21 source-contract paths are now compatibility shims. Their historical implementations are archived before replacement, while `rokid-research contract check` evaluates a declarative accepted-source snapshot: exact accepted file identities plus explicit contract-lineage dependencies. The canonical engine no longer executes the historical checker implementations.

This migration intentionally uses a stronger historical-revision contract than the original marker-oriented checks: a benign change to an accepted source file can now fail the snapshot until a reviewed successor profile is published.

See [R27.1.11 source-contract implementation reduction](../r27.1.11-source-contract-snapshot-engine.md).

<!-- r27.1.12-tool-test-oracle-finalization -->
## Tool-test oracle preservation finalization

R27.1.12 closes the R27.1 retirement queue without rewriting independent regression tests. The 38 current Tests 19–21 `test_*_tools.py` suites are explicitly classified as `PRESERVE_REGRESSION_ORACLE`; the one Test 21 suite whose synthetic obfuscated-AAR fixture is absent remains `PRESERVE_HISTORICAL`.

```bash
scripts/rokid-research test verify-oracles
scripts/rokid-research test run --track test21 --revision r3.3.4.2.6.1.3
```

A current oracle is accepted only when its exact source lock holds and the canonical runner reproduces its passing test count. R27.1.12 deletes and rewrites no historical tool-test file. See [R27.1.12 tool-test oracle finalization](../r27.1.12-tool-test-oracle-preservation.md).


<!-- r27.2.1-r25-finalization-publication -->
## r25 finalization and publication-verification framework

R27.2.1 begins the post-R27.1 host-only consolidation sequence with the thirteen-script r25 finalization/publication layer selected by the R27.2.0 residual census. Seven finalizer behaviors and six publication-verification contracts are represented by independent canonical engines and revision profiles while the historical implementations remain unchanged as equivalence oracles.

See [R27.2.1 r25 finalization/publication framework](../r27.2.1-r25-finalization-publication-framework.md).

<!-- r27.2.2-r25-finalization-publication-reduction -->
## R27.2.2 — r25 finalization/publication compatibility shims

The thirteen R27.2.1 equivalence-qualified historical implementations are now archived before replacement. Seven finalizer paths delegate to `r25_finalizer.py`; six publication-verifier paths delegate to `r25_publication_verifier.py`. Existing runner and synthetic-test filenames remain valid, while the duplicated implementation logic is no longer active.

See [R27.2.2 implementation reduction](../r27.2.2-r25-finalization-publication-reduction.md).

<!-- r27.2.4-test21-pcap-parser -->
## Canonical Test 21 PCAP parsing

R27.2.4 adds a profile-driven host-only PCAP parser for the historical Test 21 `r3.3.3` and `r3.3.3.1` analysis revisions while leaving both original parser files byte-unchanged as equivalence oracles.

```bash
scripts/rokid-research network parse-pcap --list
scripts/rokid-research network parse-pcap --revision r3.3.3.1 --pcap /path/to/capture.pcap --uid-map /path/to/uid-map.json --output /path/to/private-output
```

The canonical engine preserves the later revision's linktype-aware raw-IP handling, frame-level attribution, target-package classification, and expanded summary contract through an explicit revision profile.

See [R27.2.4 Test 21 PCAP parser framework](../r27.2.4-test21-pcap-parser-framework.md).

- [R27.2.5 Test 21 PCAP parser reduction](../r27.2.5-test21-pcap-parser-reduction.md)

- [R27.2.7 Test 19 network analyzer framework](../r27.2.7-test19-network-analyzer-framework.md) — canonical r1/r2 PCAPdroid CSV privacy analysis with behavioral equivalence and historical-source preservation.

## Final consolidation status

Use `scripts/rokid-research consolidation status` to verify the R27.2.8 final state. A passing result requires all canonical shim/source locks and all four `PRESERVE_DISTINCT_IMPLEMENTATION` family locks to match before reporting `NEXT_DEVICE_TEST_READY=YES`.

<!-- r27.3-final-publication -->
## Publication baseline

R27.3 is the final publication gate for the R27 program. It publishes only an exact allowlist of reviewed source/documentation paths, validates the final consolidation state, reruns the preserved-oracle and R27 framework gates, and refuses unexpected staged/untracked content.
