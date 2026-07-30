# Stock ADB Toggle Protocol — Accepted Publication

This directory is the sanitized, current publication for the stock Hi Rokid
**Glasses ADB debugging** toggle research. It preserves the exact r25.3.1 semantic-oracle and r25.3.1.1 operator-arm
repair lineage, and integrates the accepted `r1.3.3.2.25.3.1.2` target-pair
qualification with the accepted `r1.3.3.2.25.3.1.3` exact observed-frame
grammar closure.

## Current standing

The stock workflow produced two disable and two enable observations. Every
semantic transition passed, the control channel remained usable, and the final
state returned to its initial `on` value. Host ADB transport disappearance is
not required by the stock disable semantics.

The lossless HCI capture contains eight target DLCI 6 frames, seven with
application payload. Two malformed RFCOMM candidates were retained as private
diagnostics but occurred on a non-target dynamic CID and do not invalidate the
target channel. The target pairs contain no RFCOMM parse error.

For the four action-specific outbound messages, the observed family has exact
self-inclusive outer and nested lengths, stable field order, one monotonic
one-byte transaction/sequence candidate, repeat-stable action discriminators,
and structured `on`/`off` state correlated with both the stock UI and
`persist.vendor.adb`.

## Read the publication

- [Lineage](lineage.md)
- [Findings](findings.md)
- [Methodology](methodology.md)
- [Limitations](limitations.md)
- [Integrated runtime status](runtime-status-summary.json)
- [r25.3.1.2 source runtime status](r25.3.1.2-runtime-status-summary.json)
- [r25.3.1.3 source runtime status](r25.3.1.3-runtime-status-summary.json)
- [Evidence hashes](evidence-hashes.txt)
- [Sanitized evidence summary](../../../../evidence/sanitized/stock-adb-toggle/summary.txt)

## Safety boundary

No captured payload is published or replayed. No custom RFCOMM transmission,
ADB command, fastboot command, boot, flash, stock toggle, or device contact is
performed by this publication package. The private analysis archives remain
outside the repository; only their SHA-256 identities are published.
