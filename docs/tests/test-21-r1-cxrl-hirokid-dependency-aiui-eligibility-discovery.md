# Test 21 r1 — CXR-L / Hi Rokid Runtime-Dependency Discovery and AIUI Eligibility Census

## Objective

Prepare the first standalone-companion ownership experiment without changing runtime state.

Test 20 proved the custom Android path can issue exactly one governed CXR-L photo request and receive an image callback when the same strong image callback object is re-registered after CXR-L/service establishment. Test 21 moves from media-path qualification to **connection and runtime ownership**.

## Questions

1. Which installed phone package is the Hi Rokid runtime/authorization package for this device?
2. Which Hi Rokid processes and services are alive before any ownership mutation?
3. Is the Test 20 custom package installed and visible to Android package management?
4. Is `com.rokid.cxr:client-l:1.0.1` still the resolved local SDK artifact and does its SHA-256 match the accepted Test 20 artifact?
5. Do the repository, CXR-L AAR, or installed phone packages expose AIUI/Ink/JSAR/YodaOS/AIX signals relevant to the non-display glasses?
6. Is there enough evidence to proceed to a reversible Hi Rokid force-stop ownership probe?

## Known global-app anchor

The global Google Play listing identifies Hi Rokid as Android package `com.rokid.sprite.global.aiapp`. r1 treats an exact installed match as the preferred package identity, while preserving `--hi-rokid-package` for operator override.

Official AIUI documentation describes AIUI as an AI + AR local-agent framework with device-side APIs, and the current global Hi Rokid listing mentions AIUI Agent debugging. Neither statement proves AIUI execution on the non-display glasses, so r1 records only static eligibility signals.

## Scope

This revision is read-only. It collects package/process/service/Bluetooth-manager state and local static SDK/repository evidence.

It explicitly does **not**:

- invoke `takePhoto`;
- start audio capture;
- force-stop Hi Rokid;
- disable or uninstall any package;
- change Bluetooth pairing;
- change authorization state;
- modify glasses firmware;
- install or run an AIUI agent.

## AIUI interpretation

AIUI is treated only as a low-cost eligibility branch. Signals such as `aiui`, `.aix`, `Ink`, `JSAR`, `YodaOS`, or related package/runtime names are evidence of possible relevance, not proof that the non-display glasses support AIUI agent execution.

A positive r1 signal can justify a later bounded AIUI-specific discovery test. A negative signal does not affect the already-proven CXR-L Test 20 path.

## r1 terminal states

### `R2_FORCE_STOP_OWNERSHIP_PROBE_READY`

Use when:

- `client-l:1.0.1` is found locally;
- the expected Test 20 AAR hash matches;
- at least one plausible Hi Rokid package is identified;
- no r1 collection failure prevents interpretation.

### `NEEDS_HI_ROKID_PACKAGE_RESOLUTION`

Use when the SDK is found but package ownership remains ambiguous. The next run should supply `--hi-rokid-package` explicitly after operator review.

### `BLOCKED_CXR_L_AAR_NOT_FOUND`

Use when the known-good local CXR-L artifact cannot be located. Resolve the build/dependency cache before modifying Hi Rokid runtime state.

## Planned r2 boundary

After r1 qualifies the package boundary, r2 should perform one reversible phone-side experiment at a time:

1. capture known-good baseline;
2. force-stop the exact Hi Rokid package;
3. verify it remains installed and is not disabled;
4. launch the custom companion only;
5. observe CXR-L/service/Bluetooth ownership without media operations;
6. recover Hi Rokid explicitly;
7. verify the original state is recoverable.

Package disable, uninstall, phone reboot, photo, and audio remain outside the first r2 attempt.
