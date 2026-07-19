# Test Matrix

| ID | Test | Variable changed | Status |
|---|---|---|---|
| 00 | First launch without login | App launch only | Complete |
| 01 | Login | Authentication state | Complete |
| 02b | Owner unbind and rebind | Account binding | Complete |
| 03a | Firefox TLS canary | MITM validation | Complete — PASS |
| 03b | Hi Rokid idle/model menu | TLS target app | Complete — PASS |
| 04a | Select Gemini base model | Base model only | Complete — VALID WITH OPERATOR MARKER CORRECTION |
| 04b | Select ChatGPT base model | Base model only | Complete — PASS |
| 04c | Select Gemini vision model | Vision model only | Planned |
| 04d | Select ChatGPT vision model | Vision model only | Planned |
| 05a | Gemini controlled voice canary | Selected base model | Complete — PASS |
| 05b | ChatGPT controlled voice canary | Selected base model | Complete — PASS |
| 06a | Local-model compatibility gate | Companion-phone capability | Complete — BLOCKED ON TESTED MOTOROLA PHONE |
| 06b | Translation-mode and audio-routing survey | Translation mode | Complete — CONFIGURATION-SPECIFIC |
| 06c | Device connection and optional peripheral pairing | Peripheral workflow | Complete — CLOSED WITHOUT REFERENCE PERIPHERAL |
| 07 | Connected idle, screen on | Display state | Planned |
| 08 | Connected idle, screen off | Display state | Planned |
| 09 | Background-enabled comparison | Background permission | Planned |
| [10a](10a-face-to-face-input-routing.md) | Face-to-Face input and output routing | Audio source/profile | Complete — PASS |
| [10b](10b-online-translation-services.md) | Online translation service routing | Selected assistant model | Complete — PASS WITH CAPTURE CAVEATS |
| [10c1](10c1-local-model-download.md) | Local-model download provenance | Model download | Complete — PASS |
| [10c2](10c2-local-model-package.md) | Local-model package analysis | Installed package | Complete — PASS |
| [10c3](10c3-offline-local-execution.md) | Offline local execution and TTS | Network and offline voice | Complete — PASS AFTER VOICE INSTALL |
| [10c4](10c4-local-vs-online-flow.md) | Controlled Local-versus-Online flow | Processing mode | Complete — PASS |
| 11 | Gallery and recording | Media action | Planned |
| 12 | OTA check/update | Update action | Planned |

Model selection and prompt submission remain separate captures. Test 10 uses
the repository's public translation numbering even though the original
private capture folders used `07b` and `07c` aliases.
