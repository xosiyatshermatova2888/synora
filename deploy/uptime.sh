#!/usr/bin/env bash
# SYNORA uptime probe — exit code is the health signal for host cron / monitoring.
#
#   */5 * * * * /opt/synora/deploy/uptime.sh && echo ok || curl -fsS -m 10 \
#     https://api.uptimerobot.com/...   # ping your monitor
set -uo pipefail

BASE_URL="${SYNORA_UPTIME_URL:-https://$(hostname)}"
TIMEOUT="${SYNORA_UPTIME_TIMEOUT:-15}"

check() {
    local url="$1"
    code=$(curl -s -o /dev/null -w '%{http_code}' -m "$TIMEOUT" "$url" 2>/dev/null) || code=000
    if [ "$code" != "200" ]; then
        echo "[uptime $(date -u +%FT%TZ)] FAIL $code -> $url"
        return 1
    fi
    echo "[uptime $(date -u +%FT%TZ)] ok $url"
}

fail=0
check "$BASE_URL/api/v1/health"   || fail=1
check "$BASE_URL/api/v1/health/ready" || fail=1
check "$BASE_URL/uz"              || fail=1
exit "$fail"