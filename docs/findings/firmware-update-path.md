# Firmware Update Path

## Finding

Hi Rokid sends signed, device-scoped OTA checks after connected launch, when
the firmware page opens, and for every manual check.

## Endpoint

```text
POST https://ota.rokid.com/v1/extended/ota/check
```

Request:

```json
{
  "version": "1.22.009-20260710-151201",
  "osType": "",
  "cpuType": ""
}
```

## Triggers

| Trigger | Result |
|---|---|
| Disconnected launch | No OTA host in original D1 connection summary |
| Connected launch | Automatic live request |
| Firmware page open | Additional live request |
| First manual check | Live request |
| Repeated manual check | Fresh TLS connection/request |

## Response

Included package URL, checksum, changelog, `isForceUpdate`, response version,
package choice, and authorization/result status.

## Version policy

Installed, response, and package-URL version suffixes differed while the app
displayed “The glasses system is the latest version.”

```text
LATEST_VERSION_COMPARISON=HYBRID
```

The response version alone does not explain the UI decision.

## Bluetooth role

Opening the page produced `Ota_MsgNotify`. The raw version payload was not
visible. The app likely obtains/confirms firmware state through the connected
device-control channel before the HTTPS check.

See [Test 14B](../tests/14b-firmware-update-discovery.md).
