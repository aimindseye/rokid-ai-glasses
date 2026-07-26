# Protected-Application Machine-Readable Publication

This directory contains the sanitized r24.1 review artifacts.

- `accepted-evidence-review.json` — overall accepted baseline/enhanced review
- `class-origin-differential.json` — runtime-only versus six-APK origin changes
- `exact-dex-caller-census.json` — physical and deduplicated logical MyJni sites
- `myjni-caller-census.csv` — tabular 11-method caller status
- `real-application-lifecycle.json` — bounded RealApplication lifecycle status
- `protected-application-evidence-flow.mmd` — Mermaid source for the evidence flow

These artifacts publish reviewed counts, class/method contracts, bounded
classifications, and hashes. They do not contain APKs, DEX files, native
libraries, raw runtime events, device identifiers, or private paths.
