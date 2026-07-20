# Test 15 — Visual AI Architecture, Routing, Retention, and Context

## Final disposition

**Status: PASS**

Test 15 combines Test 15A workflow discovery with Test 15B routing, retention,
and context-persistence testing for the display-free Rokid AI Glasses Style.

The combined evidence establishes:

- how a visual question triggers the glasses camera;
- how image bytes move from glasses to phone and then cloud;
- how ChatGPT/Gemini visual selections are represented;
- how grounded follow-up questions are handled;
- how conversation thumbnails survive app restarts and offline operation;
- how synthesized answer audio reaches the glasses.

This was an architecture and workflow qualification—not a broad comparison of
vision-model accuracy.

## Private evidence

| Test | Bundle SHA-256 | Manifest entries | PCAP/key-log pairs |
|---|---|---:|---:|
| 15A | `b4214779d8794817eae51a9f317651f46e3ba8015b14679a3829e55fcaabee58` | 149 | 6 |
| 15B | `c86a7c260a4ba1fe99d15ae0bbd1be87fbc88966536baf956158ae29f1bf4ff8` | 189 | 6 |

Across both tests:

- 12 PCAP files
- 12 SSL key logs
- 12 PCAPdroid sidecars
- all capture gates passed
- no glasses restart or power cycle
- relevant AI/OSS TLS sessions decrypted
- Bluetooth HCI evidence available
- raw private evidence excluded from public deliverables

## End-to-end architecture

```text
Wearer speaks a visually grounded question
        ↓
Glasses/phone send audio to Rokid AI WebSocket
        ↓
Rokid performs server-side ASR
        ↓
Rokid agent returns take_photo tool action
        ↓
Hi Rokid sends Ai_TakePhoto over Bluetooth
        ↓
Glasses return a WebP frame over Bluetooth
        ↓
Hi Rokid uploads the WebP to Rokid-managed Aliyun OSS
        ↓
Hi Rokid sends the regional OSS object URL in processing_image
        ↓
Selected visual route processes the current image
        ↓
Rokid streams text plus synthesized_speech
        ↓
Hi Rokid forwards audio bytes to the glasses over Bluetooth
        ↓
Question, thumbnail, and answer are retained in local conversation history
```

## 1. Capture trigger

Opening or remaining in the Assistant did not capture an image.

The agent began image capture only after recognizing a visually grounded
question and returning:

```text
take_photo
```

with `handling_required=true`.

```text
VISION_CAPTURE_TRIGGER=SERVER_TOOL_ACTION_AFTER_VISUAL_ASR
FEATURE_OPEN_CAPTURE=NOT_OBSERVED
```

## 2. Camera and transport

Hi Rokid instructed the glasses:

```text
Ai_TakePhoto {"width":1440,"height":1080,"quality":70}
```

The glasses returned a WebP stream through Bluetooth. The HTTP upload body
matched the Bluetooth-reported image length.

```text
IMAGE_SOURCE=GLASSES_CAMERA
GLASSES_TO_PHONE_TRANSPORT=BLUETOOTH
IMAGE_FORMAT=WEBP
IMAGE_DIMENSIONS=1080x1440
```

The Android phone camera was not used.

## 3. Cloud staging

Each image was uploaded through multipart HTTPS to Rokid's Aliyun OSS staging
host. The AI WebSocket then received a regional OSS object URL in
`processing_image`.

```text
PHONE_TO_CLOUD_TRANSPORT=ALIYUN_OSS_MULTIPART_HTTPS
AI_WEBSOCKET_IMAGE_REPRESENTATION=OBJECT_URL
AI_WEBSOCKET_RAW_IMAGE_BYTES=NO
```

No image was exposed as a normal Android Gallery/MediaStore file.

## 4. Image metadata and privacy

All recovered visual frames were:

- WebP
- `1080 × 1440`
- RGB
- single-frame
- no EXIF
- no GPS metadata
- ICC profile present

The AI session itself contained sensitive account, device, location, weather,
and authorization context. Raw PCAPs, TLS keys, HCI logs, images, complete URLs,
and session messages must remain private.

## 5. Model catalog

Hi Rokid's model catalog separates base and multi/visual models.

### Base models

| Display name | Route |
|---|---|
| ChatGPT | `2d6h8m3qk7s5p9` |
| Gemini | `gEmpl2XKDqHRNDsL` |

### Multi/visual models

| Display name | Route |
|---|---|
| ChatGPT | `5d9h11m6qk10s8p12` |
| Gemini | `gEmEcBf6rTsSwdRc` |

## 6. Visual routing

Across Tests 15A and 15B:

| UI selection | `base_model_no` | `vl_model_no` |
|---|---|---|
| ChatGPT visual | `gEmpl2XKDqHRNDsL` | `5d9h11m6qk10s8p12` |
| Gemini visual | `gEmpl2XKDqHRNDsL` | `gEmEcBf6rTsSwdRc` |

B5 captured a live transition inside one conversation:

```text
ChatGPT vl_model_no → Gemini vl_model_no
```

while `base_model_no` remained unchanged.

Therefore:

```text
VISUAL_UI_SELECTION_FIELD=vl_model_no
VISUAL_ROUTE_CHANGE_WITH_SELECTION=CONFIRMED
VISUAL_BASE_ROUTE_CHANGE_WITH_SELECTION=NOT_OBSERVED
```

The most likely interpretation is that the visual pipeline uses the selected
multi/visual route while retaining a shared/default base route.

