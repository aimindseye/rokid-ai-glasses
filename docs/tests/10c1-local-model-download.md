# Test 10c1 — Local-Model Download Provenance

## Status

Complete — PASS.

## Question

Where does Hi Rokid obtain the compatible-phone local model, and where is it
installed?

## Method

A compatible Samsung phone was paired with the glasses. The local-model
download was observed with:

- passive PCAPdroid connection statistics,
- Android and application logs,
- before/after package storage inventory,
- screenshots retained privately, and
- post-install runtime loading evidence.

## Download configuration

Observed configuration document:

```text
https://ota-g.rokidcdn.com/sdk/AI/wend/android.latest.json
```

Observed package:

```text
https://ota-g.rokidcdn.com/sdk/AI/wend/v2.7.0/android.zip
```

The package was identified as:

- name: `wend`
- version: `v2.7.0`
- sequence/version code: `627`
- advertised size: approximately `972 MB`
- minimum application SDK marker: `1.0.5` / code `105`

## Installation

The model was installed beneath the application's external-files directory:

```text
Android/data/com.rokid.sprite.global.aiapp/files/wend
```

The final installed file total was:

```text
1,019,916,502 bytes
972.67 MiB
```

Runtime logs subsequently showed successful loading of the `wend` model from
that phone-side directory.

## Download caveats

The download failed and resumed multiple times before completion. Aggregate
connection sizes are consistent with partial reuse, but HTTP Range semantics
could not be proven because the transfer remained encrypted.

PCAPdroid disabled full payload capture after a low-memory warning. DNS,
hostnames, connection timing, byte counts, application logs, and filesystem
changes remained available and were sufficient for provenance and
installation findings.

## Result

The Local model is a phone-hosted package downloaded from Rokid's CDN. It is
not delivered from the glasses and is not executed on the glasses in the
tested configuration.
