# Test 03 — TLS Interception

## 03a — Firefox validation

### Purpose

Validate the PCAPdroid MITM configuration with a unique browser canary before
applying it to Hi Rokid.

### Result

PASS.

PCAPdroid displayed a green decrypted HTTPS connection and exposed the full
HTTP/2 request path:

    /ROKID_TLS_CANARY_20260716_FA12

The server returned HTTP 404, which was expected because the unique canary
path did not exist. Request headers, response headers, and the response body
were readable in PCAPdroid.

Earlier failed attempts recorded a certificate-trust error. The later green
connection is the accepted validation gate.

## 03b — Hi Rokid idle and model-management baseline

### Actions

- Force-stopped Hi Rokid
- Started app-filtered PCAPdroid TLS interception
- Opened Assistant, Home, and Model Management
- Opened base- and vision-model selectors without changing either model
- Submitted no prompt and no image
- Left background execution disabled
- Did not download the offline translation model

### Result

PASS for decryptable application traffic.

The PCAP plus SSL keylog produced decoded:

- HTTP/1.1
- HTTP/2
- JSON
- WebSocket traffic

Important observed endpoints included:

- `ai-cloud-global.rokid.com/manager/v3/api/model/aggregate`
- `ai-cloud-global.rokid.com/ws/ai`
- `xr-cloud-global.rokid.com/auth/base/asr/getToken`
- `device-account-prod.rokid.com/device/loginV6.do`
- `rcs-internal.rokid.com/device/bindGlassesDevice`
- Rokid home, feature-check, geolocation, OTA, and telemetry endpoints

All query values in public evidence are redacted.

### Security handling

The decrypted capture contained account credentials, device identifiers, and
an ASR token. Raw PCAP, SSL keylog, HTTP exports, and logcat remain private.
The test-account session should be rotated before model-selection tests.

### Interpretation

Hi Rokid communicates with a Rokid model-catalog endpoint and a Rokid AI
WebSocket gateway. The capture does not yet prove whether ChatGPT or Gemini is
the upstream provider for any specific request.
