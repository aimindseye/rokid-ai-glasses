# Test 21 r3.3.3 — Original-r3 Differential Replication, PCAPdroid/MITM Network Correlation, Rokid-Server Dependency Boundary, and Exact Respawn Trigger Isolation

## Purpose
Recreate the accepted Test 21 r3 sequence while adding synchronized network evidence from PCAPdroid 1.9.1+ and the PCAPdroid MITM addon. The experiment tests whether target-app network requests precede, follow, or are absent around the first Hi Rokid process respawn.

## Network capture
PCAPdroid is controlled through its documented `CaptureCtrl` API. The capture filters both `com.rokid.sprite.global.aiapp` and `org.aimindseye.rokid.cxrphotoqualification`, enables TLS decryption, supplies APP decryption rules for both packages, blocks QUIC only for traffic selected for decryption, enables full payload and PCAPdroid UID/app metadata, and writes a private PCAP plus private SSL key log when available.

The API key is accepted only through the `PCAPDROID_API_KEY` environment variable or hidden terminal input. The runner does not print or persist the key.

## Privacy
Raw PCAP, SSLKEYLOGFILE, raw HTTP/TLS material, headers, bodies, tokens, cookies, device identifiers and complete endpoint data remain under the private evidence root. The sanitized artifact contains only correlation fields, target package names, hostnames, normalized paths with query strings removed and long identifier-like path segments redacted, methods/status codes when offline decryption succeeds, and hashes.

## Interpretation
Network ordering is correlation evidence only. A custom-app request preceding Hi Rokid respawn makes a server/bootstrap dependency a candidate; it does not prove the server caused Android process creation. A respawn preceding target-app network markers favors a local Android/Binder/Bluetooth trigger. A non-reproduced respawn suggests the original r3 event was transient or depended on an unmeasured state.

## Safety
Exactly one Hi Rokid force-stop and exactly one explicit CXR-L connection attempt are allowed. Test 20 host photo arming is never performed. Photo, audio, package disable/uninstall/data clear, Bluetooth toggle, and secondary-package force-stop are absent.
