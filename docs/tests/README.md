# Tests and Qualification History

- [Master test and research matrix](test-matrix.md)
- [Current project status](../project-status.md)

## Numbered reports

| Range | Subject |
|---|---|
| 00–06 | First launch, login, TLS, model selection, device connection |
| 10 | Translation architecture and local/online behavior |
| 14 | Assistant routing and OTA checks |
| 15 | Visual AI capture, routing, and retention |
| 16 | Android lifecycle, package lineage, and privacy |
| 17 | Glasses Android, USB ADB, local services, and passive networking |
| 18 | Developer Mode and USB ADB control-path static/offline follow-up |
| 19–21 | CXR-L companion qualification, photo/callback behavior, and static Binder-boundary closure |

Tests 18A–18D are represented in the master matrix and consolidated findings;
there is not yet a standalone `18-*.md` test report.

Test 21 closes the accepted static CXR-L Binder boundary for `client-l:1.0.1`; the detailed revision chain remains historical lineage rather than the primary navigation model. See the [Test 21 overview](../research/cxr/test21-static-binder-boundary-overview.md) and [canonical tooling policy](../research/tooling/README.md).

## Research-release track

The protected companion investigation uses release identifiers rather than
numbered product tests:

- r22: native-loader and Java-handoff closure;
- r23: startup materialization, external probe, and injection-trigger boundary;
- r24: RealApplication lifecycle/class-origin/MyJni caller analysis;
- r24.1: six-APK differential and exact DEX caller census.

See the [research index](../research/README.md).

<!-- r27.1.12-tool-test-oracles -->
## Tests 19–21 regression-oracle policy

The 38 current `test_*_tools.py` suites are intentionally retained as independent regression oracles. Use `scripts/rokid-research test verify-oracles` to check their exact source locks and `scripts/rokid-research test run --list` to enumerate the registered suites. See [R27.1.12](../research/r27.1.12-tool-test-oracle-preservation.md).

