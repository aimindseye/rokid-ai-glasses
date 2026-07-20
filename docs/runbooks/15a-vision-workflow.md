# Runbook — Test 15A Visual Workflow Discovery

## Purpose

Map the complete visual request path without scoring answer accuracy.

## Preconditions

- Glasses already powered on, connected, and stable
- Android phone authorized through ADB
- PCAPdroid TLS interception and SSL key export working
- iPad mini displaying locally stored, non-sensitive photos
- No glasses restart or power cycle during the run

## Default phases

| Phase | Action |
|---|---|
| V0 | Connected ChatGPT idle baseline |
| V1 | Open/remain in visual-assistant entry without a request |
| V2 | Fresh ChatGPT visual question with Photo A |
| V3 | Fresh Gemini visual question with the same Photo A |
| V4 | Same Gemini conversation, switch to Photo B and ask again |
| V5 | Vague image-context follow-up without deliberate camera entry |

## Fixed visual question

```text
What do you see in front of me?
```

## Runner

```bash
python3 scripts/tests/run_15a_vision_workflow.py \
  --photo-a "A-landscape" \
  --photo-b "B-household-objects" \
  --photo-c "C-text-or-sign" \
  --pull-new-phone-images \
  --bugreport \
  --zip
```

The script never restarts or power-cycles the glasses.

Generated evidence is private.
