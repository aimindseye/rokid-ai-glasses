# Runbook — Test 14A-r2

## Purpose

Compare ChatGPT and Gemini while controlling session history, recognized input,
phone, app, glasses, and capture method.

## Timing rule

Use one pre-wake arm marker. Do not press Enter while invoking or speaking.
Derive question-end and response timing from decrypted `recognized_speech` and
`llm` events.

## Procedure

1. Select the required model.
2. Baseline MediaStore.
3. Start a fresh PCAPdroid capture.
4. Force-stop/relaunch only Hi Rokid.
5. Arm the trial.
6. Say “Hi Rokid,” wait for the cue, and speak the exact question.
7. Do not touch the keyboard during speech.
8. Record the observed recognized request.
9. Export PCAP and SSL key log.
10. Pull only new MediaStore IDs.
11. Treat decrypted final ASR as authoritative.

## Runner

```bash
python3 scripts/tests/run_14a_r2_manual_voice.py --repeats 1 --zip
```

Generated evidence is private.
