# Glasses Local Services and TCP Port 8341

## Privileged on-glasses stack

The glasses ran a privileged Rokid assistant process with active services for
instruction handling, media, system functions, TTS, payments, Bluetooth,
Wi-Fi, a controllable web-server component, and the master assistant.

Additional preloaded components handled OTA, device configuration, CXR,
live/media behavior, screen streaming, launcher behavior, and AntPay.

This establishes a richer device-side architecture than the earlier
phone-centric network captures alone could reveal.

## GateServiced

A root process launched by Android init was observed:

```text
GateServiced
/vendor/bin/GateServiced
UID/GID 0/0
SELinux u:r:tee:s0
```

It retained all capability bits supported by the captured kernel, with
`NoNewPrivs=0` and `Seccomp=0`.

A TCP listener remained present on `0.0.0.0:8341`. `/proc/net/tcp` attributed
the socket to UID 0. Direct cross-process file-descriptor inspection was denied
on the production build. GateServiced is therefore identified as the listener
owner with very high confidence, not by a direct readable FD link.

## Not the Android WebServerService

The Java `WebServerService` component existed, but its own logs reported its
internal server disabled and not running. Port 8341 must not be described as
the stock Wi-Fi/P2P web server on this evidence.

## Reachability during tested workflows

At idle and during one voice and one fresh-image visual-AI question:

```text
wlan0:       DOWN
p2p0:        DOWN
wifi-aware0: DOWN
IPv4 route:  none
```

The listener had no active non-loopback IP interface exposing it to the home
LAN or a P2P peer. A wildcard bind is not the same as Internet reachability.

No packet was sent to TCP 8341. This repository publishes no protocol,
payload, fuzzing, or exploit material.

## Payment clarification

`com.iap.mobile.ar_pay` and `Glass2PayService` were preloaded and actively
bound by the Rokid assistant server. This supports an on-glasses AntPay/Rokid
capability source for the earlier payment configuration. It does not show a
bound payment account or wallet credential access.

See [Test 17](../tests/17-glasses-os-adb-and-network-exposure.md).
