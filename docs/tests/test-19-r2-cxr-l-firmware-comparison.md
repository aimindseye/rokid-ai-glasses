# Test 19 r2 — CXR-L Authorization and Firmware Comparison

This test replaces the withdrawn Test 19 r1 CXR-M ownership workflow. It keeps
Hi Rokid active and qualifies one CXR-L `CUSTOMAPP` session on YodaOS-Sprite
1.22, then repeats the same client after the offered 1.23 firmware update.

Canonical execution instructions are in the
[Test 19 r2 developer runbook](../developer/companion-app/test-19-r2-qualification.md).

## Acceptance boundary

- exact Hi Rokid `G1.11.11.0727`;
- exact CXR-L `client-l:1.0.1` artifact attestation;
- Hi Rokid authorization token received but never logged;
- `onCXRLConnected(true)` observed;
- `onGlassBtConnected(true)` observed;
- clean disconnect;
- stock Hi Rokid recovery;
- optional separate PCAPdroid metadata gate;
- no media, upload, reboot, unpair, or force-stop operations.
