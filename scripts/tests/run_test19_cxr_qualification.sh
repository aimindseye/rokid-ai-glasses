#!/usr/bin/env bash
# Historical Test 19 r1 CXR-M runner is intentionally disabled.
# It mixed ownership, reboot, and PCAPdroid phases and produced an invalid
# ownership classification. Use Test 19 r2 CXR-L scripts instead.

echo "TEST19_R1_WITHDRAWN=YES"
echo "TEST19_R1_RUNNER_DISABLED=YES"
echo "REASON=SUPERSEDED_BY_STAGED_CXR_L_TEST19_R2"
echo "USE=scripts/tests/prepare_test19_r2.sh"
echo "USE=scripts/tests/run_test19_r2_connection.sh"
echo "DEVICE_OPERATION=NONE"
exit 64
