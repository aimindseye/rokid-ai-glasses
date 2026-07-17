# Test Matrix

| ID | Test | Variable changed | Status |
|---|---|---|---|
| 00 | First launch without login | App launch only | Complete |
| 01 | Login | Authentication state | Complete |
| 02b | Owner unbind and rebind | Account binding | Complete |
| 03a | Firefox TLS canary | MITM validation | Complete — PASS |
| 03b | Hi Rokid idle/model menu | TLS target app | Complete — PASS |
| 04a | Select Gemini base model | Base model only | Next |
| 04b | Select ChatGPT base model | Base model only | Next |
| 04c | Select Gemini vision model | Vision model only | Planned |
| 04d | Select ChatGPT vision model | Vision model only | Planned |
| 05a | Gemini text canary | Prompt only | Planned |
| 05b | ChatGPT text canary | Prompt only | Planned |
| 06a | Gemini vision canary | Image request only | Planned |
| 06b | ChatGPT vision canary | Image request only | Planned |
| 07 | Connected idle, screen on | Display state | Planned |
| 08 | Connected idle, screen off | Display state | Planned |
| 09 | Background enabled comparison | Background permission | Planned |
| 10 | Translation online/offline | Translation model state | Planned |
| 11 | Gallery and recording | Media action | Planned |
| 12 | OTA check/update | Update action | Planned |

Model selection and prompt submission must never occur in the same capture.
