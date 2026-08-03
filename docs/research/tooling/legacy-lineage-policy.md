# Legacy Script and Revision-Lineage Policy

## Principle

Research revision numbers preserve how a conclusion was reached. They should remain auditable, but they should not remain the permanent developer interface.

## R27 dispositions

Every legacy script family is assigned one of these migration dispositions:

| Disposition | Meaning |
|---|---|
| `CANONICAL_CANDIDATE` | Single non-revision implementation; candidate to keep directly or move behind the canonical interface. |
| `CONSOLIDATE_FAMILY` | Multiple related implementations; shared behavior must be extracted and equivalence-tested before retirement. |
| `PRESERVE_LINEAGE_PENDING_MIGRATION` | Revision-specific historical implementation; retain until a successor is proven and its lineage is recorded. |

No legacy script is removed by R27.1.0.

## Safety classification

The catalog intentionally uses conservative classifications:

- `HOST_ANALYSIS_CANDIDATE`
- `DEVICE_OR_PRIVILEGED_REVIEW_REQUIRED`
- `REVIEW_REQUIRED`

The classification is a review aid, not permission to run a script. Historical device/Frida/Magisk/ADB collectors remain governed by their original runbooks and safety gates.

## Retirement gate

A revision implementation may be retired from the active tree only after all of the following are true:

1. its source is preserved in the R27 historical source archive;
2. unique behavior has a named canonical successor;
3. fixtures or accepted evidence prove equivalent interpretation/output where applicable;
4. documentation points to the canonical interface and the history/supersession record;
5. public/private publication status has been reviewed;
6. no required evidence lineage depends on the working-tree path remaining present.

## Publication rule

The local worktree can contain historical research that is not suitable for automatic public publication. R27 inventory output that includes untracked paths is private by default. Public GitHub publication must use an explicitly reviewed subset.

## Container-compatibility rule

Whole-archive SHA-256 equivalence is only a retirement requirement when the historical format itself is deterministic. For historical packagers that intentionally inherit source filesystem ZIP metadata, compatibility is defined by the same archive-member ordering, member bytes, compression method, permission metadata, and source-metadata behavior. The canonical profile must explicitly opt into that historical mode; deterministic packaging remains the default for new tooling.

## Source-contract hash-chain migration

When a historical implementation is referenced only as an identity prerequisite by a later source-contract checker, retirement may proceed only after: (1) the original implementation and every modified checker are privately archived with SHA-256 identities; (2) the compatibility shim is independently package-equivalent; (3) all affected prerequisite hashes are migrated transitively through the source-contract chain; and (4) every applicable source-contract checker preserves its pre-migration PASS behavior. R27.1.9 applies this rule to eleven Test 21 packagers.

## Compatibility-caller rule

A historical caller does not block implementation retirement when the referenced legacy path is itself a verified compatibility shim. The path remains stable for reproducibility, but the duplicated implementation has already been removed. Source-contract, test, and runner references to a locked shim are therefore recorded as compatible inbound references rather than as active implementation blockers.

R27.1.10 applies this rule to the final sixteen Test 21 packagers after preservation, package-member equivalence, source-contract hash-chain migration, and tool-suite regression validation.

## Accepted-source snapshot retirement rule

A historical source-contract checker may be reduced to a compatibility shim when its accepted current-tree execution has been captured and converted into an independent declarative closure. The closure must preserve the original checker bytes privately, retain the historical success output, exact-lock all accepted source files observed by the contract, replace checker-to-checker SHA dependencies with explicit canonical contract-lineage edges, and reject source drift without executing the archived implementation.

The snapshot contract is intentionally stronger than historical marker-only predicate logic: changes that might have passed an old marker check can still fail because the accepted file identity changed. Updating such a profile therefore requires an explicit reviewed successor migration rather than silent hash refresh.

R27.1.11 applies this rule to all 29 active Test 21 source-contract checkers. Their historical paths remain callable as compatibility shims; no repository path is deleted.

<!-- r27.1.12-regression-oracle-policy -->
## Independent regression-oracle exception

A historical file is not automatically a retirement target merely because a canonical dispatcher exists. If the file is an independent regression oracle whose value comes from testing the canonical implementation through a separate assertion/fixture path, it is preserved as `PRESERVE_REGRESSION_ORACLE`.

Preserved regression oracles must remain source-locked, independently executable, and covered by the canonical suite registry. They are not counted as unresolved retirement work. This policy prevents consolidation from collapsing implementation and verification into the same code path.

