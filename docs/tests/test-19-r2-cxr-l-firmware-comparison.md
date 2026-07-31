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

## r2.1 exact client-l 1.0.1 API-surface repair

The first physical preparation run proved that the published `client-l:1.0.1`
AAR does not contain `com.rokid.cxr.link.utils.GlassInfo`. The original r2
synthetic stubs incorrectly invented that class and three callback methods.
r2.1 removes the unsupported callbacks, attests the real four-method
`ICXRLinkCbk` surface, preserves a private class inventory and `javap` report,
and prevents resolver failures from being misreported as APK-install failures.
No glasses or Hi Rokid operation occurs during this repair.
