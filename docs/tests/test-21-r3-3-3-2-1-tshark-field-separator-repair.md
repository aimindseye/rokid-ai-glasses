# Test 21 r3.3.3.2.1 — tshark Field-Separator Repair, 4/4 Ground-Truth Qualification, and Existing-r3.3.3 Known-Rokid-Endpoint Respawn Reanalysis

## Purpose

Repair the r3.3.3.2 offline hostname scanner without performing a new device experiment. The previous scanner used an incorrect tshark field separator representation and failed calibration even though direct tshark diagnostics recovered all four native PCAPdroid ground-truth hosts.

## Inputs

This analysis reads existing private evidence only:

- Test 21 r3.3.3 private evidence directory;
- Test 21 r3.3.3.1 private evidence directory;
- the native PCAPdroid connections CSV exported for r3.3.3.1;
- local `tshark`.

No private PCAP, SSL key log, raw CSV, IP address, port, or UID is copied into the sanitized package.

## Fixed scanner contract

The analyzer invokes tshark with `-E separator=/t` and parses tab-separated fields. It performs independent scans for:

- DNS queries;
- TLS ClientHello SNI;
- HTTP/1 requests;
- HTTP/2 requests.

Before r3.3.3 can be interpreted, the r3.3.3.1 calibration capture MUST recover exactly 4/4 native Hi Rokid hosts within 5 seconds of the native PCAPdroid `FirstSeen` timestamps:

- `www.baidu.com`;
- `ai-cloud-global.rokid.com`;
- `device-account-prod.rokid.com`;
- `rcs-internal.rokid.com`.

If calibration is not exactly 4/4, the analyzer exits nonzero and prints `R333_NETWORK_CONCLUSION=WITHHELD`.

## r3.3.3 correlation boundaries

Only the three `*.rokid.com` hosts are used for the server-dependency interpretation. Markers are classified relative to:

1. Hi Rokid force-stop;
2. button-2 NOW prompt;
3. the earliest connection/respawn observation boundary;
4. post-boundary activity.

The connection-attempt/Hi-Rokid-respawn ordering retains the corrected r3.3.3 semantics: equal timestamps are reported as `SAME_OBSERVATION_TIMESTAMP`, not forced into either causal direction.

## Interpretation

A known Rokid endpoint initiation after force-stop and before the button prompt is the strongest server/background-runtime correlation this existing capture can provide. Activity only at or after the connection/respawn boundary instead supports a local CXR-L/service activation interpretation more strongly. All network statements remain correlation, not causation.

## Safety

- device operation: NONE
- ADB operation: NONE
- new capture: NONE
- Hi Rokid force-stop: NONE
- CXR-L connection attempt: NONE
- photo operation: NONE
- audio operation: NONE
