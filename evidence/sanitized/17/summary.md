# Test 17 — Public Summary

The tested US non-display Rokid AI Glasses Style unit is a complete Android 12
`user/release-keys` device. The original Rokid data/debug cable exposed
RSA-protected USB ADB as `model:RG_glasses`; wireless ADB was disabled.

Android boot properties reported `verifiedbootstate=orange` and
`vbmeta.device_state=unlocked`. The origin was not determined, and no root,
fastboot, flashing, relocking, remount, or partition modification was attempted.

The device contained no ordinary user-installed third-party apps, but it ran a
privileged Rokid assistant stack, OTA/configuration/CXR/media components, and a
preloaded AntPay service. Eight privately preserved vendor APKs matched their
device-side SHA-256 hashes.

A root TEE-domain `GateServiced` process was attributed with very high
confidence to the persistent `0.0.0.0:8341` listener. No request was sent to the
port. At idle and during one voice and one fresh-image visual-AI workflow, the
glasses did not activate `wlan0`, `p2p0`, Wi-Fi Aware, or an IPv4 route. The
paired phone remained the strongly supported stock-AI network gateway.

Public artifacts exclude serials, addresses, ADB keys, raw dumps/logs, APKs,
partition maps, and partition images.
