# Runbook — Test 15B Visual Routing, Retention, and Context

## Purpose

Resolve visual route switching, grounded follow-up behavior, and conversation
thumbnail retention after online/offline Hi Rokid process restarts.

This is not a broad visual-accuracy benchmark.

## Preconditions

- Glasses already powered on, connected, and stable
- Gemini selected before B1
- Photo A and Photo B ready on the iPad
- Each photo has a distinctive detail deliberately omitted from the first
  answer prompt
- Bluetooth remains enabled throughout
- No glasses restart or power cycle

## Default phases

| Phase | Action |
|---|---|
| B1 | Capture Gemini → ChatGPT selection and Photo-A request |
| B2 | ChatGPT grounded follow-up |
| B3 | Offline Hi Rokid restart and history reopen |
| B4 | Online Hi Rokid restart and history reopen |
| B5 | Capture ChatGPT → Gemini selection and Photo-B request |
| B6 | Gemini grounded follow-up |

## Example

```bash
python3 scripts/tests/run_15b_visual_routing_retention.py \
  --photo-a "A-skyline" \
  --chatgpt-initial-question \
    "Describe only the major objects. Do not identify the city or landmark shown on the screen." \
  --chatgpt-followup-question \
    "Which landmark was visible on the tablet screen?" \
  --chatgpt-expected-detail \
    "One World Trade Center" \
  --photo-b "B-smartwatches" \
  --gemini-initial-question \
    "Describe only the major objects. Do not mention any times or numbers visible on the watches." \
  --gemini-followup-question \
    "What time was shown on the round watch?" \
  --gemini-expected-detail \
    "4:49" \
  --pull-new-phone-images \
  --bugreport \
  --zip
```

The script captures every phase separately and never restarts or power-cycles
the glasses.

Generated evidence is private.
