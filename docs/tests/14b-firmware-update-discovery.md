# Test 14B — Hi Rokid Firmware Update Discovery

## Final disposition

**Status: PASS for connected firmware-check behavior**

The captured evidence establishes how Hi Rokid checks Rokid AI Glasses firmware:

1. The app obtains or retains the installed glasses firmware version while the glasses are connected.
2. It sends a signed HTTPS `POST` request to Rokid's OTA service.
3. The request includes the installed firmware version and device-scoped authorization metadata.
4. Rokid returns a complete OTA manifest containing a candidate package URL, checksum, changelog, force-update flag, version metadata, and package-selection value.
5. Hi Rokid interprets the response and displays either update availability or “The glasses system is the latest version.”

The comparison is best classified as **hybrid**: the server receives the current version and selects/returns OTA metadata, while the app interprets that metadata and renders the final latest/update state.

## Evidence bundles

### Connected bundle

`14b-firmware-check-connected-20260720-112547-private-evidence.zip`

SHA-256:

`9a15df28efcc9ac3506615e58b736e3412dc64b744bb7c102c3f9dfc1c1149a1`

Validation:

- 62 manifest entries verified
- 4 PCAP files
- 4 SSL key logs
- All four `ota.rokid.com` TLS sessions decrypted successfully
- No OTA TLS application record failed authentication/decryption

### Disconnected bundle

`14b-firmware-check-disconnected-20260720-103939-private-evidence-finalized.zip`

SHA-256:

`28f92d82f1eda60afd98ca06f1298d2c2f1c89a70cd9138b955eb1d0f6d43134`

Validation:

- 25 manifest entries verified
- Original D1 connection CSV shows no contact with `ota.rokid.com`
- The recovered raw PCAP begins at approximately 10:45:12 and aligns with the aborted D2 attempt rather than the original D1 interval
- D1 raw-packet completeness is therefore **PARTIAL**
- The disconnected no-OTA conclusion is supported by the original D1 connection CSV, not by the recovered raw PCAP

## Test environment

- Hi Rokid package: `com.rokid.sprite.global.aiapp`
- Hi Rokid version: `G1.10.11.0713`
- Version code: `10100011`
- Phone: Samsung `SM-S938U1`
- Android: 16
- Installed glasses firmware displayed by Hi Rokid: `1.22.009-20260710-151201`
- Auto update displayed: `Off`

Sensitive account, device, signature, and authorization values are omitted from this report.

## Trigger behavior

| Phase | Observed trigger | OTA requests | Result |
|---|---|---:|---|
| D1 | App cold launch while glasses disconnected | 0 | No OTA lookup observed |
| C1 | App cold launch while glasses connected | 1 | Automatic OTA lookup |
| C2 | Connected app cold launch | 1 | Automatic OTA lookup |
| C2 | Firmware/System page opened | 1 additional | Page entry triggers another lookup |
| C3 | First manual Check for Updates press | 1 | Fresh live OTA lookup |
| C4 | Repeated manual Check for Updates press | 1 | Fresh live OTA lookup; not satisfied solely from cache |

### Timing evidence

- C1 app restart completed around 11:26:06; OTA request authorization time was 11:26:11.
- C2 app restart completed around 11:29:39; first OTA request authorization time was 11:29:44.
- `SettingsOtaActivity` opened around 11:30:00; C2's second OTA request used authorization time 11:30:00.
- C3 touch occurred around 11:32:14; its OTA request used authorization time 11:32:14.
- C4 touch occurred around 11:34:13; its OTA request used authorization time 11:34:13.

This confirms three connected triggers:

- automatic check after connected app launch,
- automatic check when the firmware page opens,
- explicit manual check.

## OTA request

All five decrypted checks used:

```text
POST /v1/extended/ota/check HTTP/1.1
Host: ota.rokid.com
Content-Type: application/json;charset=utf-8
```

Request body:

```json
{
  "version": "1.22.009-20260710-151201",
  "osType": "",
  "cpuType": ""
}
```

The signed `Authorization` header contained:

- protocol version
- request timestamp
- request signature
- application/service key
- device-type identifier
- device identifier
- `service=ota`

The exact sensitive values are intentionally redacted.

## OTA response

All five checks returned HTTP 200 and byte-identical JSON bodies.

Important response fields:

