# Controlled-Capture Toolkit Quick Start

## Private workspace

```bash
./scripts/capture/create_test_workspace.sh \
  --root "$HOME/private-rokid-tests" \
  --test-id example-voice-canary-r1
```

## Marker timeline

```bash
python3 scripts/capture/run_voice_marker_controller.py \
  --timeline "$TEST_ROOT/notes/normalized-voice-action-timeline.tsv" init
```

Record each marker with the same command and `mark MARKER`.

## MediaStore inventory

```bash
./scripts/capture/query_mediastore.sh \
  --user 10 \
  --output "$TEST_ROOT/notes/mediastore-inventory-private.txt"
```

## WebSocket export

```bash
./scripts/analysis/export_websocket_occurrences.sh \
  --pcap "$TEST_ROOT/pcap/$PCAP_NAME" \
  --keylog "$TEST_ROOT/pcap/$KEYLOG_NAME" \
  --output "$TEST_ROOT/decrypted/websocket-occurrences-private.tsv"
```

## Controlled phrase scan

Create a private JSON object mapping safe labels to exact controlled phrases, then run:

```bash
python3 scripts/analysis/analyze_canary_matches.py \
  --websocket-tsv "$TEST_ROOT/decrypted/websocket-occurrences-private.tsv" \
  --terms-json "$TEST_ROOT/notes/controlled-terms-private.json" \
  --private-matches "$TEST_ROOT/decrypted/canary-matches-private.tsv" \
  --safe-summary "$TEST_ROOT/notes/canary-safe-summary.json"
```

## Repository gate

```bash
./scripts/tests/run_synthetic_fixture_tests.sh
./scripts/safety/scan_public_artifacts.sh --repo . --staged
```
