# Test 20 r2 — Safe CXR-L Event and Control-Plane Qualification

## Purpose

Test 20 r2 performs one bounded CXR-L `CUSTOMAPP` connection attempt and
passively observes two ordered pairs of:

- `onGlassAiAssistStart()`
- `onGlassAiAssistStop()`

The test qualifies callback delivery, ordering, repeat behavior, timeout
behavior, automatic disconnect, and Hi Rokid recovery. It does not qualify
camera, microphone, media transport, custom commands, custom views, provider
access, glass-app management, native/JNI behavior, or cloud AI content.

## r2.1 governance repair

The implementation is applied through the Test 20 r2.1 package. The repair
retains analyzer coverage while removing a literal synthetic Bluetooth-address
fixture from the public tree and makes failed-apply rollback remove only
byte-verified overlay-created untracked paths. Runtime scope is unchanged.

## Fixed baseline

- Repository source: accepted Test 20 r1.2 `main`
- CXR-L: `com.rokid.cxr:client-l:1.0.1`
- Hi Rokid: `G1.11.11.0727`
- Glasses firmware: `1.23.009-20260725-153201`
- Test package: `org.aimindseye.rokid.cxreventqualification`
- Version: `1.0-test20-r2` (`versionCode=1`)

## Accepted physical result

The governed build, install, and single physical attempt passed on the fixed
baseline. The accepted sanitized result records:

- two accepted start callbacks;
- two accepted stop callbacks;
- two complete ordered cycles;
- zero duplicate starts;
- zero out-of-order stops;
- one connection attempt;
- terminal `AI_ASSIST_TWO_ORDERED_CYCLES_OBSERVED`;
- clean disconnect; and
- Hi Rokid recovery.

The operator attested that no AI question was spoken or dictated and no stock AI
answer was heard or displayed. The test app recorded no assistant invocation,
cloud AI request, camera access, microphone access, media-stream request, custom
command, custom view, or glass-app-management operation.

This result promotes only `ICXRLinkCbk.onGlassAiAssistStart()V` and
`ICXRLinkCbk.onGlassAiAssistStop()V` from untested to descriptor-exact
runtime-qualified status. See the [accepted event summary](../research/connection-protocol/publication/test20-r2-cxr-l-event-summary.md) and the
[Test 20 r2.2 publication closure](test-20-r2-2-final-ai-assist-callback-publication.md).

## Safety boundary

The test application:

- removes merged `INTERNET`, `CAMERA`, and `RECORD_AUDIO` permissions;
- does not invoke the stock AI assistant;
- does not contain a cloud API client;
- does not invoke photo, audio, media-stream, custom-command, custom-view, or
  glass-app-management methods;
- performs one authorization, one `CUSTOMAPP` configuration, one connection
  attempt, passive callback observation, and one disconnect;
- never logs the authorization token;
- never force-stops or clears Hi Rokid;
- never unpairs, reboots, or changes firmware.

The operator may use the normal stock assistant activation solely to create the
event. The operator must not ask or dictate a question and must cancel before
an answer. This test does **not** claim that unrelated stock background network
traffic is absent; it establishes that the test application sends no cloud AI
request and that no AI query/answer is intentionally generated.

## Required callback sequence

```text
onCXRLConnected(true)
onGlassBtConnected(true)
EVENT_OBSERVATION_ARMED
onGlassAiAssistStart()
onGlassAiAssistStop()
onGlassAiAssistStart()
onGlassAiAssistStop()
AI_ASSIST_TWO_ORDERED_CYCLES_OBSERVED
disconnect()
```

Duplicate starts, stops without an active start, incomplete cycles, a partial
one-cycle repeat, connection loss, or timeout are terminal failures.

## Completed staged execution

1. Build with `scripts/tests/build_test20_r2.sh`.
2. Install with `scripts/tests/install_test20_r2.sh`.
3. Run exactly once with `scripts/tests/run_test20_r2_events.sh`.
4. Review the private evidence ZIP locally.
5. Upload only the sanitized summary ZIP unless private inspection is
   specifically required.

## Accepted classification

```text
TEST20_R2_CLASSIFICATION=CXR_L_AI_ASSIST_EVENT_CALLBACKS_AND_STOCK_RECOVERY_PASS
TEST20_R2_QUALIFICATION=PASS
```

## Evidence boundary

The private evidence contains the JSONL event stream, firmware screenshot,
operator attestations, run metadata, hashes, and sanitized derived summary.
The sanitized ZIP contains only the derived JSON and Markdown summary.


## Final status

```text
TEST20_R2_CALLBACK_RUNTIME_QUALIFICATION=PASS
TEST20_R2_SAFETY_BOUNDARY=PASS
TEST20_R2_FINAL_RUNTIME_STATUS=ACCEPTED
TEST20_R2_PUBLICATION_STATUS=CLOSED_BY_R2_2
```

No second physical run is required for this bounded qualification.
