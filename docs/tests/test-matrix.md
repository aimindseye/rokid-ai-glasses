# Test Matrix

| ID | Test | Controlled variable | Status |
|---|---|---|---|
| 00 | First launch without login | App launch | Complete |
| 01 | Login | Authentication | Complete |
| 02b | Owner unbind/rebind | Account binding | Complete |
| 03a | Firefox TLS canary | MITM validation | PASS |
| 03b | Hi Rokid idle/model menu | TLS target app | PASS |
| 04a | Select Gemini base model | Model selection | Complete with marker correction |
| 04b | Select ChatGPT base model | Model selection | PASS |
| 05 | ChatGPT/Gemini prompt routing | Base model | Rokid-mediated routing observed |
| 06 | Local capability/peripherals | Phone/device capability | Complete in documented scope |
| 10a–10c4 | Translation architecture series | Mode/context | Complete in existing docs |
| 11 | Gallery/recording | Media action | Planned |
| 12 | Original OTA placeholder | Update action | Superseded by 14B |
| 14A | Initial assistant comparison | ChatGPT vs Gemini | Partial pass |
| 14A-r2 | Fresh-session manual voice | ChatGPT vs Gemini | Primary objective PASS |
| 14B-D1 | Disconnected baseline | Connection | Complete; raw-PCAP association partial |
| 14B-C1 | Connected cold launch | App launch | Automatic OTA request |
| 14B-C2 | Open firmware page | Page entry | Additional OTA request |
| 14B-C3 | First manual check | Button press | Live OTA request |
| 14B-C4 | Repeated manual check | Repeated press | Fresh live OTA request |
| 15A | Visual workflow discovery | Capture and transport path | PASS — glasses WebP → Bluetooth → OSS → object URL |
| 15B | Visual routing, retention, and context | Route switch, follow-up, offline history | PASS — `vl_model_no` switch, grounded recapture, local cache |
| 15 | Consolidated visual AI qualification | 15A + 15B | PASS |
| 16A | Existing-install background lifecycle | Recents vs force-stop vs relaunch | PASS — service/socket survival after swipe; force-stop boundary confirmed |
| 16B | Pixel clean install and first run | Package lineage and pre/post-login traffic | PASS — only Hi Rokid installed; pre-login Firebase/Rokid bootstrap observed |
| 16B-r2 | Clean unauthenticated repair | App-data clear and empty-token check | PASS — `rokidToken` empty before login |
| 16C-r2 | Pairing and paired data sharing | Unpaired, binding, AI, dismissal, relaunch | PASS — broad `init_scene` context; no additional package |
| 16D | Pixel background-mode A/B | Banner unsatisfied vs Unrestricted | PASS — process/services/WebSocket active in both arms |
| 16 | Consolidated Android background and privacy qualification | 16A–16D | PASS in documented scope |

Raw captures remain private. Public reports are sanitized.
