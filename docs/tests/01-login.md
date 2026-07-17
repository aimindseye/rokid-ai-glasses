# Test 01 — Login and Cloud Initialization

## Purpose

Measure the network delta introduced by logging into Hi Rokid without yet
submitting an AI prompt.

## Result

Completed on 2026-07-16.

Newly observed hostnames included:

- `ai-cloud-global.rokid.com`
- `xr-cloud-global.rokid.com`
- `ar-service.rokid.com`
- `rokid-arapp.oss-accelerate.aliyuncs.com`
- `firebaselogging-pa.googleapis.com`
- `www.googleapis.com`

No direct OpenAI or Gemini provider hostname was demonstrated.

## Private evidence

- Capture label: `01-login`
- Packets: 296
- Duration: approximately 233.27 seconds
- PCAP SHA-256:
  `96ea880522ae6b061e50b204e114adbc6ad0585b43ff18e44a8069b4c86f9199`
- Logcat SHA-256:
  `f1be40b7dc414779b1db36c4af1185eff66b133ac9d85df79ebd547f17acb77c`

## Interpretation

Login initializes Rokid global XR and AI cloud services. The immediate AI
peer appears to be a Rokid-operated gateway, but the upstream model provider
remains unproven.
