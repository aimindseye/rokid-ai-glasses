# Canonical research harness

This directory contains the repository-wide semantic front door introduced by R27.1.0.

The first canonicalization stage is deliberately a **bridge**, not a rewrite of historical experiments. Existing revision-named scripts remain immutable lineage inputs while `scripts/rokid-research` supplies a stable way to inventory, resolve, classify, and verify them.

No legacy script is deleted or silently redirected by R27.1.0.

## Source-contract framework

R27.1.3 adds a source-locked canonical dispatch layer for the currently applicable Test 21 source-contract family:

```bash
scripts/rokid-research contract check --list
scripts/rokid-research contract check --track test21 --revision r3.3.4.2.6.1.2
```

Twenty-nine Test 21 contracts are qualified behind this interface. Three historical Test 20 contracts remain explicitly deferred instead of being presented as current-tree equivalents. No historical checker is deleted or rewritten in this stage.

## Tool-test suite registry

R27.1.4 adds one canonical invocation layer for the historical Tests 19–21 `test_*_tools.py` family:

```bash
scripts/rokid-research test run --list
scripts/rokid-research test run --track test21 --revision r3.2
scripts/rokid-research test run --track test21 --revision r3.3.4.2.6.1.3
```

Thirty-eight current suites are source-locked and equivalence-qualified. The historical Test 21 `r3.3.4.2.6.1.1` suite remains explicitly deferred because its synthetic obfuscated AAR fixture is absent from the current repository. Historical unittest files remain unchanged and are still the assertion-level oracle in this stage.

## Shared primitives and retirement readiness

R27.1.5 centralizes common hashing, source-lock, subprocess, syntax, marker/regex, sidecar, and privacy primitives used by the canonical engines.

```bash
scripts/rokid-research retirement status
```

The retirement report marks only independently implemented/equivalence-qualified families as candidates. Historical source-contract checkers and tool-test suites remain required because their canonical commands still execute those historical files.

## R27.2.1 r25 finalization and publication verification

R27.2.1 adds independent profile-driven engines for the seven historical r25 private-evidence finalizers and six historical sanitized-publication verifiers:

```bash
scripts/rokid-research connection finalize --list
scripts/rokid-research connection verify-publication --list
```

The profiles retain revision-specific manifest, archive, privacy, and semantic rules. The thirteen historical scripts remain source-locked and byte-unchanged in R27.2.1; the equivalence gate is a prerequisite to any later compatibility-shim reduction.

## R27.2.2 r25 lifecycle implementation reduction

After the R27.2.1 7/7 + 6/6 equivalence gate, all thirteen revision-specific lifecycle scripts are retained only as compatibility shims. Their historical bytes are preserved before replacement.

```bash
scripts/rokid-research connection finalize --revision r25.2.2.2 --run /path/to/run
scripts/rokid-research connection verify-publication --revision r25.2.2.2 --publication /path/to/publication.json
```

Historical runners may still call the old filenames; the live files delegate to these canonical engines.
