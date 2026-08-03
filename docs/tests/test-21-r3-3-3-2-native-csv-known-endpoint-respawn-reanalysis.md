# Test 21 r3.3.3.2 — PCAPdroid Native CSV Ground-Truth Recovery, Known-Rokid-Endpoint Timeline Correlation, and Existing-r3.3.3 Respawn Reanalysis

## Purpose

Use PCAPdroid's native Connections CSV as the app-attribution ground truth for Hi Rokid, qualify a hostname/timestamp scanner against the existing r3.3.3.1 private PCAP, then apply the same scanner to the already-collected r3.3.3 private PCAP around the force-stop / button-2 / connection / Hi Rokid respawn boundary.

No Android device operation and no new capture are permitted.

## Ground truth

The operator-exported native CSV has 17 columns and eight Hi Rokid rows. The observed hosts are `www.baidu.com`, `ai-cloud-global.rokid.com`, `device-account-prod.rokid.com`, and `rcs-internal.rokid.com`. The three `*.rokid.com` hosts are treated as the primary known-Rokid endpoint set. Native IP addresses, ports and UID are never copied into sanitized evidence.

## Interpretation guardrails

- A hostname match in r3.3.3 is a known-endpoint correlation, not renewed package attribution for that packet.
- DNS query, TLS ClientHello, HTTP request and HTTP/2 request are treated as connection/request initiation markers.
- An initiation marker before respawn is correlation only; it does not prove a server caused the Android process start.
- Equal connection-attempt and respawn timestamps are reported as `SAME_OBSERVATION_TIMESTAMP`; they are never forced into either ordering.
- No marker is reported as `NO_KNOWN_ROKID_ENDPOINT_INITIATION_AFTER_FORCE`, never as “respawn preceded network.”

## Privacy

Inputs remain private in place. The sanitized package excludes raw PCAP, SSL key logs, raw native CSV, IP addresses, ports, UIDs, headers, cookies and bodies.
