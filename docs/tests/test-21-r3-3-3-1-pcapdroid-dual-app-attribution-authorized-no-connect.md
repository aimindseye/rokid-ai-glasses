# Test 21 r3.3.3.1 — PCAPdroid Dual-App Attribution Qualification and Authorized-No-Connect Network Baseline

## Purpose
Qualify PCAPdroid application attribution after both Hi Rokid and `org.aimindseye.rokid.cxrphotoqualification` have been explicitly added to PCAPdroid Target Apps and TLS Decryption. This test does not force-stop Hi Rokid and does not start CXR-L. It separates ordinary Hi Rokid traffic, custom-app idle traffic, and authorization-only traffic.

## Sequence
1. Confirm both apps are selected in PCAPdroid Target Apps and TLS Decryption.
2. Start a PCAPdroid capture through the documented `CaptureCtrl` API with both apps in `app_filter` and `decryption_rules`.
3. Capture a 15-second normal Hi Rokid baseline while the custom app is stopped.
4. Launch the custom app and capture 10 seconds without authorization or connection.
5. Authorize exactly once through Hi Rokid, return to the custom app, and capture 20 seconds with no CXR-L connection attempt.
6. Stop PCAPdroid, pull the private PCAP/key log, parse PCAPdroid UID trailers, and correlate decrypted HTTP rows.

## Attribution repair
The r3.3.3 parser associated decrypted HTTP rows only by flow tuple. MITM/VPN transformation can change tuples. r3.3.3.1 instead maps `tshark frame.number` to the PCAPdroid UID trailer on the exact PCAP frame first. Flow tuple is only a fallback. This is intended to resolve the prior state where 26 HTTP rows decrypted but zero target HTTP rows were attributed.

## Interpretation
`BOTH_TARGET_PACKET_ATTRIBUTION_PROVEN` proves both target package identities occur in PCAPdroid UID metadata. `HI_ATTRIBUTION_PROVEN_CUSTOM_NETWORK_SILENT` means capture attribution worked for Hi Rokid while the custom app produced no packet rows; it does not imply the custom app was omitted from PCAPdroid. `TARGET_HTTP_ATTRIBUTION_PROVEN` proves at least one decrypted HTTP row can be assigned to either target package.

## Safety/privacy
No Hi Rokid force-stop, no button-2/CXR-L attempt, no photo, no audio, no Bluetooth mutation, and no package clear/uninstall/disable. Raw PCAP, SSL key log, headers, bodies, cookies, tokens, IP addresses, and raw decrypted payload remain private. Sanitized output contains target package names, counts, hostnames, redacted paths, methods/statuses, attribution method, and phase only.
