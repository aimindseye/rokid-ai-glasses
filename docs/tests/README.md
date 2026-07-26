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

Tests 18A–18D are represented in the master matrix and consolidated findings;
there is not yet a standalone `18-*.md` test report.

## Research-release track

The protected companion investigation uses release identifiers rather than
numbered product tests:

- r22: native-loader and Java-handoff closure;
- r23: startup materialization, external probe, and injection-trigger boundary;
- r24: RealApplication lifecycle/class-origin/MyJni caller analysis;
- r24.1: six-APK differential and exact DEX caller census.

See the [research index](../research/README.md).
