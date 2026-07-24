# Test 18 — USB ADB control path, stale-state risk, cable uncertainty, and recovery boundaries

## Scope

Test 18 is an offline follow-up to the authorized USB-ADB baseline established
in Test 17. It analyzes the exact stock OTA and reviewed static application,
framework, init, SELinux-policy, boot-image, and recovery artifacts.

No command was sent to the glasses during this investigation. No restart,
recovery entry, fastboot operation, sideload, property mutation, application
installation, flashing, or slot change occurred.

The tested scope remains the non-display Rokid AI Glasses Style, global Hi
Rokid environment, and the exact firmware build used by the private evidence
set. Findings can differ across product, region, account, cable, and firmware.

## Evidence labels

- **Observed** — captured during the earlier authorized ADB session.
- **Static finding** — recovered from the exact stock software artifacts.
- **Inferred** — best-supported explanation, not runtime proof.
- **Unresolved** — evidence is insufficient for a reliable conclusion.

## 18A — Developer Mode control path

**Static finding:** the glasses-side settings implementation recognizes:

```text
settings_developer_mode
```

with the values:

```text
on
off
```

The recovered enable path performs the equivalent of:

```text
persist.vendor.adb=true
Settings.Global.adb_enabled=1
```

The recovered disable path performs:

```text
persist.vendor.adb=false
```

No matching `Settings.Global.adb_enabled=0` write was found in the available
disable method.

### Interpretation

This asymmetry makes a stale state possible:

```text
phone or framework indicator: enabled
vendor ADB property:           false
```

The static method proves that the software can create this mismatch. It does
not prove which branch most recently executed on the tested unit or whether the
property write succeeded at runtime.

## 18B — Runtime domain and SELinux property mapping

**Static finding:** the relevant Rokid packages resolve to the `priv_app`
SELinux domain in the analyzed package and `seapp_contexts` evidence:

```text
com.rokid.os.sprite.assistserver → priv_app
com.rokid.cxrservice             → priv_app
com.rokid.sysconfig              → priv_app
```

The vendor property maps to:

```text
persist.vendor.adb → adbd_config_prop
```

The discovered policy sources contained neither:

- a direct, expanded allow rule proving that these targets may set
  `adbd_config_prop`; nor
- an explicit prohibition proving that the write must fail.

**Unresolved:** compiled-policy attribute expansion and live process labels are
still needed to close direct authorization.

A missing text-policy match is not evidence of denial.

## 18C — Cable and debug-board analysis

The real `dtbo` and `vendor_boot` inputs and the earlier exact debug-board
binary candidate were analyzed.

**Static finding:** generic debug-board detection exists in charger-related
code.

**Not found:** no bounded same-function or same-device-tree-node path connected
that debug-board evidence to:

- `persist.vendor.adb`;
- `adbd`;
- USB gadget activation; or
- an official Rokid cable identifier.

Therefore:

```text
firmware cable-ID gate:          not proven
cable or contact cause:          not ruled out
firmware or gadget-state cause:  not ruled out
```

A supported cable can differ without a recognizable firmware string. Possible
differences include data-contact routing, magnetic alignment, signal quality,
a passive strap, or active cable electronics.

### Field context

The researcher reports that the current third-party cable model is used
successfully by multiple other owners. This lowers the probability of a
model-wide incompatibility, but it does not eliminate an individual cable,
contact, alignment, adapter, or unit-specific issue. This field report was not
independently qualified in Test 18.

Rokid support separately advised the researcher that only specified
development/debugging cables are supported and did not guarantee the current
cable. The exact non-display-compatible official cable SKU remains to be
confirmed.

## 18D — Repair-app and recovery boundaries

No exported, unprotected glasses-side component was proven to reach the
Developer Mode setter. A normal user-installed glasses APK is therefore not
assumed capable of directly repairing the state.

A phone-side companion remains a plausible research direction:

```text
query current state
send settings_developer_mode=off
wait for a positive reply
send settings_developer_mode=on
wait for a positive reply
query current state again
```

This design would ask the existing privileged Rokid stack to perform its normal
operation. It remains blocked on exact CXR framing, authentication, device
addressing, request correlation, and reply semantics.

Recovery contains standard ADB/sideload/fastboot-related components and a
generic swipe-capable menu, but the physical gesture mapping and reliable exit
path are unresolved. Blind recovery navigation, sideload, fastboot, slot
changes, and flashing remain outside the approved boundary.

## Cable versus software classification

The current evidence supports a combined-condition model:

```text
Developer Mode setting accepted
AND vendor ADB property is true
AND a usable data/debug attachment exists
AND the USB gadget state machine binds successfully
```

Failure of any condition can produce no USB enumeration.

The earlier fact that this unit exposed authorized USB ADB proves the glasses
and that earlier physical setup were capable of data at that time. It does not
by itself identify why enumeration later disappeared.

## Current conclusions

| Question | Result |
|---|---|
| Exact Developer Mode key and values recovered? | Yes, statically |
| Enable and disable property writes recovered? | Yes, statically |
| Disable-path framework-state asymmetry found? | Yes, statically |
| Rokid package domains bounded? | Yes: `priv_app` |
| Direct `priv_app` property authorization closed? | No |
| Special official-cable code check proven? | No |
| Cable/contact cause ruled out? | No |
| Firmware/gadget-state cause ruled out? | No |
| Safe exported glasses repair component found? | No |
| Phone-side replay ready to implement? | No; protocol/auth closure remains |
| Recovery entry approved? | No |
| Flashing or slot changes approved? | No |

## Next research

The next static phase is not a publication prerequisite. It should independently
address:

1. compiled SELinux-policy and attribute expansion;
2. exact CXR settings request/reply framing and authentication;
3. deduplication and reachability analysis of exported components;
4. a no-restart current-cable versus confirmed compatible official-cable A/B
   comparison.

The unresolved items should remain visible rather than delaying publication of
the bounded findings above.