The exact public downstream provider/model is not visible.

## 7. Fresh capture policy

Every explicitly visual initial request caused a fresh camera frame.

Test 15B further showed that both grounded follow-ups also caused fresh capture:

- ChatGPT landmark follow-up → new photo
- Gemini watch-time follow-up → new photo

```text
GROUNDED_VISUAL_FOLLOWUP_POLICY=RECAPTURE_CURRENT_SCENE
PRIOR_IMAGE_REUSE_FOR_GROUNDED_FOLLOWUP=NOT_OBSERVED
```

The conversation identifier persisted, but the visual evidence was refreshed.

A vague Test 15A follow-up that did not name a visual detail caused no capture
and received a clarification question. Together, the behavior is:

```text
VAGUE_IMAGE_REFERENCE → ask for clarification, no capture
SPECIFIC_VISUAL_DETAIL → capture a fresh current frame
```

## 8. Conversation-history retention

Every captured image appeared as a thumbnail beside its visual question.

No normal MediaStore image was created.

After force-stopping Hi Rokid and relaunching it while the phone was offline:

- prior question text remained;
- prior answer text remained;
- both captured thumbnails remained;
- thumbnails rendered without placeholders;
- no successful network request was available.

Online relaunch also used the retained thumbnails without a direct OSS fetch.

Therefore:

```text
HI_ROKID_CONVERSATION_IMAGE_RETAINED=YES
ANDROID_MEDIASTORE_IMAGE_CREATED=NO
LOCAL_APP_PRIVATE_PERSISTENT_CACHE=CONFIRMED
ONLINE_DIRECT_OSS_THUMBNAIL_FETCH=NOT_OBSERVED
RETENTION_ARCHITECTURE=REMOTE_OBJECT_PLUS_LOCAL_CACHE
```

The exact private cache/database path remains unresolved.

## 9. Visual context persistence

Test 15 did not confirm that a prior image remains available to the model for a
later grounded question.

When the user asked a specific visual follow-up, Rokid recaptured the scene.

Therefore:

```text
CONVERSATION_TEXT_CONTINUITY=CONFIRMED
PRIOR_IMAGE_MODEL_CONTEXT_PERSISTENCE=NOT_CONFIRMED
CURRENT_SCENE_RECAPTURE_FOR_GROUNDED_QUERY=CONFIRMED
```

## 10. TTS and audio delivery

Rokid's AI WebSocket supplied `synthesized_speech` using a `moss_audio` voice
identifier. Hi Rokid streamed the received audio to the glasses through
Bluetooth.

Android Google TTS was initialized but was not observed synthesizing the visual
assistant answers. Microsoft/Azure TTS was not observed on the phone.

```text
AI_ASSISTANT_TTS_ORIGIN=ROKID_CLOUD
PHONE_TTS_ENGINE_INITIALIZED=GOOGLE_TTS
PHONE_TTS_USED_FOR_AI_ANSWER=NOT_OBSERVED
MICROSOFT_TTS=NOT_CONFIRMED
UPSTREAM_CLOUD_TTS_PROVIDER=UNKNOWN
```

## Final assertions

| Assertion | Result |
|---|---|
| `TEST_15_STATUS` | **PASS** |
| `VISION_CAPTURE_TRIGGER` | **SERVER TOOL AFTER VISUAL ASR** |
| `IMAGE_SOURCE` | **GLASSES CAMERA** |
| `GLASSES_TO_PHONE` | **BLUETOOTH** |
| `PHONE_TO_CLOUD` | **ALIYUN OSS MULTIPART HTTPS** |
| `AI_IMAGE_REPRESENTATION` | **OBJECT URL** |
| `ANDROID_MEDIASTORE_IMAGE` | **NO** |
| `CHATGPT_GEMINI_VISUAL_ROUTE_DIFFERENCE` | **CONFIRMED** |
| `VISUAL_SELECTION_PROPAGATES_VIA_VL_MODEL_NO` | **CONFIRMED** |
| `VISUAL_BASE_ROUTE_CHANGES` | **NOT OBSERVED** |
| `FRESH_CAPTURE_PER_INITIAL_VISUAL_REQUEST` | **CONFIRMED** |
| `FRESH_CAPTURE_PER_GROUNDED_FOLLOWUP` | **CONFIRMED** |
| `PRIOR_IMAGE_REUSE_FOR_GROUNDED_FOLLOWUP` | **NOT OBSERVED** |
| `OFFLINE_HISTORY_TEXT` | **CONFIRMED** |
| `OFFLINE_HISTORY_THUMBNAILS` | **CONFIRMED** |
| `LOCAL_PERSISTENT_THUMBNAIL_CACHE` | **CONFIRMED** |
| `PRIOR_IMAGE_MODEL_CONTEXT_PERSISTENCE` | **NOT CONFIRMED** |
| `ROKID_CLOUD_SYNTHESIZED_AUDIO` | **CONFIRMED** |
| `PHONE_TTS_FOR_ANSWER` | **NOT OBSERVED** |
| `EXACT_DOWNSTREAM_VISION_PROVIDER` | **NOT OBSERVED** |

## Remaining optional research

The primary Test 15 objective is complete. Optional future work could examine:

- cache expiry and deletion;
- OSS object accessibility and lifetime;
- cache behavior after Android storage cleanup;
- retention after logout or device unbind;
- exact Bluetooth RFCOMM/DLCI framing;
- upstream visual and TTS providers.