| Field | Observed value |
|---|---|
| `code` | `OK` |
| `authorize` | `true` |
| `isForceUpdate` | `false` |
| `packageChoice` | `"1"` |
| `version` | `1.22.009-20260710-153201` |
| package URL version component | `1.22.009-20260710-150201` |
| checksum | `516e268b35a3b9ac6359d6ae22a25edc` |
| changelog | Multilingual YodaOS-Sprite update notes |

The response included a complete package URL under Rokid's OTA CDN and stated that the release requires the latest Rokid Glasses app.

## Version-resolution finding

The displayed installed version, response metadata version, and package URL version are not identical:

| Source | Version |
|---|---|
| Installed/displayed firmware | `1.22.009-20260710-151201` |
| Response `version` field | `1.22.009-20260710-153201` |
| Package URL component | `1.22.009-20260710-150201` |

Despite these differing timestamp suffixes, Hi Rokid displayed:

> The glasses system is the latest version

Therefore, the app does **not** appear to perform a simple lexical or numeric greater-than comparison using only the response's `version` field.

The exact internal rule is not visible, but the evidence supports a hybrid policy involving some combination of:

- the version submitted to the OTA server,
- server-side device/package selection,
- `packageChoice`,
- the package represented by the returned URL,
- and client-side interpretation of the returned manifest.

## Bluetooth role

The firmware page is unavailable when the glasses are disconnected. When the page opened during C2, logcat recorded:

```text
recv Notify: cmd Ota
onNotify cmd:Ota
onNotify subCmd:Ota_MsgNotify
status:RESPONSE_SUCCEED
```

The OTA HTTPS request body then contained the same firmware version shown in the UI.

**Best-supported interpretation:** Hi Rokid obtains or confirms installed firmware state over its connected Bluetooth/device-control channel, then submits that version to Rokid's OTA server.

The captured log does not expose the raw Bluetooth payload containing the version, so the exact Bluetooth command structure remains unresolved.

## Caching behavior

C3 and C4 each opened a new TLS connection to `ota.rokid.com`, sent a new signed request with a new timestamp/signature, and received a new HTTP 200 response.

Therefore:

`REPEATED_MANUAL_CHECK=LIVE_SERVER_REQUEST`

The app may cache the resulting display state, but it did not rely exclusively on cached OTA metadata when the button was pressed again.

## Final assertions

| Assertion | Status |
|---|---|
| `DISCONNECTED_LAUNCH_OTA_CHECK` | **NOT OBSERVED** |
| `CONNECTED_LAUNCH_OTA_CHECK` | **CONFIRMED** |
| `FIRMWARE_PAGE_OPEN_OTA_CHECK` | **CONFIRMED** |
| `MANUAL_CHECK_OTA_REQUEST` | **CONFIRMED** |
| `REPEATED_CHECK_LIVE_REQUEST` | **CONFIRMED** |
| `OTA_ENDPOINT` | **CONFIRMED: `/v1/extended/ota/check`** |
| `CURRENT_VERSION_SENT_TO_SERVER` | **CONFIRMED** |
| `DEVICE_SCOPED_SIGNED_AUTHORIZATION` | **CONFIRMED** |
| `FULL_OTA_MANIFEST_RETURNED` | **CONFIRMED** |
| `FORCE_UPDATE_FLAG_RETURNED` | **CONFIRMED** |
| `PACKAGE_CHECKSUM_RETURNED` | **CONFIRMED** |
| `RELEASE_NOTES_RETURNED` | **CONFIRMED** |
| `SIMPLE_RESPONSE_VERSION_COMPARISON` | **NOT SUPPORTED** |
| `LATEST_VERSION_COMPARISON` | **HYBRID** |
| `D1_RAW_PCAP_ASSOCIATION` | **PARTIAL / MISMATCHED RECOVERY** |
| `CONNECTED_TEST_EVIDENCE` | **PASS** |

## Final conclusion

Hi Rokid checks firmware by combining connected-device state with Rokid's OTA service. It automatically performs the check after a connected app launch, checks again when the firmware page opens, and performs a fresh server request for every manual button press.

The app submits the installed firmware version to `ota.rokid.com/v1/extended/ota/check` using signed, device-scoped authorization. Rokid returns a full OTA manifest rather than a simple boolean. Hi Rokid then applies additional policy to decide what to show, because the server's `version` field alone does not explain the displayed “latest version” result.
