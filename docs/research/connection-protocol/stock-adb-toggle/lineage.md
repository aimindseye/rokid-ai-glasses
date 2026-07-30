# Stock ADB Toggle Research Lineage

| Release | Standing | Retained conclusion |
|---|---|---|
| `r1.3.3.2.25.3` pre-repair | Rejected | Proved the local `persist.vendor.adb=true → false → true` transition, but incorrectly required the existing authorized USB ADB transport to disappear. |
| `r1.3.3.2.25.3.1` | Repair package | Corrected the semantic disable oracle; the first physical attempt exposed an operator-arm sequencing race. |
| `r1.3.3.2.25.3.1.1` | Accepted source capture; initial analysis incomplete | Completed two disable and two enable stock actions, restored the final state, retained a usable control channel, and captured a post-action bugreport. Initial analysis rejected every HCI member because two parse errors were not yet scoped to the target handle/CID pairs. |
| `r1.3.3.2.25.3.1.2` | Accepted | Reanalyzed the existing capture offline, retained non-target-CID errors as diagnostics, qualified the target pairs, attributed DLCI 6 UIH payloads, and proved the repeated enable/disable differential. |
| `r1.3.3.2.25.3.1.3` | Accepted | Closed the exact observed ADB-toggle message grammar, nested length, monotonic sequence candidate, action discriminator, and structured state role without contacting a device. |
| `r1.3.3.2.25.3.1.4` | Publication integration | Integrates sanitized findings, methods, limitations, runtime status, evidence hashes, navigation, and generic host-only verification tooling. |
| `r1.3.3.2.25.3.1.4.2` | Current packaging repair | Adds the exact r25.3.1 and r25.3.1.1 documentation and generic tools to the bounded publication so the complete 18-path lineage is committed rather than ignored. |

The accepted r25.3.1.2 and r25.3.1.3 results do not erase the earlier failures.
Those failures remain part of the audit trail because they explain the semantic
oracle repair, operator-arm repair, and target-pair-scoped parser qualification.

## Published lineage files

The repository publication includes the exact five-file r25.3.1 and five-file
r25.3.1.1 overlays as superseded audit lineage, together with the accepted
r25.3.1.2 and r25.3.1.3 analyzers and documents. Inclusion preserves the repair
trail; it does not change the standing of any failed intermediate run.
