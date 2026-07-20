# Test 14B Sanitized Summary

- Connected launch triggered automatic OTA checking.
- Firmware-page entry triggered another check.
- Every manual press made a fresh request.
- Endpoint: `POST ota.rokid.com/v1/extended/ota/check`.
- Installed firmware was sent to the server.
- Response contained a complete OTA manifest.
- Latest-version resolution is hybrid.
- D1 raw-PCAP association was partial; the original connection summary had no
  OTA host.
