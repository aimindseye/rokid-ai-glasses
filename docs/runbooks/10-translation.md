# Runbook — Test 10 Translation

## Purpose

Reproduce the architecture findings for Face-to-Face, Online, and Local
translation without collecting unnecessary private data.

This runbook proves execution flow. It is not a translation-accuracy or
audio-quality benchmark.

## Prerequisites

- Rokid AI Glasses paired and connected
- Hi Rokid installed on a compatible Android phone
- ADB authorized for the controlled phone
- Bluetooth enabled
- A second device or generated audio source
- Passive network-capture capability for Online routing
- Sufficient phone storage for the local package
- Target-language Android offline TTS voice for the final Local test

Do not place raw captures, logs, screenshots, model files, serials, account
identifiers, Bluetooth addresses, tokens, or private paths in the Git
worktree.

## Fixed canary

Use one fixed phrase for flow comparison:

```text
The blue bicycle arrives at seven forty-two.
```

Generate one audio file and replay the same file in Local and Online phases.

## 10a — Face-to-Face route

1. Select Face to Face.
2. Keep the companion phone away from the source.
3. Present the source near the glasses.
4. Confirm that translation starts.
5. Correlate the run with application logs that identify the glasses audio
   listener.
6. Confirm Bluetooth A2DP as the output route.

Do not generalize the result to other translation modes.

## 10b — Online service routing

1. Enable functional internet.
2. Disable TLS interception for the application if interception changes
   behavior.
3. Start passive PCAPdroid capture.
4. Select Online, Face to Face, and a fixed language pair.
5. Run the canary once per assistant-model selection.
6. Export connection statistics and application logs privately.
7. Compare service families, not just byte totals.
8. Record any setup error such as an incorrect target language.

Accept the run for architecture only when the corrected successful segments
use the expected translation path.

## 10c1 — Local-model download

1. Confirm the phone is compatible before downloading.
2. Capture package storage inventory before download.
3. Start passive connection capture.
4. Download and install the Local package.
5. Capture package storage inventory afterward.
6. Record the configuration URL, package URL, installed relative path,
   version, sizes, and runtime load result.
7. Document interrupted downloads and capture-tool memory limits.

Do not publish the downloaded archive or model binaries.

## 10c2 — Package metadata

Collect privately:

- file names and sizes,
- full-file SHA-256 hashes,
- small text/configuration files,
- bounded headers from large model files,
- GGUF metadata, and
- ONNX/VAD metadata.

Publish only reviewed metadata and hashes. Do not publish model binaries or
large binary headers.

## 10c3 — Offline execution

1. Confirm the model is installed.
2. Install the target-language Android offline TTS voice.
3. Verify that the Android TTS sample plays with Wi-Fi and mobile data off.
4. Restore the initial network state before starting the scripted run.
5. Start the Local test.
6. Disable Wi-Fi and mobile data while preserving Bluetooth.
7. Force-stop and relaunch Hi Rokid.
8. Select Local, Face to Face, and the fixed language pair.
9. Play the fixed source audio.
10. Capture logs, connectivity state, routes, reachability, TTS engine, and
    Bluetooth output route.
11. Restore the original network state.

A run with local text but failed speech may still prove Local recognition and
translation. It does not prove complete offline spoken output.

## 10c4 — Controlled Local-versus-Online flow

1. Use the same phone, glasses, placement, language pair, and source file.
2. Run Local with Wi-Fi and mobile data disabled.
3. Restore functional internet.
4. Run Online.
5. Keep the source-audio hash in private evidence.
6. Compare:
   - input route,
   - processing host,
   - translation engine,
   - TTS engine,
   - network dependency,
   - output route, and
   - progressive versus final-result behavior.
7. Do not score accuracy or voice quality unless a separate benchmark is
   explicitly designed.

## Android routing warning

Do not require `adb shell ip route` to show a main-table default route.
Samsung and other Android builds may use policy-routing tables.

Use one or more of:

- `ip route show table all`,
- Android connectivity state,
- successful DNS/reachability,
- successful application service startup, and
- observed service connections.

## Public closeout

Publish:

- test report,
- architecture finding,
- endpoint summary,
- local-package metadata,
- controlled-flow summary, and
- hash-only private-evidence manifest.

Run both the repository-wide public-tree validator and the Test 10 validator
before committing.
